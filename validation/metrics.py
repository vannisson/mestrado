# metrics.py
# =============================================================================
# Métricas de validação para DT/AGV
# - MAE, MSE, RMSE
# - MAPE (robusta perto de zero)
# - DTW com janela (Sakoe–Chiba)
# - Estimativa de defasagem (lag) via correlação cruzada normalizada
#
# Uso típico:
#   from metrics import mae, mse, rmse, mape, dtw_cost, lag_xcorr_ms, 
# =============================================================================

from typing import Callable, Iterable, Optional
import numpy as np
import math


# ------------------------------ Básicas ------------------------------------- #

def mae(x: Iterable[float], y: Iterable[float]) -> float:
    """
    Mean Absolute Error (mesmas unidades do sinal).
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    return float(np.mean(np.abs(x - y)))


def mse(x: Iterable[float], y: Iterable[float]) -> float:
    """
    Mean Squared Error.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    return float(np.mean((x - y) ** 2))


def rmse(x: Iterable[float], y: Iterable[float]) -> float:
    """
    Root Mean Squared Error (penaliza mais outliers).
    """
    return float(np.sqrt(mse(x, y)))


def mape(
    x: Iterable[float],
    y: Iterable[float],
    eps: float = 1e-6,
) -> float:
    """
    Mean Absolute Percentage Error (robusta perto de zero).

    - Ignora amostras onde |x| <= eps para evitar explosão percentual
      em regiões próximas de zero.
    - Retorna 0.0 se não houver amostras válidas após o filtro.

    Retorno em PERCENTUAL (0–100).
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    mask = np.abs(x) > eps
    if not np.any(mask):
        return 0.0
    return float(100.0 * np.mean(np.abs(x[mask] - y[mask]) / np.abs(x[mask])))


# ------------------------------ Defasagem ----------------------------------- #

def lag_xcorr_ms(
    x: Iterable[float],
    y: Iterable[float],
    fs_hz: float,
) -> float:
    """
    Estima o lag (em milissegundos) que maximiza a correlação cruzada normalizada.

    - Remove média de cada série.
    - Normaliza pela norma (correlação de correlação).
    - Retorna lag > 0 se y está ATRASADO em relação a x (y(t) ≈ x(t - lag)).

    Parâmetros
    ----------
    x, y : sequências numéricas (mesmo comprimento, amostradas à mesma taxa)
    fs_hz : float
        Frequência de amostragem em Hz.

    Retorna
    -------
    float
        Defasagem em milissegundos.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if len(x) == 0 or len(y) == 0:
        return 0.0

    x = x - np.mean(x)
    y = y - np.mean(y)
    denom = np.linalg.norm(x) * np.linalg.norm(y)
    if denom == 0:
        return 0.0

    corr = np.correlate(x, y, mode='full') / denom
    k = int(np.argmax(corr))
    lag_samples = k - (len(x) - 1)

    # >>> ajuste para cumprir a docstring:
    lag_seconds = (-lag_samples) / float(fs_hz)
    return float(lag_seconds * 1000.0)

# ==========================
# Bloco de compatibilidade
# ==========================

def dtw_cost_and_path_length_nd(
    X: Iterable[Iterable[float]],
    Y: Iterable[Iterable[float]],
    window: Optional[int] = None,
    metric: str = "euclidean",
    weights: Optional[Iterable[float]] = None,
) -> tuple[float, int]:
    """
    Retorna (custo_total_DTW, tamanho_do_caminho) para séries multivariadas.
    Cada amostra é vetor em R^D. Usa norma -> custo escalar.
    """
    X = np.asarray(X, dtype=float)
    Y = np.asarray(Y, dtype=float)
    if X.ndim == 1: X = X[:, None]
    if Y.ndim == 1: Y = Y[:, None]

    n, Dx = X.shape
    m, Dy = Y.shape
    if Dx != Dy:
        raise ValueError(f"Dimensão incompatível: {Dx} vs {Dy}")

    if n == 0 and m == 0:
        return (0.0, 0)
    if n == 0 or m == 0:
        # custo = soma das normas das amostras remanescentes; caminho = n+m
        return (float(np.sum(np.linalg.norm(X, axis=1)) + np.sum(np.linalg.norm(Y, axis=1))), int(n + m))

    if window is None:
        window = max(n, m)
    window = max(int(window), abs(n - m))

    if weights is not None:
        w = np.asarray(weights, dtype=float).reshape(1, -1)
        if w.shape[1] != Dx:
            raise ValueError("weights deve ter mesmo D das séries")
    else:
        w = None

    def point_cost(a, b) -> float:
        d = a - b
        if w is not None:
            d = d * w
        if metric == "manhattan":
            return float(np.sum(np.abs(d)))
        return float(np.linalg.norm(d))  # euclidiana

    Dacc = np.full((n + 1, m + 1), np.inf, dtype=np.float64)
    Dacc[0, 0] = 0.0

    for i in range(1, n + 1):
        j_start = max(1, i - window)
        j_end   = min(m, i + window)
        xi = X[i - 1]
        for j in range(j_start, j_end + 1):
            c = point_cost(xi, Y[j - 1])
            Dacc[i, j] = c + min(Dacc[i - 1, j], Dacc[i, j - 1], Dacc[i - 1, j - 1])

    # backtracking para comprimento do caminho
    i, j = n, m
    path_len = 0
    while i > 0 or j > 0:
        path_len += 1
        up   = Dacc[i - 1, j]     if i > 0 else np.inf
        left = Dacc[i, j - 1]     if j > 0 else np.inf
        diag = Dacc[i - 1, j - 1] if (i > 0 and j > 0) else np.inf
        if diag <= up and diag <= left:
            i -= 1; j -= 1
        elif up <= left:
            i -= 1
        else:
            j -= 1

    return float(Dacc[n, m]), int(path_len)


def dtw_cost_nd(
    X: Iterable[Iterable[float]],
    Y: Iterable[Iterable[float]],
    window: Optional[int] = None,
    metric: str = "euclidean",
    weights: Optional[Iterable[float]] = None,
) -> float:
    total, _ = dtw_cost_and_path_length_nd(X, Y, window=window, metric=metric, weights=weights)
    return float(total)


def dtw_cost_normalized_nd(
    X: Iterable[Iterable[float]],
    Y: Iterable[Iterable[float]],
    window: Optional[int] = None,
    metric: str = "euclidean",
    weights: Optional[Iterable[float]] = None,
) -> float:
    total, L = dtw_cost_and_path_length_nd(X, Y, window=window, metric=metric, weights=weights)
    if L <= 0:
        return 0.0
    return float(total / L)

# =============================================================================
# MÉTRICAS ADICIONAIS DE SINCRONIZAÇÃO TEMPORAL E FIDELIDADE ESPACIAL
# =============================================================================
def windowed_dtw(
    x: Iterable[float],
    y: Iterable[float],
    fs_hz: float,
    window_s: float = 1.0,
    step_s: Optional[float] = None,
) -> tuple[list[float], list[float]]:
    """
    Calcula o DTW normalizado em janelas deslizantes.
    Retorna (tempos_centro_janela, lista_dtw_valores).

    Útil para observar variação temporal da sincronização (jitter).
    """
    step_s = step_s or (window_s / 2.0)
    win = int(window_s * fs_hz)
    step = int(step_s * fs_hz)
    if win <= 0 or len(x) < win or len(y) < win:
        return [], []
    vals, times = [], []
    for i in range(0, len(x) - win, step):
        seg_x = x[i:i+win]
        seg_y = y[i:i+win]
        t_center = (i + win/2) / fs_hz
        try:
            val = dtw_cost_normalized_nd(seg_x, seg_y)
        except Exception:
            val = math.nan
        vals.append(val)
        times.append(t_center)
    return times, vals


def lag_variance(
    x: Iterable[float],
    y: Iterable[float],
    fs_hz: float,
    window_s: float = 1.0,
    step_s: Optional[float] = None,
) -> tuple[float, float]:
    """
    Mede a estabilidade temporal da sincronização.
    Retorna (média_ms, desvio_padrao_ms) dos lags em janelas.

    Se o desvio for alto -> jitter temporal significativo.
    """
    step_s = step_s or (window_s / 2.0)
    win = int(window_s * fs_hz)
    step = int(step_s * fs_hz)
    if win <= 0 or len(x) < win or len(y) < win:
        return (0.0, 0.0)
    lags = []
    for i in range(0, len(x) - win, step):
        seg_x = x[i:i+win]
        seg_y = y[i:i+win]
        lag = lag_xcorr_ms(seg_x, seg_y, fs_hz)
        lags.append(lag)
    if not lags:
        return (0.0, 0.0)
    return float(np.mean(lags)), float(np.std(lags))


def pearson_corr(
    x: Iterable[float],
    y: Iterable[float],
) -> float:
    """
    Coeficiente de correlação de Pearson (ρ).
    Mede a coerência linear entre as séries.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if len(x) != len(y) or len(x) < 2:
        return 0.0
    x_m, y_m = np.mean(x), np.mean(y)
    num = np.sum((x - x_m) * (y - y_m))
    den = math.sqrt(np.sum((x - x_m)**2) * np.sum((y - y_m)**2))
    return float(num / den) if den != 0 else 0.0


def discrete_frechet_distance(P: Iterable[Iterable[float]], Q: Iterable[Iterable[float]]) -> float:
    """
    Distância de Fréchet discreta entre duas trajetórias (x,y).
    Mede similaridade espacial independente do tempo.
    """
    P = np.asarray(P, dtype=float)
    Q = np.asarray(Q, dtype=float)
    n, m = len(P), len(Q)
    ca = np.full((n, m), -1.0)

    def dist(i, j):
        return np.linalg.norm(P[i] - Q[j])

    def rec(i, j):
        if ca[i, j] > -1:
            return ca[i, j]
        if i == 0 and j == 0:
            ca[i, j] = dist(0, 0)
        elif i > 0 and j == 0:
            ca[i, j] = max(rec(i-1, 0), dist(i, 0))
        elif i == 0 and j > 0:
            ca[i, j] = max(rec(0, j-1), dist(0, j))
        elif i > 0 and j > 0:
            ca[i, j] = max(
                min(rec(i-1, j), rec(i-1, j-1), rec(i, j-1)),
                dist(i, j)
            )
        else:
            ca[i, j] = float("inf")
        return ca[i, j]

    return float(rec(n-1, m-1))


def edr_distance(
    x: Iterable[float],
    y: Iterable[float],
    epsilon: float = 0.05,
) -> float:
    """
    Edit Distance on Real sequences (EDR).
    Tolerante a ruído, mede diferença estrutural entre séries.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    n, m = len(x), len(y)
    if n == 0 or m == 0:
        return float(max(n, m))
    dp = np.zeros((n+1, m+1))
    dp[:, 0] = np.arange(n+1)
    dp[0, :] = np.arange(m+1)

    for i in range(1, n+1):
        for j in range(1, m+1):
            cost = 0 if abs(x[i-1] - y[j-1]) <= epsilon else 1
            dp[i, j] = min(
                dp[i-1, j] + 1,      # deleção
                dp[i, j-1] + 1,      # inserção
                dp[i-1, j-1] + cost  # substituição
            )
    return float(dp[n, m])


# ---- Aliases para compatibilidade com os outros módulos ----
compute_mae  = mae
compute_mse  = mse
compute_rmse = rmse
compute_mape = mape

compute_dtw = dtw_cost_nd
compute_dtw_normalized = dtw_cost_normalized_nd
# nomes que os outros scripts esperam:
compute_dtw_and_path_length = dtw_cost_and_path_length_nd
compute_dtw_normalized      = dtw_cost_normalized_nd
lag_ms = lag_xcorr_ms  # se alguém usar esse atalho

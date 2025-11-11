# validator.py
# =============================================================================
# Validator principal para comparar as séries temporais do AGV fonte e gêmeo.
# - Alinha streams (odometria, rodas, IMU) por timestamp
# - Calcula métricas MAE, RMSE, MAPE, DTW e lag
# - Gera arquivos metrics.json e metrics.csv
# =============================================================================

import os
import json
import csv
from typing import Dict, Any, Tuple
import numpy as np
import pandas as pd
from metrics import (
    mae, rmse, mape, dtw_cost, lag_xcorr_ms,
    windowed_dtw, lag_variance, pearson_corr,
    discrete_frechet_distance, edr_distance
)

# --------------------------------------------------------------------------- #
# Funções utilitárias
# --------------------------------------------------------------------------- #

def _ensure_dir(path: str):
    """Cria diretório se não existir."""
    os.makedirs(os.path.dirname(path), exist_ok=True)


def _resample(df: pd.DataFrame, dt: float, tcol: str = "t") -> pd.DataFrame:
    """
    Reamostra DataFrame para passo temporal fixo (interpolação linear).
    Assume que df[tcol] está em segundos.
    """
    if tcol not in df.columns:
        raise ValueError(f"Coluna de tempo '{tcol}' ausente em {df.columns}")
    df = df.sort_values(tcol)
    t0, t1 = df[tcol].iloc[0], df[tcol].iloc[-1]
    grid = np.arange(t0, t1, dt)
    out = {tcol: grid}
    for col in df.columns:
        if col == tcol:
            continue
        out[col] = np.interp(grid, df[tcol].to_numpy(), df[col].to_numpy())
    return pd.DataFrame(out)


def _pair_metrics(
    ref_df: pd.DataFrame,
    twin_df: pd.DataFrame,
    dt: float,
    fs_hz: float,
    dtw_window: int = None,
) -> Dict[str, Dict[str, float]]:
    """
    Calcula métricas entre dois DataFrames alinhados temporalmente.
    Cada coluna (exceto 't') é considerada uma variável a ser comparada.

    Inclui métricas adicionais:
    - DTW em janela (windowed_dtw)
    - Variação de lag (lag_variance)
    - Correlação (pearson_corr)
    - EDR (Edit Distance on Real sequences)
    - Fréchet (para dados com pares x,y)
    """
    ref = _resample(ref_df, dt)
    twin = _resample(twin_df, dt)
    n = min(len(ref), len(twin))
    ref = ref.iloc[:n]
    twin = twin.iloc[:n]

    out = {}

    for col in [c for c in ref.columns if c != "t"]:
        x = ref[col].to_numpy()
        y = twin[col].to_numpy()

        _mae = mae(x, y)
        _rmse = rmse(x, y)
        _mape = mape(x, y)
        _dtw = dtw_cost(x, y, window=dtw_window)
        _lag = lag_xcorr_ms(x, y, fs_hz)

        # --- Novas métricas ---
        _, _dtw_win_vals = windowed_dtw(x, y, fs_hz, window_s=1.0)
        _dtw_var = float(np.nanstd(_dtw_win_vals)) if _dtw_win_vals else 0.0

        _lag_mean, _lag_std = lag_variance(x, y, fs_hz, window_s=1.0)
        _corr = pearson_corr(x, y)
        _edr = edr_distance(x, y, epsilon=0.05)

        _frechet = None
        if {"x", "y"}.issubset(ref.columns):
            path_real = ref[["x", "y"]].to_numpy()
            path_twin = twin[["x", "y"]].to_numpy()
            _frechet = discrete_frechet_distance(path_real, path_twin)

        out[col] = dict(
            mae=_mae,
            rmse=_rmse,
            mape=_mape,
            dtw=_dtw,
            lag_ms=_lag,
            dtw_var=_dtw_var,
            lag_mean_ms=_lag_mean,
            lag_std_ms=_lag_std,
            pearson_r=_corr,
            edr=_edr,
            frechet=_frechet if _frechet is not None else 0.0
        )

    return out


# --------------------------------------------------------------------------- #
# Função principal de validação
# --------------------------------------------------------------------------- #

def validate_pair(
    source_dir: str,
    twin_dir: str,
    out_dir: str,
    dt: float = 0.05,
    buffer_horizon: float = 3.0,
    fs_hz: float = 20.0,
):
    """
    Executa validação completa entre source e twin.
    Espera arquivos CSV com nomes: odom.csv, wheels.csv, imu.csv.
    Cada arquivo deve conter coluna 't' e variáveis numéricas correspondentes.

    Parâmetros
    ----------
    source_dir : str
        Diretório contendo CSVs do AGV fonte.
    twin_dir : str
        Diretório contendo CSVs do AGV gêmeo.
    out_dir : str
        Diretório onde metrics.json e metrics.csv serão salvos.
    dt : float
        Passo temporal (s) para reamostragem.
    buffer_horizon : float
        Horizonte de buffer (s), atualmente não usado diretamente.
    fs_hz : float
        Frequência de amostragem para cálculo de lag (Hz).
    """
    channels = ["odom", "wheels", "imu"]
    results = {}

    for ch in channels:
        src_path = os.path.join(source_dir, f"{ch}.csv")
        twin_path = os.path.join(twin_dir, f"{ch}.csv")
        if not (os.path.exists(src_path) and os.path.exists(twin_path)):
            print(f"[warn] Arquivos ausentes para canal '{ch}', pulando.")
            continue

        ref_df = pd.read_csv(src_path)
        twin_df = pd.read_csv(twin_path)

        # Janela DTW = 20% do tamanho da série
        dtw_window = int(0.2 * min(len(ref_df), len(twin_df)))
        metrics_dict = _pair_metrics(ref_df, twin_df, dt, fs_hz, dtw_window)
        results[ch] = metrics_dict

    # Salvar JSON completo
    _ensure_dir(os.path.join(out_dir, "metrics.json"))
    with open(os.path.join(out_dir, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    # Salvar CSV simplificado
    rows = []
    for ch, vars_dict in results.items():
        for var, md in vars_dict.items():
            rows.append([
                ch, var,
                md["mae"], md["rmse"], md["mape"], md["dtw"], md["lag_ms"],
                md["dtw_var"], md["lag_mean_ms"], md["lag_std_ms"],
                md["pearson_r"], md["edr"], md["frechet"]
            ])

    _ensure_dir(os.path.join(out_dir, "metrics.csv"))
    with open(os.path.join(out_dir, "metrics.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "channel", "var", "mae", "rmse", "mape", "dtw", "lag_ms",
            "dtw_var", "lag_mean_ms", "lag_std_ms", "pearson_r", "edr", "frechet"
        ])
        w.writerows(rows)

    print(f"[ok] Métricas salvas em {out_dir}/metrics.json e metrics.csv")
    return results


# --------------------------------------------------------------------------- #
# Execução direta via CLI
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Offline validation between source and twin runs.")
    ap.add_argument("--source", required=True, help="Diretório com CSVs do AGV fonte")
    ap.add_argument("--twin", required=True, help="Diretório com CSVs do AGV gêmeo")
    ap.add_argument("--out", required=True, help="Diretório de saída (resultados)")
    ap.add_argument("--dt", type=float, default=0.05, help="Passo temporal para reamostragem (s)")
    ap.add_argument("--fs", type=float, default=20.0, help="Frequência de amostragem (Hz)")
    args = ap.parse_args()

    results = validate_pair(args.source, args.twin, args.out, dt=args.dt, fs_hz=args.fs)

    print(json.dumps(results, indent=2))

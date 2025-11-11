"""
plot_metrics.py
============================================================
Validação quantitativa de Gêmeos Digitais (AGV ↔ Twin)
Autor: Geo / Mestrado (UFAL)
============================================================
"""

import os
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from metrics import lag_xcorr_ms

# ----------------------------------------------------------
# CONFIGURAÇÃO
# ----------------------------------------------------------
COLOR_REAL = "#0072B2"   # azul (AGV real)
COLOR_TWIN = "#E69F00"   # laranja (Gêmeo)
COLOR_ERR  = "#D55E00"   # vermelho (erro)
FS_HZ = 20.0
plt.ioff()  # não abre figuras

# ----------------------------------------------------------
# FUNÇÕES AUXILIARES
# ----------------------------------------------------------
def load_csv_pair(source_dir: Path, twin_dir: Path, name: str):
    """Carrega CSVs (AGV e Twin), interpola Twin para o tempo do AGV."""
    df_r = pd.read_csv(source_dir / f"{name}.csv")
    df_t = pd.read_csv(twin_dir / f"{name}.csv")
    if "t" not in df_r or "t" not in df_t:
        raise ValueError(f"'{name}.csv' deve conter coluna 't'.")

    df_t_interp = pd.DataFrame({"t": df_r["t"]})
    for c in [c for c in df_t.columns if c != "t"]:
        df_t_interp[c] = np.interp(df_r["t"], df_t["t"], df_t[c])

    return df_r, df_t_interp


def save_fig(fig, out_dir: Path, name: str):
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / name
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)
    print(f"[plot_metrics] Figura salva: {path}")


def normalize(x):
    x = np.asarray(x)
    return (x - np.nanmean(x)) / (np.nanstd(x) + 1e-9)


# ----------------------------------------------------------
# GRÁFICOS
# ----------------------------------------------------------
def plot_trajectory(ref, twin, out_dir):
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.plot(ref["x"], ref["y"], COLOR_REAL, lw=1.8, label="AGV Real")
    ax.plot(twin["x"], twin["y"], COLOR_TWIN, "--", lw=1.8, label="Twin")
    ax.scatter(ref["x"].iloc[0], ref["y"].iloc[0], c="green", marker="o", label="Início")
    ax.scatter(ref["x"].iloc[-1], ref["y"].iloc[-1], c="red", marker="x", label="Fim")
    ax.set_title("Trajetórias XY")
    ax.set_xlabel("X (m)"); ax.set_ylabel("Y (m)")
    ax.axis("equal"); ax.grid(True, ls="--", alpha=0.6); ax.legend()
    save_fig(fig, out_dir, "trajectory_xy.png")


def plot_time_series(ref, twin, var, out_dir):
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(ref["t"], ref[var], COLOR_REAL, lw=1.5, label="AGV Real")
    ax.plot(twin["t"], twin[var], COLOR_TWIN, "--", lw=1.5, label="Twin")
    ax.set_title(f"Séries temporais – {var}")
    ax.set_xlabel("Tempo (s)"); ax.set_ylabel(var)
    ax.legend(); ax.grid(True, ls="--", alpha=0.6)
    save_fig(fig, out_dir, f"time_series_{var}.png")


def plot_error_time_series(ref, twin, var, out_dir):
    err = np.abs(ref[var] - twin[var])
    fig, ax = plt.subplots(figsize=(8, 3))
    ax.plot(ref["t"], err, color=COLOR_ERR, lw=1.2)
    ax.set_title(f"Erro absoluto – {var}")
    ax.set_xlabel("Tempo (s)"); ax.set_ylabel(f"|Δ{var}| (m ou rad)")
    ax.grid(True, ls="--", alpha=0.6)
    save_fig(fig, out_dir, f"error_time_{var}.png")


def plot_cross_correlation(ref, twin, var, out_dir):
    x, y = normalize(ref[var]), normalize(twin[var])
    corr = np.correlate(x, y, mode="full")
    corr /= np.max(np.abs(corr))  # normaliza
    lags = np.arange(-len(x)+1, len(x))
    lags_sec = lags / FS_HZ
    lag_ms = lag_xcorr_ms(x, y, FS_HZ)

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(lags_sec, corr, color="#009E73")
    ax.axvline(x=lag_ms/1000.0, color="r", ls="--", label=f"Lag={lag_ms/1000:.2f}s")
    ax.set_xlim(-5, 5)
    ax.set_ylim(-1.1, 1.1)
    ax.set_title(f"Correlação cruzada – {var}")
    ax.set_xlabel("Defasagem (s)"); ax.set_ylabel("Correlação normalizada")
    ax.legend(); ax.grid(True, ls="--", alpha=0.6)
    save_fig(fig, out_dir, f"crosscorr_{var}.png")


def plot_global_correlation(ref, twin, out_dir):
    r_x = np.corrcoef(ref["x"], twin["x"])[0, 1]
    r_y = np.corrcoef(ref["y"], twin["y"])[0, 1]
    r_th = np.corrcoef(ref["theta"], twin["theta"])[0, 1]
    fig, ax = plt.subplots(figsize=(4, 4))
    bars = ax.bar(["x", "y", "θ"], [r_x, r_y, r_th],
                  color=[COLOR_REAL, COLOR_TWIN, "#009E73"], alpha=0.8)
    ax.set_ylim(0, 1)
    ax.set_ylabel("Coeficiente de correlação (r)")
    ax.set_title("Correlação linear global (AGV ↔ Twin)")
    for bar in bars:
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
                f"{bar.get_height():.3f}", ha="center", va="bottom", fontsize=9)
    save_fig(fig, out_dir, "correlation_global.png")


def plot_metric_histograms(metrics_csv, out_dir):
    df = pd.read_csv(metrics_csv)
    metric_cols = [c for c in df.columns if c not in ["epoch", "timestamp"]]
    for m in metric_cols:
        fig, ax = plt.subplots(figsize=(5, 3))
        ax.hist(df[m].astype(float), bins=30, color="#56B4E9",
                edgecolor="black", alpha=0.7)
        ax.set_title(f"Distribuição – {m}")
        ax.set_xlabel(m); ax.set_ylabel("Frequência")
        ax.grid(True, ls="--", alpha=0.5)
        save_fig(fig, out_dir, f"hist_{m}.png")


# ----------------------------------------------------------
# MAIN
# ----------------------------------------------------------
if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--metrics_dir", required=True, help="Diretório do experimento.")
    args = ap.parse_args()

    METRICS_DIR = Path(args.metrics_dir)
    OUT_DIR = METRICS_DIR / "figs"
    SRC, TWIN = METRICS_DIR / "agv_logs", METRICS_DIR / "twin_logs"

    print(f"[plot_metrics] Gerando figuras em: {OUT_DIR}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if SRC.exists() and TWIN.exists():
        try:
            ref, twin = load_csv_pair(SRC, TWIN, "odom")

            # Séries temporais + erros
            for var in ["x", "y", "theta"]:
                plot_time_series(ref, twin, var, OUT_DIR)
                plot_error_time_series(ref, twin, var, OUT_DIR)
                plot_cross_correlation(ref, twin, var, OUT_DIR)

            # Correlação global
            plot_global_correlation(ref, twin, OUT_DIR)

            # Trajetória
            plot_trajectory(ref, twin, OUT_DIR)

        except Exception as e:
            print(f"[plot_metrics] Falha ao gerar figuras: {e}")
    else:
        print("[plot_metrics] ⚠️ Logs agv/twin não encontrados neste cenário.")

    metrics_csv = METRICS_DIR / "metrics.csv"
    if metrics_csv.exists():
        plot_metric_histograms(metrics_csv, OUT_DIR)

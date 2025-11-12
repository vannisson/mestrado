# plot_semi_metrics.py
# ============================================================
# Gera figuras apenas a partir de metrics.csv (sem logs AGV/Twin)
# Autor: Geo / Mestrado (UFAL)
# ============================================================

from pathlib import Path
import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

plt.ioff()  # não abrir janelas

# ------------------------------------------------------------
# Utils
# ------------------------------------------------------------
def save_fig(fig, out_dir: Path, name: str):
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / name
    fig.tight_layout()
    fig.savefig(path, dpi=220)
    plt.close(fig)
    print(f"[plot] saved: {path}")

def as_float_series(df: pd.DataFrame, col: str):
    if col not in df.columns:
        return None
    s = pd.to_numeric(df[col], errors="coerce")
    return s.dropna()

def hist_auto(series: pd.Series, title: str, out_dir: Path, fname: str, bins=30):
    if series is None or series.empty:
        return
    fig, ax = plt.subplots(figsize=(5.2, 3.4))
    ax.hist(series.values.astype(float), bins=bins, edgecolor="black", alpha=0.75)
    ax.set_title(title)
    ax.set_xlabel(fname.split("hist_")[-1].split(".png")[0])
    ax.set_ylabel("Frequência")
    ax.grid(True, ls="--", alpha=0.45)
    save_fig(fig, out_dir, fname)

def hist_clipped(series: pd.Series, title: str, out_dir: Path, fname: str, p=99.0, bins=30):
    if series is None or series.empty:
        return
    hi = np.nanpercentile(series, p)
    lo = np.nanpercentile(series, 100 - p) if p > 50 else np.nanmin(series)
    s = series[(series >= lo) & (series <= hi)]
    fig, ax = plt.subplots(figsize=(5.2, 3.4))
    ax.hist(s.values.astype(float), bins=bins, edgecolor="black", alpha=0.75)
    ax.set_title(f"{title} (≤ p{int(p)})")
    ax.set_xlabel(fname.split("hist_")[-1].split(".png")[0])
    ax.set_ylabel("Frequência")
    ax.grid(True, ls="--", alpha=0.45)
    note = f"clipped at p{int(p)}={hi:.2g}"
    ax.text(0.98, 0.98, note, ha="right", va="top", transform=ax.transAxes, fontsize=8)
    save_fig(fig, out_dir, fname)

def scatter_xy(x: pd.Series, y: pd.Series, title: str, out_dir: Path, fname: str,
               xlabel: str, ylabel: str):
    if x is None or y is None or x.empty or y.empty:
        return
    n = min(len(x), len(y))
    x = x.iloc[:n].astype(float)
    y = y.iloc[:n].astype(float)

    fig, ax = plt.subplots(figsize=(5.2, 4.2))
    ax.scatter(x, y, s=12, alpha=0.6)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(True, ls="--", alpha=0.45)
    # correlação de Pearson (robusta a NaN já removidos)
    try:
        r = np.corrcoef(x, y)[0, 1]
        ax.text(0.98, 0.02, f"r = {r:.3f}", ha="right", va="bottom",
                transform=ax.transAxes, fontsize=9)
    except Exception:
        pass
    save_fig(fig, out_dir, fname)

# ------------------------------------------------------------
# Main
# ------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--metrics_csv", required=True, help="Caminho para metrics.csv")
    ap.add_argument("--out_dir", default=None, help="Diretório de saída (default: figs/ ao lado do CSV)")
    ap.add_argument("--label", default="", help="Rótulo opcional para compor nomes de arquivos (ex.: delay, perturbed)")
    ap.add_argument("--bins", type=int, default=30, help="Bins dos histogramas (default: 30)")
    ap.add_argument("--clip_p", type=float, default=99.0, help="Percentil do hist recortado (default: 99)")
    args = ap.parse_args()

    metrics_csv = Path(args.metrics_csv)
    if not metrics_csv.is_file():
        raise FileNotFoundError(f"metrics.csv não encontrado: {metrics_csv}")

    out_dir = Path(args.out_dir) if args.out_dir else metrics_csv.parent / "figs"
    label_suffix = f"_{args.label}" if args.label else ""

    df = pd.read_csv(metrics_csv)

    # salva um summary com percentis úteis
    desc = df.apply(pd.to_numeric, errors="ignore")
    numeric_cols = desc.select_dtypes(include=[np.number]).columns.tolist()
    summary = desc[numeric_cols].describe(percentiles=[0.05, 0.25, 0.5, 0.75, 0.95]).T
    summary_path = out_dir / f"summary{label_suffix}.csv"
    out_dir.mkdir(parents=True, exist_ok=True)
    summary.to_csv(summary_path)
    print(f"[plot] summary -> {summary_path}")

    # --- séries numéricas de interesse (se existirem)
    mse   = as_float_series(df, "mse")
    rmse  = as_float_series(df, "rmse")
    mae   = as_float_series(df, "mae")
    mape  = as_float_series(df, "mape")
    dtw_c = as_float_series(df, "dtw_cru")    # custo DTW “cru”
    dtw_n = as_float_series(df, "dtw_norm")   # DTW normalizado
    frech = as_float_series(df, "frechet_xy")
    edr_x = as_float_series(df, "edr_x")
    edr_y = as_float_series(df, "edr_y")
    p_x   = as_float_series(df, "pearson_x")
    p_y   = as_float_series(df, "pearson_y")
    lag_x = as_float_series(df, "lag_x_ms")
    lag_y = as_float_series(df, "lag_y_ms")

    # --------------------------------------------------------
    # 1) Histogramas básicos (todas as numéricas)
    # --------------------------------------------------------
    for col in numeric_cols:
        series = as_float_series(df, col)
        if series is None: 
            continue
        hist_auto(series, f"Distribuição – {col}",
                  out_dir, f"hist_{col}{label_suffix}.png", bins=args.bins)

    # 1.1) Versões "clipped" (útil para MAPE e outliers grandes)
    if mape is not None:
        hist_clipped(mape, "MAPE", out_dir, f"hist_mape_clipped{label_suffix}.png",
                     p=args.clip_p, bins=args.bins)

    # --------------------------------------------------------
    # 2) Plots “core” para o artigo
    # --------------------------------------------------------
    # RMSE vs DTW_norm (separação: atraso x modelo ruim)
    scatter_xy(rmse, dtw_n,
               f"RMSE vs DTW_norm{label_suffix}",
               out_dir, f"scatter_rmse_vs_dtw_norm{label_suffix}.png",
               xlabel="RMSE", ylabel="DTW_norm")

    # DTW_norm vs lag (captura sincronização)
    # usa lag médio (x,y) se ambos existirem
    lag_avg = None
    if lag_x is not None and lag_y is not None:
        lag_avg = (lag_x + lag_y) / 2.0
    elif lag_x is not None:
        lag_avg = lag_x
    elif lag_y is not None:
        lag_avg = lag_y

    scatter_xy(dtw_n, lag_avg,
               f"DTW_norm vs Lag (ms){label_suffix}",
               out_dir, f"scatter_dtw_norm_vs_lag{label_suffix}.png",
               xlabel="DTW_norm", ylabel="Lag (ms)")

    # RMSE vs lag (mostra impacto do atraso na métrica de magnitude)
    scatter_xy(rmse, lag_avg,
               f"RMSE vs Lag (ms){label_suffix}",
               out_dir, f"scatter_rmse_vs_lag{label_suffix}.png",
               xlabel="RMSE", ylabel="Lag (ms)")

    # --------------------------------------------------------
    # 3) Distribuições de LAG e Pearson (se houver)
    # --------------------------------------------------------
    if lag_x is not None:
        hist_auto(lag_x, f"Distribuição – lag_x_ms{label_suffix}",
                  out_dir, f"hist_lag_x_ms{label_suffix}.png", bins=args.bins)
    if lag_y is not None:
        hist_auto(lag_y, f"Distribuição – lag_y_ms{label_suffix}",
                  out_dir, f"hist_lag_y_ms{label_suffix}.png", bins=args.bins)

    if p_x is not None or p_y is not None:
        fig, ax = plt.subplots(figsize=(5.2, 3.6))
        labels, data = [], []
        if p_x is not None:
            labels.append("pearson_x"); data.append(p_x.values.astype(float))
        if p_y is not None:
            labels.append("pearson_y"); data.append(p_y.values.astype(float))
        ax.boxplot(data, labels=labels, showmeans=True)
        ax.set_title(f"Correlação linear (boxplot){label_suffix}")
        ax.grid(True, ls="--", alpha=0.45)
        save_fig(fig, out_dir, f"box_pearson{label_suffix}.png")

    print("[plot] done.")

if __name__ == "__main__":
    main()

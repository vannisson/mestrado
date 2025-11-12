# plot_compare_metrics.py
# ============================================================
# Paper-ready figures from three metrics.csv files:
# final_results/{normal,delay,wrong_model}/metrics.csv
# - 3x1 histograms per metric (one subplot per scenario)
# - overlay histograms (appendix/checks)
# - compact summary table (CSV + LaTeX booktabs)
# - scatter plots: RMSE vs Lag(avg), DTW_norm vs Lag(avg)
# - compact box/violin plots com limites padronizados e N
# Author: Geo / Mestrado (UFAL)
# ============================================================

from pathlib import Path
import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

plt.ioff()  # no GUI

# ------------------------------- Utils --------------------------------
def _read_metrics(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    for c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="ignore")
    return df

def _num(series):
    return pd.to_numeric(series, errors="coerce").dropna()

def _ensure_out(out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir

def _title_metric(metric: str) -> str:
    mapping = {
        "mse": "MSE",
        "rmse": "RMSE",
        "mae": "MAE",
        "mape": "MAPE",
        "dtw_cru": "DTW (raw)",
        "dtw_norm": "DTW (normalized)",
        "frechet_xy": "Fréchet distance (XY)",
        "edr_x": "EDR (X)",
        "edr_y": "EDR (Y)",
        "pearson_x": "Pearson r (X)",
        "pearson_y": "Pearson r (Y)",
        "lag_x_ms": "Lag (X) [ms]",
        "lag_y_ms": "Lag (Y) [ms]",
        "lag_avg_ms": "Lag (avg X/Y) [ms]",
    }
    return mapping.get(metric, metric)

def _annotate_stats(ax, data: np.ndarray, fontsize=9):
    if data.size == 0:
        return
    mu = np.nanmean(data)
    med = np.nanmedian(data)
    n = data.size
    ax.legend([f"N={n}, mean={mu:.3g}, median={med:.3g}"],
              loc="upper right", frameon=True, fontsize=fontsize)

def _common_numeric_columns(dfs: dict) -> list:
    sets = []
    for df in dfs.values():
        cols = df.select_dtypes(include=[np.number]).columns.tolist()
        cols = [c for c in cols if c.lower() not in ("epoch", "timestamp")]
        sets.append(set(cols))
    common = sorted(set.intersection(*sets)) if sets else []
    return common

# ------------------------ Summary Table (CSV + LaTeX) ------------------
def _summary_stats(s: pd.Series):
    s = pd.to_numeric(s, errors="coerce").dropna().values
    if s.size == 0:
        return np.nan, np.nan, np.nan, np.nan, np.nan
    mean = np.mean(s)
    std = np.std(s, ddof=1)
    med = np.median(s)
    q1, q3 = np.percentile(s, [25, 75])
    return mean, std, med, q1, q3

def export_summary_tables(scen_data: dict, out_dir: Path, metrics: list):
    rows = []
    for scen, df in scen_data.items():
        for m in metrics:
            if m not in df.columns:
                continue
            mean, std, med, q1, q3 = _summary_stats(df[m])
            rows.append({
                "scenario": scen,
                "metric": m,
                "mean": mean, "std": std,
                "median": med, "q1": q1, "q3": q3,
                "N": pd.to_numeric(df[m], errors="coerce").dropna().size
            })
    tab = pd.DataFrame(rows)
    csv_path = out_dir / "metrics_summary_by_scenario.csv"
    tab.to_csv(csv_path, index=False)

    # LaTeX compact table (booktabs): mean±std / median[IQR]
    pivot = tab.pivot(index="scenario", columns="metric",
                      values=["mean", "std", "median", "q1", "q3", "N"])

    def fmt_cell(r, c):
        try:
            mean = pivot.loc[r, ("mean", c)]
        except KeyError:
            return "--"
        std  = pivot.loc[r, ("std", c)]
        med  = pivot.loc[r, ("median", c)]
        q1   = pivot.loc[r, ("q1", c)]
        q3   = pivot.loc[r, ("q3", c)]
        if pd.isna(mean):
            return "--"
        return f"{mean:.3g}±{std:.3g} / {med:.3g}[{q1:.3g}–{q3:.3g}]"

    scen_order = ["normal", "delay", "wrong_model"]
    cols = [c for c in metrics if (("mean", c) in pivot.columns)]
    lines = []
    lines.append("\\begin{tabular}{l" + "c"*len(cols) + "}")
    lines.append("\\toprule")
    lines.append("Scenario & " + " & ".join(_title_metric(c) for c in cols) + " \\\\")
    lines.append("\\midrule")
    label_map = {"normal": "Scenario 1", "delay": "Scenario 2", "wrong_model": "Scenario 3"}
    for scen in scen_order:
        if scen not in pivot.index:
            continue
        cells = [fmt_cell(scen, c) for c in cols]
        lines.append(label_map[scen] + " & " + " & ".join(cells) + " \\\\")
    lines.append("\\bottomrule")
    lines.append("\\end{tabular}")
    (out_dir / "metrics_summary_by_scenario.tex").write_text("\n".join(lines), encoding="utf-8")

    print(f"[table] CSV -> {csv_path}")
    print(f"[table] LaTeX -> {out_dir/'metrics_summary_by_scenario.tex'}")

# ------------------------- Plot: histograms ----------------------------
def plot_hist_3x1(metric: str, scen_data: dict, scen_titles: dict,
                  out_dir: Path, bins=30, clip_p=None, dpi=300, tight=True):
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.6), sharex=False, sharey=False)
    fig.suptitle(f"{_title_metric(metric)} — Distribution across scenarios", fontsize=12)

    for ax, key in zip(axes, ["normal", "delay", "wrong_model"]):
        if key not in scen_data or metric not in scen_data[key].columns:
            ax.set_visible(False)
            continue
        series = _num(scen_data[key][metric])
        if clip_p:
            hi = np.nanpercentile(series, clip_p)
            series = series[series <= hi]
        ax.hist(series.values, bins=bins, edgecolor="black", alpha=0.75)
        ax.set_title(scen_titles[key])
        ax.set_xlabel(_title_metric(metric))
        ax.set_ylabel("Frequency")
        ax.grid(True, ls="--", alpha=0.25)
        _annotate_stats(ax, series.values)

    _ensure_out(out_dir)
    fname = f"hist_{metric}_3x1.png" if not clip_p else f"hist_{metric}_3x1_clipped_p{int(clip_p)}.png"
    if tight:
        fig.tight_layout(rect=[0, 0.0, 1, 0.95])
        fig.savefig(out_dir / fname, dpi=dpi, bbox_inches="tight")
    else:
        fig.savefig(out_dir / fname, dpi=dpi)
    plt.close(fig)
    print(f"[plot] saved: {out_dir / fname}")

def plot_hist_overlay(metric: str, scen_data: dict, scen_titles: dict,
                      out_dir: Path, bins=30, clip_p=None, dpi=300, tight=True):
    fig, ax = plt.subplots(figsize=(6.2, 4.2))
    for key in ["normal", "delay", "wrong_model"]:
        if key not in scen_data or metric not in scen_data[key].columns:
            continue
        series = _num(scen_data[key][metric])
        if clip_p:
            hi = np.nanpercentile(series, clip_p)
            series = series[series <= hi]
        ax.hist(series.values, bins=bins, alpha=0.45, edgecolor="black",
                density=True, label=scen_titles[key])
    ax.set_title(f"{_title_metric(metric)} — Overlaid distributions")
    ax.set_xlabel(_title_metric(metric))
    ax.set_ylabel("Density")
    ax.grid(True, ls="--", alpha=0.25)
    ax.legend(frameon=True)
    _ensure_out(out_dir)
    fname = f"hist_{metric}_overlay.png" if not clip_p else f"hist_{metric}_overlay_clipped_p{int(clip_p)}.png"
    if tight:
        fig.tight_layout()
        fig.savefig(out_dir / fname, dpi=dpi, bbox_inches="tight")
    else:
        fig.savefig(out_dir / fname, dpi=dpi)
    plt.close(fig)
    print(f"[plot] saved: {out_dir / fname}")

# ------------------------- Plot: scatters & boxes ----------------------
def _avg_lag(df: pd.DataFrame):
    lx = pd.to_numeric(df.get("lag_x_ms"), errors="coerce")
    ly = pd.to_numeric(df.get("lag_y_ms"), errors="coerce")
    if lx is None and ly is None:
        return None
    if lx is not None and ly is not None:
        return pd.concat([lx, ly], axis=1).mean(axis=1)
    return lx if lx is not None else ly

def scatter_across_scenarios(scen_data: dict, x_metric: str, y_metric: str,
                             out_dir: Path, title: str, fname: str,
                             x_clip_p=None, dpi=300, tight=True):
    fig, ax = plt.subplots(figsize=(6.4, 4.4))
    colors = {"normal": "#1f77b4", "delay": "#ff7f0e", "wrong_model": "#2ca02c"}
    labels = {"normal": "Scenario 1 — Nominal Twin",
              "delay": "Scenario 2 — Command Delay",
              "wrong_model": "Scenario 3 — Perturbed Model"}
    plotted = False
    for scen, df in scen_data.items():
        if y_metric not in df.columns and y_metric != "lag_avg_ms":
            continue
        x = _avg_lag(df) if x_metric == "lag_avg_ms" else pd.to_numeric(df.get(x_metric), errors="coerce")
        y = _avg_lag(df) if y_metric == "lag_avg_ms" else pd.to_numeric(df.get(y_metric), errors="coerce")
        if x is None or y is None:
            continue
        x, y = x.dropna().astype(float), y.dropna().astype(float)
        n = min(len(x), len(y))
        if n == 0:
            continue
        if x_clip_p:
            lo, hi = np.percentile(x.iloc[:n], [100-x_clip_p, x_clip_p])
            mask = (x.iloc[:n] >= lo) & (x.iloc[:n] <= hi)
            xx, yy = x.iloc[:n][mask], y.iloc[:n][mask]
        else:
            xx, yy = x.iloc[:n], y.iloc[:n]
        ax.scatter(xx, yy, s=18, alpha=0.45, label=labels.get(scen, scen),
                   c=colors.get(scen, None))
        plotted = True
    if not plotted:
        plt.close(fig)
        return
    ax.set_title(title)
    ax.set_xlabel(_title_metric(x_metric))
    ax.set_ylabel(_title_metric(y_metric))
    ax.axvline(0.0, color="k", lw=1, ls="--", alpha=0.5)  # referência de lag=0
    ax.grid(True, ls="--", alpha=0.25)
    ax.legend(frameon=True)
    if tight:
        fig.tight_layout()
        fig.savefig(out_dir / fname, dpi=dpi, bbox_inches="tight")
    else:
        fig.savefig(out_dir / fname, dpi=dpi)
    plt.close(fig)
    print(f"[plot] saved: {out_dir / fname}")

# y-lims padrão para box/violin (podem ser ajustados por CLI)
DEFAULT_YLIMS = {
    "dtw_norm": (0.0, 0.18),
    "frechet_xy": (0.0, 0.30),
    "rmse": (0.0, 0.75),
}

def box_per_metric(metric: str, scen_data: dict, out_dir: Path, violin=False,
                   dpi=300, tight=True, set_common_ylim=True):
    labels = []
    data = []
    order = [("normal", "Scenario 1 — Nominal Twin"),
             ("delay", "Scenario 2 — Command Delay"),
             ("wrong_model", "Scenario 3 — Perturbed Model")]
    for key, lab in order:
        if key not in scen_data or metric not in scen_data[key].columns:
            continue
        s = pd.to_numeric(scen_data[key][metric], errors="coerce").dropna().values
        if s.size:
            labels.append(lab)
            data.append(s)
    if not data:
        return
    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    if violin:
        parts = ax.violinplot(data, showmeans=True, showextrema=True, showmedians=True)
        ax.set_xticks(range(1, len(labels) + 1))
        ax.set_xticklabels(labels)
    else:
        ax.boxplot(data, labels=labels, showmeans=True)

    # y-lim comum (ajuda comparação entre cenários)
    if set_common_ylim and metric in DEFAULT_YLIMS:
        ax.set_ylim(*DEFAULT_YLIMS[metric])

    # anota N acima de cada caixa
    ymax = ax.get_ylim()[1]
    for i, arr in enumerate(data, start=1):
        ax.text(i, ymax * 1.01, f"N={len(arr)}", ha="center", va="bottom", fontsize=9)

    ax.set_title(f"{_title_metric(metric)} — compact distribution")
    ax.set_ylabel(_title_metric(metric))
    ax.grid(True, ls="--", alpha=0.25)
    if tight:
        fig.tight_layout()
        fig.savefig(out_dir / (f"violin_{metric}.png" if violin else f"box_{metric}.png"),
                    dpi=dpi, bbox_inches="tight")
    else:
        fig.savefig(out_dir / (f"violin_{metric}.png" if violin else f"box_{metric}.png"),
                    dpi=dpi)
    plt.close(fig)
    print(f"[plot] saved: {out_dir / (f'violin_{metric}.png' if violin else f'box_{metric}.png')}")

# ------------------------------- Main ---------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="final_results",
                    help="Root folder containing scenario subfolders")
    ap.add_argument("--normal", default="normal/metrics.csv",
                    help="Path relative to --root for Scenario 1 (normal)")
    ap.add_argument("--delay", default="delay/metrics.csv",
                    help="Path relative to --root for Scenario 2 (delay)")
    ap.add_argument("--wrong_model", default="wrong_model/metrics.csv",
                    help="Path relative to --root for Scenario 3 (perturbed model)")
    ap.add_argument("--out_dir", default=None,
                    help="Output folder (default: <root>/figs_compare_v2)")
    ap.add_argument("--bins", type=int, default=30)
    ap.add_argument("--clip_mape_p", type=float, default=99.0,
                    help="Percentile clipping for MAPE (to curb outliers)")
    ap.add_argument("--x_clip_p", type=float, default=None,
                    help="Percentile for x-axis clipping on scatter (e.g., 99 for p1–p99)")
    ap.add_argument("--no_scatter", action="store_true",
                    help="Skip scatter plots")
    ap.add_argument("--no_boxes", action="store_true",
                    help="Skip box/violin plots")
    ap.add_argument("--violin", action="store_true",
                    help="Use violin instead of box for compact plots")
    ap.add_argument("--dpi", type=int, default=300, help="Figure DPI")
    ap.add_argument("--no_tight", action="store_true", help="Disable bbox_inches='tight'")
    args = ap.parse_args()

    root = Path(args.root)
    scen_paths = {
        "normal": root / args.normal,
        "delay": root / args.delay,
        "wrong_model": root / args.wrong_model,
    }

    scen_titles = {
        "normal": "Scenario 1 — Nominal Twin",
        "delay": "Scenario 2 — Command Delay",
        "wrong_model": "Scenario 3 — Perturbed Model",
    }

    # read data
    scen_data = {}
    for k, p in scen_paths.items():
        if p.is_file():
            df = _read_metrics(p)
            # Deriva lag médio se não existir
            if "lag_avg_ms" not in df.columns and (("lag_x_ms" in df.columns) or ("lag_y_ms" in df.columns)):
                df["lag_avg_ms"] = _avg_lag(df)
            scen_data[k] = df
        else:
            print(f"[warn] missing metrics.csv for {k}: {p}")

    if not scen_data:
        raise SystemExit("[error] No metrics found.")

    # output folder
    out_dir = Path(args.out_dir) if args.out_dir else (root / "figs_compare_v2")
    _ensure_out(out_dir)

    # common numeric metrics across scenarios
    common = _common_numeric_columns(scen_data)
    if not common:
        raise SystemExit("[error] No common numeric metrics across scenarios.")

    # --- Summary tables (CSV + LaTeX)
    export_summary_tables(scen_data, out_dir, common)

    # --- Figures: histograms
    for metric in common:
        if metric.lower() == "mape" and args.clip_mape_p:
            plot_hist_3x1(metric, scen_data, scen_titles, out_dir,
                          bins=args.bins, clip_p=args.clip_mape_p, dpi=args.dpi, tight=not args.no_tight)
            plot_hist_overlay(metric, scen_data, scen_titles, out_dir,
                              bins=args.bins, clip_p=args.clip_mape_p, dpi=args.dpi, tight=not args.no_tight)
        else:
            plot_hist_3x1(metric, scen_data, scen_titles, out_dir, bins=args.bins, dpi=args.dpi, tight=not args.no_tight)
            plot_hist_overlay(metric, scen_data, scen_titles, out_dir, bins=args.bins, dpi=args.dpi, tight=not args.no_tight)

    # --- Figures: scatters (key relationships)
    if not args.no_scatter:
        if ("rmse" in common) and (("lag_x_ms" in common) or ("lag_y_ms" in common) or ("lag_avg_ms" in common)):
            scatter_across_scenarios(
                scen_data, "lag_avg_ms", "rmse", out_dir,
                "Relationship between magnitude error and misalignment",
                "scatter_rmse_vs_lagavg.png",
                x_clip_p=args.x_clip_p, dpi=args.dpi, tight=not args.no_tight
            )
        if ("dtw_norm" in common) and (("lag_x_ms" in common) or ("lag_y_ms" in common) or ("lag_avg_ms" in common)):
            scatter_across_scenarios(
                scen_data, "lag_avg_ms", "dtw_norm", out_dir,
                "Temporal-shape similarity vs misalignment",
                "scatter_dtw_norm_vs_lagavg.png",
                x_clip_p=args.x_clip_p, dpi=args.dpi, tight=not args.no_tight
            )

    # --- Figures: box/violin para métricas core
    if not args.no_boxes:
        for metric in ["rmse", "dtw_norm", "frechet_xy"]:
            if metric in common:
                box_per_metric(metric, scen_data, out_dir,
                               violin=args.violin, dpi=args.dpi, tight=not args.no_tight,
                               set_common_ylim=True)

    print("[done] all outputs in:", out_dir)

if __name__ == "__main__":
    main()

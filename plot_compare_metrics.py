#!/usr/bin/env python3
"""
Figuras principais (versão Seaborn) para a dissertação.

Gera, a partir de final_results/{normal,delay,wrong_model}/metrics.csv:

- Histogramas 3×1:
    • RMSE
    • DTW_norm
    • Lag médio (lag_avg_ms)
    • Fréchet (XY)  [opcional: pode comentar se não quiser]

- Boxplots por cenário:
    • RMSE
    • DTW_norm
    • Fréchet (XY)

- Scatter plots:
    • RMSE        vs Lag médio
    • DTW_norm    vs Lag médio
    • RMSE        vs DTW_norm  (diagnóstico delay × modelo)
    • Fréchet XY  vs Lag médio (opcional)

Saída: fig_seaborn/
"""

from pathlib import Path
import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

sns.set_theme(style="whitegrid", context="paper", font_scale=1.2)

# ---------------------------------------------------------------------
# Utilitários
# ---------------------------------------------------------------------
TITLE_MAP = {
    "mse": "MSE",
    "rmse": "RMSE",
    "mae": "MAE",
    "mape": "MAPE",
    "dtw_cru": "DTW (raw)",
    "dtw_norm": "DTW normalizado",
    "frechet_xy": "Distância de Fréchet (XY)",
    "edr_x": "EDR (X)",
    "edr_y": "EDR (Y)",
    "lag_avg_ms": "Lag médio [ms]",
    "lag_x_ms": "Lag X [ms]",
    "lag_y_ms": "Lag Y [ms]",
}

def mt(metric: str) -> str:
    return TITLE_MAP.get(metric, metric)

def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def read_metrics(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    # tenta converter colunas numéricas
    for c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="ignore")
    return df

# ---------------------------------------------------------------------
# Lag médio
# ---------------------------------------------------------------------
def add_lag_avg(df: pd.DataFrame) -> pd.DataFrame:
    """Adiciona coluna 'lag_avg_ms' se possível (x, y ou já existente)."""
    if "lag_avg_ms" in df.columns:
        return df

    lx = df["lag_x_ms"] if "lag_x_ms" in df.columns else None
    ly = df["lag_y_ms"] if "lag_y_ms" in df.columns else None

    if lx is not None and ly is not None:
        lx = pd.to_numeric(lx, errors="coerce")
        ly = pd.to_numeric(ly, errors="coerce")
        df["lag_avg_ms"] = pd.concat([lx, ly], axis=1).mean(axis=1)
    elif lx is not None:
        df["lag_avg_ms"] = pd.to_numeric(lx, errors="coerce")
    elif ly is not None:
        df["lag_avg_ms"] = pd.to_numeric(ly, errors="coerce")

    return df

def metric_available(metric: str, scen_data: dict) -> bool:
    if metric == "lag_avg_ms":
        return any(
            ("lag_avg_ms" in df.columns)
            or ("lag_x_ms" in df.columns)
            or ("lag_y_ms" in df.columns)
            for df in scen_data.values()
        )
    return any(metric in df.columns for df in scen_data.values())

def get_global_limits(metric: str, scen_data: dict) -> tuple[float, float]:
    """Limites globais (min/max) para um dado metric, com margem."""
    values = []

    for df in scen_data.values():
        local = df.copy()
        if metric == "lag_avg_ms":
            local = add_lag_avg(local)
        if metric in local.columns:
            vals = pd.to_numeric(local[metric], errors="coerce").dropna()
            values.append(vals)

    if not values:
        return (0.0, 1.0)

    all_vals = pd.concat(values)
    vmin, vmax = all_vals.min(), all_vals.max()
    if vmin == vmax:
        return (float(vmin - 1), float(vmax + 1))

    margin = 0.05 * (vmax - vmin)
    return (float(vmin - margin), float(vmax + margin))

# ---------------------------------------------------------------------
# Gráficos
# ---------------------------------------------------------------------
def plot_hist_3x1(metric: str, scen_data: dict, scen_titles: dict, outdir: Path) -> None:
    if not metric_available(metric, scen_data):
        return

    vmin, vmax = get_global_limits(metric, scen_data)

    fig, axs = plt.subplots(1, 3, figsize=(14, 4), sharey=True)
    fig.suptitle(f"{mt(metric)} — distribuição por cenário", y=1.05)

    for ax, scen in zip(axs, ["normal", "delay", "wrong_model"]):
        df = scen_data[scen].copy()
        if metric == "lag_avg_ms":
            df = add_lag_avg(df)

        if metric not in df.columns:
            ax.set_visible(False)
            continue

        data = pd.to_numeric(df[metric], errors="coerce").dropna()
        sns.histplot(
            data,
            ax=ax,
            bins=30,
            color="#4C72B0",
            edgecolor="black",
        )
        ax.set_title(scen_titles[scen])
        ax.set_xlabel(mt(metric))
        ax.set_ylabel("Frequência")
        ax.set_xlim(vmin, vmax)

    fig.tight_layout()
    fig.savefig(outdir / f"hist3x1_{metric}.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

def plot_box(metric: str, scen_data: dict, scen_titles: dict, outdir: Path) -> None:
    if not metric_available(metric, scen_data):
        return

    frames = []
    for scen, df in scen_data.items():
        local = df.copy()
        if metric == "lag_avg_ms":
            local = add_lag_avg(local)
        if metric in local.columns:
            vals = pd.to_numeric(local[metric], errors="coerce").dropna()
            if not vals.empty:
                frames.append(
                    pd.DataFrame(
                        {
                            "value": vals,
                            "scenario": scen_titles[scen],
                        }
                    )
                )

    if not frames:
        return

    dfc = pd.concat(frames, ignore_index=True)
    vmin, vmax = dfc["value"].min(), dfc["value"].max()
    if vmin == vmax:
        vmin -= 1
        vmax += 1

    plt.figure(figsize=(7, 4))
    ax = sns.boxplot(
        data=dfc,
        x="scenario",
        y="value",
        showmeans=True,
        width=0.55,
        meanprops={
            "marker": "D",
            "markerfacecolor": "green",
            "markeredgecolor": "black",
        },
    )
    sns.stripplot(
        data=dfc,
        x="scenario",
        y="value",
        color="black",
        size=1.5,
        alpha=0.3,
    )

    ax.set_title(f"{mt(metric)} — distribuição compacta")
    ax.set_xlabel("")
    ax.set_ylabel(mt(metric))
    ax.set_ylim(vmin - 0.05 * (vmax - vmin), vmax + 0.05 * (vmax - vmin))

    plt.tight_layout()
    plt.savefig(outdir / f"box_{metric}.png", dpi=300, bbox_inches="tight")
    plt.close()

def plot_scatter(x_metric: str, y_metric: str, scen_data: dict, scen_titles: dict, outdir: Path) -> None:
    if not (metric_available(x_metric, scen_data) and metric_available(y_metric, scen_data)):
        return

    frames = []

    for scen, df in scen_data.items():
        local = df.copy()
        if x_metric == "lag_avg_ms":
            local = add_lag_avg(local)
        if y_metric == "lag_avg_ms":
            local = add_lag_avg(local)

        if (x_metric not in local.columns) or (y_metric not in local.columns):
            continue

        x = pd.to_numeric(local[x_metric], errors="coerce")
        y = pd.to_numeric(local[y_metric], errors="coerce")

        frame = pd.DataFrame(
            {
                x_metric: x,
                y_metric: y,
                "scenario": scen_titles[scen],
            }
        ).dropna()

        if not frame.empty:
            frames.append(frame)

    if not frames:
        return

    full = pd.concat(frames, ignore_index=True)

    plt.figure(figsize=(7, 4))
    sns.scatterplot(
        data=full,
        x=x_metric,
        y=y_metric,
        hue="scenario",
        alpha=0.6,
        s=35,
    )

    plt.title(f"{mt(y_metric)} vs {mt(x_metric)}")
    plt.xlabel(mt(x_metric))
    plt.ylabel(mt(y_metric))
    plt.tight_layout()
    plt.savefig(outdir / f"scatter_{y_metric}_vs_{x_metric}.png", dpi=300, bbox_inches="tight")
    plt.close()

# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------
def main() -> None:
    root = Path("final_results")
    outdir = Path("fig_seaborn")
    ensure_dir(outdir)

    scen_data = {
        "normal": read_metrics(root / "normal/metrics.csv"),
        "delay": read_metrics(root / "delay/metrics.csv"),
        "wrong_model": read_metrics(root / "wrong_model/metrics.csv"),
    }

    scen_titles = {
        "normal": "Nominal",
        "delay": "Delay",
        "wrong_model": "Modelo perturbado",
    }

    # -----------------------------------------------------------------
    # Histogramas 3×1 (apenas métricas principais)
    # -----------------------------------------------------------------
    CORE_HIST_METRICS = [
        "rmse",
        "dtw_norm",
        "lag_avg_ms",
        "frechet_xy",  # opcional: comente se não quiser
    ]

    for m in CORE_HIST_METRICS:
        plot_hist_3x1(m, scen_data, scen_titles, outdir)

    # -----------------------------------------------------------------
    # Boxplots compactos (cenários lado a lado)
    # -----------------------------------------------------------------
    CORE_BOX_METRICS = [
        "rmse",
        "dtw_norm",
        "frechet_xy",
    ]

    for m in CORE_BOX_METRICS:
        plot_box(m, scen_data, scen_titles, outdir)

    # -----------------------------------------------------------------
    # Scatter plots principais
    # -----------------------------------------------------------------
    SCATTER_PAIRS = [
        ("lag_avg_ms", "rmse"),
        ("lag_avg_ms", "dtw_norm"),
        ("rmse", "dtw_norm"),
        ("lag_avg_ms", "frechet_xy"),  # opcional
    ]

    for x_metric, y_metric in SCATTER_PAIRS:
        plot_scatter(x_metric, y_metric, scen_data, scen_titles, outdir)

    print(f"✔ Figuras principais geradas em: {outdir.absolute()}")

if __name__ == "__main__":
    main()

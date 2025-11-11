import os
import sys
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# --- Caminho base do projeto ---
sys.path.append(r"C:\Users\geova\repos\mestrado")

from validation.metrics import (
    compute_mse,
    compute_mae,
    compute_mape,
    compute_dtw,
    compute_dtw_and_path_length,
    compute_dtw_normalized,
    pearson_corr,
    discrete_frechet_distance,
    edr_distance,
    lag_ms,
)

FS_HZ = 20.0
ROOT = Path(r"C:\Users\geova\repos\mestrado")
agv_dir  = ROOT / "logs" / "experiments" / "cenario_montecarlo_20251110_190543" / "agv_logs"
twin_dir = ROOT / "logs" / "experiments" / "cenario_montecarlo_20251110_190543" / "twin_logs"
out_dir  = ROOT / "logs" / "experiments" / "cenario_montecarlo_20251110_190543" / "offline_compare"
out_dir.mkdir(parents=True, exist_ok=True)
out_csv  = out_dir / "metrics.csv"

# ---------------------------------------------------------------------------
# Carregamento e alinhamento
# ---------------------------------------------------------------------------
def load_pose_csv(csv_path: Path) -> pd.DataFrame:
    """Lê CSV de odometria (t,x,y,theta)."""
    df = pd.read_csv(csv_path)
    if "t" not in df.columns:
        raise ValueError(f"{csv_path} não contém coluna 't'.")
    return df

def interp_to_ref(ref: pd.DataFrame, test: pd.DataFrame) -> pd.DataFrame:
    """Interpola test para ter os mesmos timestamps de ref."""
    out = pd.DataFrame({"t": ref["t"]})
    for c in [c for c in test.columns if c != "t"]:
        out[c] = np.interp(ref["t"], test["t"], test[c])
    return out

# ---------------------------------------------------------------------------
# Cálculo das métricas entre dois DataFrames (ref = AGV, test = Twin)
# ---------------------------------------------------------------------------
def compute_all_metrics(ref: pd.DataFrame, test: pd.DataFrame) -> dict:
    """Calcula todas as métricas relevantes para o estudo."""
    x_r, y_r = ref["x"].to_numpy(), ref["y"].to_numpy()
    x_t, y_t = test["x"].to_numpy(), test["y"].to_numpy()

    # --- Métricas simples (1D concatenado) ---
    ref_flat = np.concatenate([x_r, y_r])
    test_flat = np.concatenate([x_t, y_t])
    mse_val  = compute_mse(ref_flat, test_flat)
    rmse_val = float(np.sqrt(mse_val))
    mae_val  = compute_mae(ref_flat, test_flat)
    mape_val = compute_mape(ref_flat, test_flat)

    # --- DTW (2D trajetória) ---
    A_xy = np.vstack([x_r, y_r]).T
    B_xy = np.vstack([x_t, y_t]).T
    dtw_cru = compute_dtw(A_xy, B_xy)
    total_cost, path_len = compute_dtw_and_path_length(A_xy, B_xy)
    dtw_norm = compute_dtw_normalized(A_xy, B_xy)

    # --- Fréchet e EDR ---
    frechet_xy = discrete_frechet_distance(A_xy, B_xy)
    edr_x = edr_distance(x_r, x_t)
    edr_y = edr_distance(y_r, y_t)

    # --- Correlação e Lag ---
    pearson_x = pearson_corr(x_r, x_t)
    pearson_y = pearson_corr(y_r, y_t)
    lag_x_ms = lag_ms(x_r, x_t, FS_HZ)
    lag_y_ms = lag_ms(y_r, y_t, FS_HZ)

    return dict(
        mse=mse_val,
        rmse=rmse_val,
        mae=mae_val,
        mape=mape_val,
        dtw_cru=dtw_cru,
        dtw_norm=dtw_norm,
        frechet_xy=frechet_xy,
        edr_x=edr_x,
        edr_y=edr_y,
        pearson_x=pearson_x,
        pearson_y=pearson_y,
        lag_x_ms=lag_x_ms,
        lag_y_ms=lag_y_ms,
    )

# ---------------------------------------------------------------------------
# Loop principal
# ---------------------------------------------------------------------------
def compute_offline(ref_dir: Path, test_dir: Path):
    ref_file = ref_dir / "odom.csv"
    test_file = test_dir / "odom.csv"
    if not ref_file.exists() or not test_file.exists():
        print(f"[compute_offline] Faltando odom.csv em {ref_dir} ou {test_dir}")
        return

    ref = load_pose_csv(ref_file)
    test = load_pose_csv(test_file)
    test_interp = interp_to_ref(ref, test)
    metrics = compute_all_metrics(ref, test_interp)

    df = pd.DataFrame([metrics])
    df.to_csv(out_csv, index=False)
    print(f"[compute_offline] Métricas salvas em: {out_csv}")

    # --- Resumo estatístico ---
    summary_path = out_dir / "summary.csv"
    df.describe(percentiles=[0.05, 0.5, 0.95]).to_csv(summary_path)
    print(f"[compute_offline] Resumo salvo em: {summary_path}")

    # --- Histogramas automáticos ---
    for col in df.columns:
        fig, ax = plt.subplots(figsize=(5, 3))
        ax.hist(df[col], bins=10, color="#56B4E9", edgecolor="black", alpha=0.7)
        ax.set_title(f"Histograma – {col}")
        ax.grid(True, ls="--", alpha=0.5)
        fig.tight_layout()
        fig.savefig(out_dir / f"hist_{col}.png", dpi=150)
        plt.close(fig)
    print(f"[compute_offline] Histogramas salvos em: {out_dir}")

# ---------------------------------------------------------------------------
if __name__ == "__main__":
    compute_offline(agv_dir, twin_dir)

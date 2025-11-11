from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

# --- CONFIGURAÇÃO (ajustada) ---
ROOT = Path(r"C:\Users\geova\repos\mestrado")
agv_csv  = ROOT / "logs" / "agv_logs"  / "odometry_pose.csv"
twin_csv = ROOT / "logs" / "twin_logs" / "odometry_pose.csv"
out_dir  = ROOT / "figs" / "pose"
out_dir.mkdir(parents=True, exist_ok=True)

# --- Verifica existência ---
for p in (agv_csv, twin_csv):
    if not p.is_file():
        print(f"[plot_pose] CSV não encontrado: {p}")
        raise SystemExit(1)

# --- LÊ OS CSVs ---
agv_df = pd.read_csv(agv_csv)
twin_df = pd.read_csv(twin_csv)

# --- CONVERTE timestamps ---
def to_datetime_safe(s):
    try:
        return pd.to_datetime(s)
    except Exception:
        if pd.api.types.is_numeric_dtype(s):
            if s.max() > 10**11:
                return pd.to_datetime(s, unit="ms")
            return pd.to_datetime(s, unit="s")
        return pd.to_datetime(range(len(s)))

agv_df['timestamp'] = to_datetime_safe(agv_df['timestamp'])
twin_df['timestamp'] = to_datetime_safe(twin_df['timestamp'])

# --- Extrai posição ---
def extract_xy(df):
    missing = {'v0','v1'} - set(df.columns)
    if missing:
        raise RuntimeError(f"[plot_pose] Faltam colunas {missing} em {list(df.columns)}")
    return df['v0'], df['v1']  # x=v0, y=v1

x_agv, y_agv = extract_xy(agv_df)
x_twin, y_twin = extract_xy(twin_df)

# --- Trajetória XY ---
plt.figure(figsize=(8, 6))
plt.plot(x_agv, y_agv, label='AGV Real', linewidth=2)
plt.plot(x_twin, y_twin, '--', label='Gêmeo Digital')
plt.xlabel("X (m)")
plt.ylabel("Y (m)")
plt.title("Trajetória XY: AGV vs Gêmeo Digital")
plt.legend(); plt.grid(True); plt.axis("equal"); plt.tight_layout()

out_xy = out_dir / "trajetoria_xy.png"
plt.savefig(out_xy, dpi=180)
print(f"[plot_pose] Figura salva: {out_xy}")
plt.show()

# --- Série temporal de X e Y ---
fig, axs = plt.subplots(2, 1, figsize=(10, 6), sharex=True)

axs[0].plot(agv_df['timestamp'], x_agv, label='AGV - X')
axs[0].plot(twin_df['timestamp'], x_twin, '--', label='Gêmeo - X')
axs[0].set_ylabel("X (m)"); axs[0].legend(); axs[0].grid(True)

axs[1].plot(agv_df['timestamp'], y_agv, label='AGV - Y')
axs[1].plot(twin_df['timestamp'], y_twin, '--', label='Gêmeo - Y')
axs[1].set_ylabel("Y (m)"); axs[1].set_xlabel("Tempo")
axs[1].legend(); axs[1].grid(True)

plt.suptitle("Série Temporal de Posição")
plt.tight_layout()

out_ts = out_dir / "series_temporais_xy.png"
plt.savefig(out_ts, dpi=180)
print(f"[plot_pose] Figura salva: {out_ts}")
plt.show()

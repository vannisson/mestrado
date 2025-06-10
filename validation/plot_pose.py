import pandas as pd
import matplotlib.pyplot as plt

# --- CONFIGURAÇÃO ---
agv_csv = "../logs/agv_logs/odometry_pose.csv"
twin_csv = "../logs/twin_logs/odometry_pose.csv"

# --- LÊ OS CSVs ---
agv_df = pd.read_csv(agv_csv)
twin_df = pd.read_csv(twin_csv)

# --- CONVERTE timestamps ---
agv_df['timestamp'] = pd.to_datetime(agv_df['timestamp'])
twin_df['timestamp'] = pd.to_datetime(twin_df['timestamp'])

# --- Extrai posição ---
def extract_xy(df):
    return df['v0'], df['v1']  # x = v0, y = v1

x_agv, y_agv = extract_xy(agv_df)
x_twin, y_twin = extract_xy(twin_df)

# --- Trajetória XY ---
plt.figure(figsize=(8, 6))
plt.plot(x_agv, y_agv, label='AGV Real', linewidth=2)
plt.plot(x_twin, y_twin, '--', label='Gêmeo Digital')
plt.xlabel("X (m)")
plt.ylabel("Y (m)")
plt.title("Trajetória XY: AGV vs Gêmeo Digital")
plt.legend()
plt.grid(True)
plt.axis("equal")
plt.tight_layout()
plt.show()

# --- Série temporal de X e Y ---
fig, axs = plt.subplots(2, 1, figsize=(10, 6), sharex=True)

axs[0].plot(agv_df['timestamp'], x_agv, label='AGV - X')
axs[0].plot(twin_df['timestamp'], x_twin, '--', label='Gêmeo - X')
axs[0].set_ylabel("X (m)")
axs[0].legend()
axs[0].grid(True)

axs[1].plot(agv_df['timestamp'], y_agv, label='AGV - Y')
axs[1].plot(twin_df['timestamp'], y_twin, '--', label='Gêmeo - Y')
axs[1].set_ylabel("Y (m)")
axs[1].set_xlabel("Tempo")
axs[1].legend()
axs[1].grid(True)

plt.suptitle("Série Temporal de Posição")
plt.tight_layout()
plt.show()

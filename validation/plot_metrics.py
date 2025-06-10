import os
import pandas as pd
import matplotlib.pyplot as plt

# --- CONFIGURAÇÃO ---
log_dir = "../logs/validation"

# --- Lista todos os arquivos CSV ---
csv_files = [f for f in os.listdir(log_dir) if f.endswith(".csv")]

# --- Para cada arquivo, plota as métricas no tempo ---
for file in csv_files:
    path = os.path.join(log_dir, file)
    df = pd.read_csv(path)

    # Verifica se contém as colunas necessárias (incluindo DTW cru e DTW médio)
    required_cols = {"timestamp", "mse", "rmse", "mae", "mape", "dtw_cru", "dtw_medio"}
    if not required_cols.issubset(df.columns):
        continue  # Pula arquivos que não são de métricas completas

    df["timestamp"] = pd.to_datetime(df["timestamp"])

    # Cria subplots por métrica (6 linhas: MSE, RMSE, MAE, MAPE, DTW_cru, DTW_medio)
    fig, axs = plt.subplots(6, 1, figsize=(10, 12), sharex=True)
    fig.suptitle(f"Métricas no tempo - {file.replace('_', '/').replace('.csv', '')}")

    axs[0].plot(df["timestamp"], df["mse"], label="MSE")
    axs[0].set_ylabel("MSE")
    axs[0].grid(True)

    axs[1].plot(df["timestamp"], df["rmse"], label="RMSE", color="tab:orange")
    axs[1].set_ylabel("RMSE")
    axs[1].grid(True)

    axs[2].plot(df["timestamp"], df["mae"], label="MAE", color="tab:green")
    axs[2].set_ylabel("MAE")
    axs[2].grid(True)

    axs[3].plot(df["timestamp"], df["mape"], label="MAPE", color="tab:red")
    axs[3].set_ylabel("MAPE (%)")
    axs[3].grid(True)

    axs[4].plot(df["timestamp"], df["dtw_cru"], label="DTW Cru", color="tab:purple")
    axs[4].set_ylabel("DTW Cru")
    axs[4].grid(True)

    axs[5].plot(df["timestamp"], df["dtw_medio"], label="DTW Médio", color="tab:brown")
    axs[5].set_ylabel("DTW Médio")
    axs[5].set_xlabel("Tempo")
    axs[5].grid(True)

    plt.tight_layout()
    plt.subplots_adjust(top=0.92)
    plt.show()

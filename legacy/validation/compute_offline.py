import os
import sys
import pandas as pd
import numpy as np

# Adiciona o caminho para o repositório “mestrado” onde está validation.metrics
sys.path.append("C:\\Users\\geova\\repos\\mestrado")

from validation.metrics import (
    compute_mse,
    compute_mae,
    compute_mape,
    compute_dtw,
    compute_dtw_and_path_length,
    compute_dtw_normalized
)

def load_series_from_csv(csv_path: str) -> np.ndarray:
    """
    Lê um CSV que contém uma série temporal (possivelmente com coluna 'timestamp' + várias colunas numéricas)
    e retorna um array 1D concatenando todas as colunas numéricas (exclui 'timestamp' se existir).
    """
    df = pd.read_csv(csv_path)
    if "timestamp" in df.columns:
        df = df.drop(columns=["timestamp"])
    return df.to_numpy(dtype=np.float32).flatten()

def compute_metrics_for_all(ref_dir: str, test_dir: str):
    """
    Para cada arquivo CSV no diretório ref_dir, encontra o arquivo de mesmo nome em test_dir,
    carrega as duas séries e imprime:
      • MSE
      • MAE
      • MAPE
      • DTW cru (custo total)
      • DTW médio (normalizado)
    """
    ref_files = {f for f in os.listdir(ref_dir) if f.endswith(".csv")}
    test_files = {f for f in os.listdir(test_dir) if f.endswith(".csv")}

    common_files = sorted(list(ref_files.intersection(test_files)))
    if not common_files:
        print("Nenhum CSV correspondente encontrado entre:\n  •", ref_dir, "\n  •", test_dir)
        return

    for filename in common_files:
        ref_path = os.path.join(ref_dir, filename)
        test_path = os.path.join(test_dir, filename)

        try:
            ref_array = load_series_from_csv(ref_path)
            test_array = load_series_from_csv(test_path)

            # Ajusta tamanho se necessário
            if ref_array.shape != test_array.shape:
                min_len = min(len(ref_array), len(test_array))
                ref_array = ref_array[:min_len]
                test_array = test_array[:min_len]

            # Cálculos de métricas
            mse_value = compute_mse(ref_array, test_array)
            mae_value = compute_mae(ref_array, test_array)
            mape_value = compute_mape(ref_array, test_array)
            dtw_cru = compute_dtw(ref_array.tolist(), test_array.tolist())
            total_cost, path_len = compute_dtw_and_path_length(ref_array.tolist(), test_array.tolist())
            dtw_medio = compute_dtw_normalized(ref_array.tolist(), test_array.tolist())

            print(f"Arquivo: '{filename}'")
            print(f"  MSE: {mse_value:.5f}")
            print(f"  MAE: {mae_value:.5f}")
            print(f"  MAPE: {mape_value:.5f}%")
            print(f"  DTW cru (total): {dtw_cru:.5f}")
            print(f"  DTW passos: {path_len}")
            print(f"  DTW médio (normalizado): {dtw_medio:.5f}")
            print()
        except Exception as e:
            print(f"[Erro] ao processar '{filename}': {e}")


if __name__ == "__main__":
    """
    Ajuste os caminhos abaixo para apontar às pastas 'agv_logs' e 'twin_logs' do seu projeto.
    """
    agv_dir = r"C:\Users\geova\repos\mestrado\logs\agv_logs"
    twin_dir = r"C:\Users\geova\repos\mestrado\logs\twin_logs"

    if not os.path.isdir(agv_dir):
        print(f"Pasta de referência (agv_logs) não encontrada: {agv_dir}")
        sys.exit(1)
    if not os.path.isdir(twin_dir):
        print(f"Pasta de teste (twin_logs) não encontrada: {twin_dir}")
        sys.exit(1)

    compute_metrics_for_all(agv_dir, twin_dir)

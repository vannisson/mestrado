import csv
import time
from pathlib import Path
import numpy as np
import pandas as pd

from controller.send_target_position import send_target_position

class ExperimentManager:
    """
    Gera um CSV de métricas por cenário, com colunas:
      epoch, mse, rmse, mae, mape, dtw_cru, dtw_medio
    """
    def __init__(
        self,
        base_target: tuple[float, float],
        noise_std: float,
        n_runs: int,
        wait_time: float,
        validation_log: str,
        metric_columns: list[str],
        scenario_csv: str,
    ):
        self.base_target     = np.array(base_target, dtype=float)
        self.noise_std       = noise_std
        self.n_runs          = n_runs
        self.wait_time       = wait_time
        self.validation_log  = Path(validation_log)
        self.metric_columns  = metric_columns
        self.scenario_csv    = Path(scenario_csv)

        # garante que a pasta existe e escreve o cabeçalho
        self.scenario_csv.parent.mkdir(parents=True, exist_ok=True)
        with open(self.scenario_csv, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["epoch"] + self.metric_columns)

    def run(self):
        for epoch in range(1, self.n_runs + 1):
            # 1) perturba o alvo e dispara o envio
            dx, dy = np.random.normal(0, self.noise_std, size=2)
            target = self.base_target + np.array([dx, dy])
            send_target_position(*target)
            print(f"> [Epoch {epoch}] Enviado x={target[0]:.3f}, y={target[1]:.3f}")

            # 2) espera o validator gerar a próxima linha no CSV de validação
            time.sleep(self.wait_time)

            # 3) lê o último registro do CSV de validação
            df   = pd.read_csv(self.validation_log)
            last = df.iloc[-1]

            # 4) grava no CSV de cenário
            row = [epoch] + [float(last[col]) for col in self.metric_columns]
            with open(self.scenario_csv, "a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(row)

            print(f"   → métricas gravadas: " +
                  ", ".join(f"{c}={row[i+1]:.3f}" for i, c in enumerate(self.metric_columns)))

import csv
import time
from pathlib import Path

import numpy as np
import pandas as pd
from pandas.errors import EmptyDataError

from controller.send_target_position import send_target_position

class ExperimentManager:
    """
    Monte Carlo: em cada época perturba o alvo, espera o validator gerar
    o CSV de validação (com header + dados), lê a última linha e grava
    em um CSV específico de cenário (epoch + métricas).
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
        self.poll_dt         = 0.2  # intervalo de retry (s)

        # prepara o CSV de cenário (header)
        self.scenario_csv.parent.mkdir(parents=True, exist_ok=True)
        with open(self.scenario_csv, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["epoch"] + self.metric_columns)

    def _wait_for_validation_df(self) -> pd.DataFrame:
        """
        Espera até que o CSV de validação tenha header + pelo menos 1 linha de dados.
        """
        deadline = time.time() + self.wait_time + 5
        while time.time() < deadline:
            try:
                df = pd.read_csv(self.validation_log)
                if df.shape[1] > 0 and len(df) > 0:
                    return df
            except (FileNotFoundError, EmptyDataError):
                pass
            time.sleep(self.poll_dt)
        raise RuntimeError(f"Timeout aguardando {self.validation_log}")

    def run(self) -> None:
        for epoch in range(1, self.n_runs + 1):
            # 1) limpa o CSV antigo de validação
            try:
                self.validation_log.unlink()
            except FileNotFoundError:
                pass

            # 2) gera ruído e envia um único set-point
            dx, dy = np.random.normal(0, self.noise_std, size=2)
            target = self.base_target + np.array([dx, dy])
            send_target_position(*target)
            print(f"> [Epoch {epoch}] Enviado x={target[0]:.3f}, y={target[1]:.3f}")

            # 3) espera o validator criar header + linha de dados
            df = self._wait_for_validation_df()
            last = df.iloc[-1]

            # 4) salva no CSV de cenário
            row = [epoch] + [float(last[col]) for col in self.metric_columns]
            with open(self.scenario_csv, "a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(row)

            metrics_str = ", ".join(
                f"{col}={row[i+1]:.3f}"
                for i, col in enumerate(self.metric_columns)
            )
            print(f"   → métricas registradas: {metrics_str}")

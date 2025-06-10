import time
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from controller.send_target_position import send_target_position

class ExperimentManager:
    """
    Gerencia um ensaio de Monte Carlo:
      1) em cada época perturba a posição alvo segundo N(0,σ²)
      2) envia via MQTT (send_target_position)
      3) aguarda a simulação + validator gerarem o CSV de métricas
      4) lê o último registro do CSV e acumula cada uma das métricas
      5) ao final, salva um histograma por métrica
    """
    def __init__(
        self,
        base_target: tuple[float, float],
        noise_std: float,
        n_runs: int,
        wait_time: float,
        metric_log: str,
        metric_columns: list[str],
    ):
        self.base_target    = np.array(base_target, dtype=float)
        self.noise_std      = noise_std
        self.n_runs         = n_runs
        self.wait_time      = wait_time
        self.metric_log     = metric_log
        self.metric_columns = metric_columns

        # dicionário: nome_da_métrica → lista de valores
        self.results = {col: [] for col in self.metric_columns}

    def run_monte_carlo(self):
        """Roda as n_runs perturbações e coleta todas as métricas do CSV."""
        # zera resultados anteriores
        self.results = {col: [] for col in self.metric_columns}

        for i in range(1, self.n_runs + 1):
            # 1) gera ruído Gaussiano centrado em zero
            dx, dy = np.random.normal(0, self.noise_std, size=2)
            target = self.base_target + np.array([dx, dy])
            send_target_position(*target)

            # 2) espera a simulação + validator gerarem a linha no CSV
            time.sleep(self.wait_time)

            # 3) abre o CSV e pega o último registro
            df   = pd.read_csv(self.metric_log)
            last = df.iloc[-1]

            # 4) coleta cada métrica
            line = []
            for col in self.metric_columns:
                val = float(last[col])
                self.results[col].append(val)
                line.append(f"{col}={val:.3f}")

            print(f"[{i}/{self.n_runs}] " + ", ".join(line))

        return self.results

    def save_all_histograms(self, out_dir: str, bins: int = 30):
        """
        Gera e salva um histograma para cada métrica em <out_dir>/<metrica>_hist.png
        """
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)

        for col, values in self.results.items():
            fig, ax = plt.subplots(figsize=(6,4))
            ax.hist(values, bins=bins, edgecolor="black")
            ax.set_title(f"Histograma de {col} ({len(values)} runs)")
            ax.set_xlabel(col)
            ax.set_ylabel("Frequência")
            ax.grid(True, linestyle="--", alpha=0.5)
            fig.tight_layout()

            file = out / f"{col}_hist.png"
            fig.savefig(file)
            plt.close(fig)
            print(f"  → {col}: salvo em {file}")

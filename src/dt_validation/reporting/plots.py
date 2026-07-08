from __future__ import annotations

import re
from pathlib import Path

import matplotlib
import numpy as np

from dt_validation.core.series import AlignedSignal

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402


def create_validation_plots(
    run_dir: Path,
    aligned_signals: dict[str, AlignedSignal],
) -> list[str]:
    plot_dir = run_dir / "plots"
    plot_dir.mkdir(exist_ok=True)
    generated: list[str] = []
    for signal, aligned in sorted(aligned_signals.items()):
        error = np.linalg.norm(aligned.reference - aligned.candidate, axis=1)
        figure, axis = plt.subplots(figsize=(8, 3.5))
        axis.plot(aligned.timestamps, error, linewidth=1.1)
        axis.set_title(f"Erro por amostra — {signal}")
        axis.set_xlabel("Tempo decorrido (s)")
        axis.set_ylabel(aligned.unit or "erro")
        axis.grid(True, alpha=0.3)
        figure.tight_layout()
        relative = f"plots/{_safe_name(signal)}_error.png"
        figure.savefig(run_dir / relative, dpi=130)
        plt.close(figure)
        generated.append(relative)

    position = aligned_signals.get("odometry.position")
    if position is not None and position.reference.shape[1] >= 2:
        figure, axis = plt.subplots(figsize=(6, 5))
        axis.plot(position.reference[:, 0], position.reference[:, 1], label="Referência")
        axis.plot(
            position.candidate[:, 0],
            position.candidate[:, 1],
            "--",
            label="Candidato",
        )
        axis.set_title("Trajetória XY")
        axis.set_xlabel("X (m)")
        axis.set_ylabel("Y (m)")
        axis.axis("equal")
        axis.grid(True, alpha=0.3)
        axis.legend()
        figure.tight_layout()
        relative = "plots/trajectory_xy.png"
        figure.savefig(run_dir / relative, dpi=130)
        plt.close(figure)
        generated.append(relative)
    return generated


def _safe_name(signal: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", signal).strip("_")


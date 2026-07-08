from __future__ import annotations

import numpy as np

from dt_validation.metrics.base import MetricError


def bootstrap_summary(
    values: list[float] | np.ndarray,
    *,
    confidence: float = 0.95,
    repetitions: int = 2_000,
    seed: int = 42,
) -> dict[str, float]:
    samples = np.asarray(values, dtype=float)
    if samples.ndim != 1 or not len(samples) or not np.all(np.isfinite(samples)):
        raise MetricError("bootstrap needs a non-empty finite one-dimensional sample")
    if not 0 < confidence < 1 or repetitions < 100:
        raise MetricError("invalid bootstrap configuration")
    generator = np.random.default_rng(seed)
    means = np.mean(generator.choice(samples, size=(repetitions, len(samples))), axis=1)
    alpha = (1.0 - confidence) / 2.0
    return {
        "mean": float(np.mean(samples)),
        "std": float(np.std(samples, ddof=1)) if len(samples) > 1 else 0.0,
        "median": float(np.median(samples)),
        "ci_low": float(np.quantile(means, alpha)),
        "ci_high": float(np.quantile(means, 1.0 - alpha)),
    }


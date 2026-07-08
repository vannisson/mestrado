from __future__ import annotations

from typing import cast

import numpy as np
from scipy.signal import correlate, correlation_lags

from dt_validation.core.series import SignalFrame
from dt_validation.metrics.base import MetricError
from dt_validation.metrics.signal import _validate_pair


def normalized_dtw(
    reference: np.ndarray,
    candidate: np.ndarray,
    *,
    window: int | float = 0.1,
    **_: object,
) -> float:
    _validate_pair(reference, candidate)
    n, m = len(reference), len(candidate)
    if isinstance(window, float):
        if not 0 < window <= 1:
            raise MetricError("float DTW window must be in (0, 1]")
        width = int(np.ceil(max(n, m) * window))
    else:
        width = int(window)
    width = max(width, abs(n - m), 1)

    costs = np.full((n + 1, m + 1), np.inf, dtype=float)
    steps = np.zeros((n + 1, m + 1), dtype=int)
    costs[0, 0] = 0.0
    for i in range(1, n + 1):
        for j in range(max(1, i - width), min(m, i + width) + 1):
            predecessors = (
                (costs[i - 1, j], steps[i - 1, j]),
                (costs[i, j - 1], steps[i, j - 1]),
                (costs[i - 1, j - 1], steps[i - 1, j - 1]),
            )
            previous_cost, previous_steps = min(predecessors, key=lambda item: item[0])
            costs[i, j] = previous_cost + np.linalg.norm(reference[i - 1] - candidate[j - 1])
            steps[i, j] = previous_steps + 1
    if not np.isfinite(costs[n, m]) or steps[n, m] == 0:
        raise MetricError("no valid DTW path inside the configured window")
    return float(costs[n, m] / steps[n, m])


def cross_correlation_lag(
    reference: np.ndarray,
    candidate: np.ndarray,
    *,
    timestamps: np.ndarray,
    max_lag_samples: int | None = None,
    **_: object,
) -> float:
    _validate_pair(reference, candidate)
    if len(reference) < 2:
        raise MetricError("lag estimation needs at least two samples")
    ref_series = _collapse(reference)
    candidate_series = _collapse(candidate)
    ref_series = ref_series - np.mean(ref_series)
    candidate_series = candidate_series - np.mean(candidate_series)
    if np.std(ref_series) == 0 or np.std(candidate_series) == 0:
        raise MetricError("lag estimation is undefined for constant signals")
    correlation = correlate(candidate_series, ref_series, mode="full", method="auto")
    lags = correlation_lags(len(candidate_series), len(ref_series), mode="full")
    if max_lag_samples is not None:
        selected = np.abs(lags) <= max_lag_samples
        correlation = correlation[selected]
        lags = lags[selected]
    lag_samples = int(lags[int(np.argmax(correlation))])
    timestep = float(np.median(np.diff(timestamps)))
    return lag_samples * timestep


def stream_statistics(frame: SignalFrame) -> dict[str, float]:
    if len(frame.timestamps) < 2:
        raise MetricError("stream statistics need at least two samples")
    intervals = np.diff(frame.timestamps)
    if np.any(intervals <= 0):
        raise MetricError("stream timestamps must be strictly increasing")
    return {
        "frequency_hz": float(1.0 / np.mean(intervals)),
        "jitter_seconds": float(np.std(intervals)),
        "duration_seconds": float(frame.timestamps[-1] - frame.timestamps[0]),
    }


def _collapse(values: np.ndarray) -> np.ndarray:
    if values.shape[1] == 1:
        return values[:, 0]
    return cast(np.ndarray, np.linalg.norm(values, axis=1))

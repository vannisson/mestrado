from __future__ import annotations

import numpy as np

from dt_validation.metrics.base import MetricError
from dt_validation.metrics.signal import _validate_pair


def iae(
    reference: np.ndarray,
    candidate: np.ndarray,
    *,
    timestamps: np.ndarray,
    **_: object,
) -> float:
    return _integral(reference, candidate, timestamps, power=1, time_weighted=False)


def ise(
    reference: np.ndarray,
    candidate: np.ndarray,
    *,
    timestamps: np.ndarray,
    **_: object,
) -> float:
    return _integral(reference, candidate, timestamps, power=2, time_weighted=False)


def itae(
    reference: np.ndarray,
    candidate: np.ndarray,
    *,
    timestamps: np.ndarray,
    **_: object,
) -> float:
    return _integral(reference, candidate, timestamps, power=1, time_weighted=True)


def _integral(
    reference: np.ndarray,
    candidate: np.ndarray,
    timestamps: np.ndarray,
    *,
    power: int,
    time_weighted: bool,
) -> float:
    _validate_pair(reference, candidate)
    if len(timestamps) != len(reference) or len(timestamps) < 2:
        raise MetricError("integral metrics need matching timestamps and at least two samples")
    elapsed = timestamps - timestamps[0]
    error = np.linalg.norm(reference - candidate, axis=1) ** power
    if time_weighted:
        error = error * elapsed
    return float(np.trapezoid(error, elapsed))


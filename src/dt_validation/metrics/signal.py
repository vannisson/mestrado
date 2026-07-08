from __future__ import annotations

from typing import cast

import numpy as np

from dt_validation.metrics.base import MetricError


def mse(reference: np.ndarray, candidate: np.ndarray, **_: object) -> float:
    error = _error(reference, candidate)
    return float(np.mean(np.square(error)))


def rmse(reference: np.ndarray, candidate: np.ndarray, **_: object) -> float:
    return float(np.sqrt(mse(reference, candidate)))


def mae(reference: np.ndarray, candidate: np.ndarray, **_: object) -> float:
    return float(np.mean(np.abs(_error(reference, candidate))))


def mape(
    reference: np.ndarray,
    candidate: np.ndarray,
    *,
    epsilon: float = 1e-6,
    **_: object,
) -> float:
    error = _error(reference, candidate)
    valid = np.abs(reference) > epsilon
    if not np.any(valid):
        raise MetricError("MAPE is undefined because every reference value is near zero")
    return float(np.mean(np.abs(error[valid] / reference[valid])) * 100.0)


def nrmse(
    reference: np.ndarray,
    candidate: np.ndarray,
    *,
    normalization: str = "range",
    epsilon: float = 1e-12,
    **_: object,
) -> float:
    value = rmse(reference, candidate)
    if normalization == "range":
        denominator = float(np.max(reference) - np.min(reference))
    elif normalization == "std":
        denominator = float(np.std(reference))
    else:
        raise MetricError(f"unsupported NRMSE normalization: {normalization}")
    if denominator <= epsilon:
        raise MetricError("NRMSE normalization denominator is zero")
    return value / denominator


def max_absolute_error(reference: np.ndarray, candidate: np.ndarray, **_: object) -> float:
    return float(np.max(np.abs(_error(reference, candidate))))


def p95_absolute_error(reference: np.ndarray, candidate: np.ndarray, **_: object) -> float:
    return float(np.percentile(np.abs(_error(reference, candidate)), 95))


def steady_state_error(
    reference: np.ndarray,
    candidate: np.ndarray,
    *,
    tail_fraction: float = 0.1,
    **_: object,
) -> float:
    _validate_pair(reference, candidate)
    if not 0 < tail_fraction <= 1:
        raise MetricError("tail_fraction must be in (0, 1]")
    count = max(1, int(np.ceil(len(reference) * tail_fraction)))
    return float(np.mean(np.linalg.norm(reference[-count:] - candidate[-count:], axis=1)))


def _error(reference: np.ndarray, candidate: np.ndarray) -> np.ndarray:
    _validate_pair(reference, candidate)
    return cast(np.ndarray, reference - candidate)


def _validate_pair(reference: np.ndarray, candidate: np.ndarray) -> None:
    if reference.shape != candidate.shape:
        raise MetricError(f"shape mismatch: {reference.shape} != {candidate.shape}")
    if not reference.size:
        raise MetricError("metric needs at least one sample")
    if not np.all(np.isfinite(reference)) or not np.all(np.isfinite(candidate)):
        raise MetricError("metric input contains non-finite values")

from __future__ import annotations

from typing import cast

import numpy as np

from dt_validation.metrics.base import MetricError
from dt_validation.metrics.signal import _validate_pair


def ate_rmse(reference: np.ndarray, candidate: np.ndarray, **_: object) -> float:
    _validate_positions(reference, candidate)
    squared_distance = np.sum(np.square(reference - candidate), axis=1)
    return float(np.sqrt(np.mean(squared_distance)))


def endpoint_error(reference: np.ndarray, candidate: np.ndarray, **_: object) -> float:
    _validate_positions(reference, candidate)
    return float(np.linalg.norm(reference[-1] - candidate[-1]))


def path_length_relative_error(
    reference: np.ndarray,
    candidate: np.ndarray,
    *,
    epsilon: float = 1e-12,
    **_: object,
) -> float:
    _validate_positions(reference, candidate)
    ref_length = _path_length(reference)
    if ref_length <= epsilon:
        raise MetricError("relative path error is undefined for a stationary reference")
    return abs(_path_length(candidate) - ref_length) / ref_length


def rpe_translation_rmse(reference: np.ndarray, candidate: np.ndarray, **_: object) -> float:
    _validate_positions(reference, candidate)
    if len(reference) < 2:
        raise MetricError("RPE needs at least two poses")
    relative_error = np.diff(reference, axis=0) - np.diff(candidate, axis=0)
    return float(np.sqrt(np.mean(np.sum(np.square(relative_error), axis=1))))


def quaternion_geodesic_mean(reference: np.ndarray, candidate: np.ndarray, **_: object) -> float:
    return float(np.mean(_quaternion_angles(reference, candidate)))


def quaternion_geodesic_p95(reference: np.ndarray, candidate: np.ndarray, **_: object) -> float:
    return float(np.percentile(_quaternion_angles(reference, candidate), 95))


def rpe_rotation_rmse(reference: np.ndarray, candidate: np.ndarray, **_: object) -> float:
    _validate_quaternions(reference, candidate)
    if len(reference) < 2:
        raise MetricError("rotational RPE needs at least two poses")
    ref_relative = _relative_quaternions(reference[:-1], reference[1:])
    candidate_relative = _relative_quaternions(candidate[:-1], candidate[1:])
    angles = _quaternion_angles(ref_relative, candidate_relative)
    return float(np.sqrt(np.mean(np.square(angles))))


def _validate_positions(reference: np.ndarray, candidate: np.ndarray) -> None:
    _validate_pair(reference, candidate)
    if reference.shape[1] not in (2, 3):
        raise MetricError("trajectory metrics require 2-D or 3-D positions")


def _validate_quaternions(reference: np.ndarray, candidate: np.ndarray) -> None:
    _validate_pair(reference, candidate)
    if reference.shape[1] != 4:
        raise MetricError("orientation metrics require quaternions [x, y, z, w]")
    if np.any(np.linalg.norm(reference, axis=1) == 0) or np.any(
        np.linalg.norm(candidate, axis=1) == 0
    ):
        raise MetricError("zero-length quaternion")


def _quaternion_angles(reference: np.ndarray, candidate: np.ndarray) -> np.ndarray:
    _validate_quaternions(reference, candidate)
    ref = reference / np.linalg.norm(reference, axis=1, keepdims=True)
    test = candidate / np.linalg.norm(candidate, axis=1, keepdims=True)
    dots = np.clip(np.abs(np.sum(ref * test, axis=1)), 0.0, 1.0)
    return cast(np.ndarray, 2.0 * np.arccos(dots))


def _relative_quaternions(first: np.ndarray, second: np.ndarray) -> np.ndarray:
    inverse = first.copy()
    inverse[:, :3] *= -1
    return _quaternion_multiply(inverse, second)


def _quaternion_multiply(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    lx, ly, lz, lw = left.T
    rx, ry, rz, rw = right.T
    return np.column_stack(
        (
            lw * rx + lx * rw + ly * rz - lz * ry,
            lw * ry - lx * rz + ly * rw + lz * rx,
            lw * rz + lx * ry - ly * rx + lz * rw,
            lw * rw - lx * rx - ly * ry - lz * rz,
        )
    )


def _path_length(positions: np.ndarray) -> float:
    return float(np.sum(np.linalg.norm(np.diff(positions, axis=0), axis=1)))

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from dt_validation.core.models import CheckStatus, MetricResult, MetricSpec
from dt_validation.core.series import AlignedSignal
from dt_validation.metrics import control, robotics, signal, temporal
from dt_validation.metrics.base import MetricError

MetricFunction = Callable[..., float]

METRIC_REGISTRY: dict[str, tuple[MetricFunction, str]] = {
    "mse": (signal.mse, "signal-unit²"),
    "rmse": (signal.rmse, "signal-unit"),
    "mae": (signal.mae, "signal-unit"),
    "mape": (signal.mape, "%"),
    "nrmse": (signal.nrmse, "ratio"),
    "max_absolute_error": (signal.max_absolute_error, "signal-unit"),
    "p95_absolute_error": (signal.p95_absolute_error, "signal-unit"),
    "steady_state_error": (signal.steady_state_error, "signal-unit"),
    "normalized_dtw": (temporal.normalized_dtw, "signal-unit"),
    "cross_correlation_lag": (temporal.cross_correlation_lag, "s"),
    "absolute_cross_correlation_lag": (temporal.absolute_cross_correlation_lag, "s"),
    "ate_rmse": (robotics.ate_rmse, "m"),
    "endpoint_error": (robotics.endpoint_error, "m"),
    "path_length_relative_error": (robotics.path_length_relative_error, "ratio"),
    "rpe_translation_rmse": (robotics.rpe_translation_rmse, "m"),
    "quaternion_geodesic_mean": (robotics.quaternion_geodesic_mean, "rad"),
    "quaternion_geodesic_p95": (robotics.quaternion_geodesic_p95, "rad"),
    "rpe_rotation_rmse": (robotics.rpe_rotation_rmse, "rad"),
    "iae": (control.iae, "signal-unit*s"),
    "ise": (control.ise, "signal-unit^2*s"),
    "itae": (control.itae, "signal-unit*s^2"),
}


def compute_metric(spec: MetricSpec, aligned: AlignedSignal) -> MetricResult:
    definition = METRIC_REGISTRY.get(spec.name)
    if definition is None:
        return MetricResult(
            name=spec.name,
            signal=spec.signal,
            status=CheckStatus.INVALID,
            sample_count=aligned.sample_count,
            details={"reason": "unknown metric"},
        )
    function, unit = definition
    parameters: dict[str, Any] = dict(spec.parameters)
    parameters["timestamps"] = aligned.timestamps
    try:
        value = function(aligned.reference, aligned.candidate, **parameters)
    except (MetricError, ValueError, FloatingPointError) as error:
        return MetricResult(
            name=spec.name,
            signal=spec.signal,
            status=CheckStatus.INVALID,
            sample_count=aligned.sample_count,
            details={"reason": str(error)},
        )
    return MetricResult(
        name=spec.name,
        signal=spec.signal,
        status=CheckStatus.PASS,
        value=value,
        unit=unit.replace("signal-unit", aligned.unit),
        sample_count=aligned.sample_count,
        details={"reference_coverage": aligned.reference_coverage},
    )

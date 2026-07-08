import math

import numpy as np
import pytest

from dt_validation.core.models import CheckStatus, MetricSpec
from dt_validation.core.series import AlignedSignal, SignalFrame
from dt_validation.metrics.control import iae, ise, itae
from dt_validation.metrics.registry import compute_metric
from dt_validation.metrics.robotics import (
    ate_rmse,
    quaternion_geodesic_mean,
    rpe_translation_rmse,
)
from dt_validation.metrics.signal import mae, mse, rmse
from dt_validation.metrics.statistics import bootstrap_summary
from dt_validation.metrics.temporal import (
    absolute_cross_correlation_lag,
    cross_correlation_lag,
    normalized_dtw,
    stream_statistics,
)


def test_pointwise_metrics_have_known_values() -> None:
    reference = np.array([[0.0], [2.0]])
    candidate = np.array([[0.0], [0.0]])

    assert mse(reference, candidate) == 2.0
    assert rmse(reference, candidate) == math.sqrt(2.0)
    assert mae(reference, candidate) == 1.0


def test_dtw_is_zero_for_identical_vector_series() -> None:
    values = np.array([[0.0, 1.0], [1.0, 2.0], [2.0, 3.0]])
    assert normalized_dtw(values, values, window=1) == 0.0


def test_robotics_metrics_use_geometry() -> None:
    reference = np.array([[0.0, 0.0], [1.0, 0.0], [2.0, 0.0]])
    candidate = np.array([[0.0, 0.0], [1.0, 0.0], [3.0, 0.0]])

    assert ate_rmse(reference, candidate) == pytest.approx(1 / math.sqrt(3))
    assert rpe_translation_rmse(reference, candidate) == pytest.approx(1 / math.sqrt(2))


def test_quaternion_metric_handles_double_cover() -> None:
    identity = np.array([[0.0, 0.0, 0.0, 1.0]])
    negative_identity = -identity
    quarter_turn = np.array([[0.0, 0.0, math.sin(math.pi / 4), math.cos(math.pi / 4)]])

    assert quaternion_geodesic_mean(identity, negative_identity) == 0.0
    assert quaternion_geodesic_mean(identity, quarter_turn) == pytest.approx(math.pi / 2)


def test_mape_is_explicitly_invalid_near_zero() -> None:
    aligned = AlignedSignal(
        signal="speed",
        timestamps=np.array([0.0, 1.0]),
        reference=np.zeros((2, 1)),
        candidate=np.ones((2, 1)),
        unit="m/s",
        reference_total=2,
        candidate_total=2,
    )
    result = compute_metric(MetricSpec(name="mape", signal="speed"), aligned)

    assert result.status == CheckStatus.INVALID
    assert "near zero" in result.details["reason"]


def test_bootstrap_is_reproducible() -> None:
    first = bootstrap_summary([1.0, 2.0, 3.0], repetitions=200, seed=7)
    second = bootstrap_summary([1.0, 2.0, 3.0], repetitions=200, seed=7)
    assert first == second


def test_integral_control_metrics_use_elapsed_time() -> None:
    reference = np.zeros((3, 1))
    candidate = np.ones((3, 1))
    timestamps = np.array([10.0, 11.0, 12.0])

    assert iae(reference, candidate, timestamps=timestamps) == pytest.approx(2.0)
    assert ise(reference, candidate, timestamps=timestamps) == pytest.approx(2.0)
    assert itae(reference, candidate, timestamps=timestamps) == pytest.approx(2.0)


def test_lag_and_stream_statistics_are_explicit() -> None:
    reference = np.array([[0.0], [1.0], [0.0], [0.0], [0.0]])
    candidate = np.array([[0.0], [0.0], [1.0], [0.0], [0.0]])
    timestamps = np.arange(5, dtype=float) * 0.1
    frame = SignalFrame("pulse", timestamps, reference)

    assert cross_correlation_lag(
        reference,
        candidate,
        timestamps=timestamps,
    ) == pytest.approx(0.1)
    assert absolute_cross_correlation_lag(
        reference,
        candidate,
        timestamps=timestamps,
    ) == pytest.approx(0.1)
    assert stream_statistics(frame)["frequency_hz"] == pytest.approx(10.0)

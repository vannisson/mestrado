import numpy as np

from dt_validation.core.alignment import align_nearest
from dt_validation.core.series import SignalFrame


def test_elapsed_alignment_ignores_clock_origin() -> None:
    reference = SignalFrame("speed", np.array([100.0, 100.1, 100.2]), np.array([1, 2, 3]))
    candidate = SignalFrame("speed", np.array([900.0, 900.1, 900.2]), np.array([1, 2, 3]))

    aligned = align_nearest(
        reference,
        candidate,
        tolerance_seconds=0.01,
        time_basis="elapsed",
    )

    assert aligned.sample_count == 3
    np.testing.assert_allclose(aligned.reference, aligned.candidate)
    assert aligned.reference_coverage == 1.0


def test_absolute_alignment_rejects_unrelated_clocks() -> None:
    reference = SignalFrame("speed", np.array([100.0, 100.1]), np.array([1, 2]))
    candidate = SignalFrame("speed", np.array([900.0, 900.1]), np.array([1, 2]))

    try:
        align_nearest(reference, candidate, tolerance_seconds=0.01, time_basis="absolute")
    except ValueError as error:
        assert "no samples aligned" in str(error)
    else:
        raise AssertionError("absolute alignment should have failed")


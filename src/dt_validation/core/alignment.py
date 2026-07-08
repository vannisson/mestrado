from __future__ import annotations

import numpy as np

from dt_validation.core.series import AlignedSignal, SignalFrame


def align_nearest(
    reference: SignalFrame,
    candidate: SignalFrame,
    *,
    tolerance_seconds: float,
    time_basis: str = "elapsed",
) -> AlignedSignal:
    if reference.signal != candidate.signal:
        raise ValueError("cannot align different signals")
    if reference.values.shape[1] != candidate.values.shape[1]:
        raise ValueError(
            f"signal dimension mismatch: {reference.values.shape[1]} != "
            f"{candidate.values.shape[1]}"
        )
    _validate_timestamps(reference.timestamps, "reference")
    _validate_timestamps(candidate.timestamps, "candidate")

    ref_time = reference.timestamps.copy()
    candidate_time = candidate.timestamps.copy()
    if time_basis == "elapsed":
        if len(ref_time):
            ref_time -= ref_time[0]
        if len(candidate_time):
            candidate_time -= candidate_time[0]
    elif time_basis != "absolute":
        raise ValueError(f"unsupported time basis: {time_basis}")

    matched_ref: list[int] = []
    matched_candidate: list[int] = []
    for reference_index, timestamp in enumerate(ref_time):
        insertion = int(np.searchsorted(candidate_time, timestamp))
        choices = [
            index for index in (insertion - 1, insertion) if 0 <= index < len(candidate_time)
        ]
        if not choices:
            continue
        candidate_index = min(choices, key=lambda index: abs(candidate_time[index] - timestamp))
        if abs(candidate_time[candidate_index] - timestamp) <= tolerance_seconds:
            matched_ref.append(reference_index)
            matched_candidate.append(candidate_index)

    if not matched_ref:
        raise ValueError(f"no samples aligned for signal {reference.signal}")
    return AlignedSignal(
        signal=reference.signal,
        timestamps=ref_time[np.asarray(matched_ref)],
        reference=reference.values[np.asarray(matched_ref)],
        candidate=candidate.values[np.asarray(matched_candidate)],
        unit=reference.unit,
        reference_total=len(reference.timestamps),
        candidate_total=len(candidate.timestamps),
    )


def _validate_timestamps(timestamps: np.ndarray, participant: str) -> None:
    if not len(timestamps):
        raise ValueError(f"{participant} has no samples")
    if not np.all(np.isfinite(timestamps)):
        raise ValueError(f"{participant} timestamps contain non-finite values")
    if np.any(np.diff(timestamps) < 0):
        raise ValueError(f"{participant} timestamps are not monotonic")

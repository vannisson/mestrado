from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class SignalFrame:
    signal: str
    timestamps: np.ndarray
    values: np.ndarray
    unit: str = ""

    def __post_init__(self) -> None:
        timestamps = np.asarray(self.timestamps, dtype=float)
        values = np.asarray(self.values, dtype=float)
        if values.ndim == 1:
            values = values[:, None]
        if timestamps.ndim != 1 or values.ndim != 2:
            raise ValueError("timestamps must be 1-D and values must be 2-D")
        if len(timestamps) != len(values):
            raise ValueError("timestamps and values must have the same length")
        object.__setattr__(self, "timestamps", timestamps)
        object.__setattr__(self, "values", values)


@dataclass(frozen=True, slots=True)
class AlignedSignal:
    signal: str
    timestamps: np.ndarray
    reference: np.ndarray
    candidate: np.ndarray
    unit: str
    reference_total: int
    candidate_total: int

    @property
    def sample_count(self) -> int:
        return len(self.timestamps)

    @property
    def reference_coverage(self) -> float:
        return self.sample_count / self.reference_total if self.reference_total else 0.0


@dataclass(frozen=True, slots=True)
class AlignmentFailure:
    signal: str
    reason: str


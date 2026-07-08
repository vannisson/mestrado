from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import numpy as np
import pandas as pd

from dt_validation.adapters.base import AdapterCapabilities, ParticipantAdapter
from dt_validation.core.models import Command, Observation, Scenario
from dt_validation.core.series import SignalFrame

_FILE_SIGNALS: dict[str, tuple[str, slice | None, str]] = {
    "imu_linearVelocity": ("imu.linear_velocity", None, "m/s"),
    "imu_angularVelocity": ("imu.angular_velocity", None, "rad/s"),
    "odometry_wheel_vel": ("odometry.wheel_velocity", None, "rad/s"),
    "sensor_ranges": ("lidar.ranges", None, "m"),
}


class CsvReplayAdapter(ParticipantAdapter):
    def __init__(self, participant: str, directory: str | Path, run_id: str) -> None:
        self.participant = participant
        self.directory = Path(directory)
        self.run_id = run_id
        self.frames: dict[str, SignalFrame] = {}
        self._observations: list[Observation] = []

    @property
    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            resettable=True,
            controllable=False,
            stepped=False,
            provides_source_time=True,
        )

    async def prepare(self, scenario: Scenario) -> None:
        del scenario
        self.load()

    async def start(self) -> None:
        return None

    async def apply_command(self, command: Command) -> None:
        del command
        raise RuntimeError("CSV replay adapters do not accept commands")

    async def observations(self) -> AsyncIterator[Observation]:
        for observation in self._observations:
            yield observation

    async def step(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    def load(self) -> dict[str, SignalFrame]:
        if not self.directory.is_dir():
            raise FileNotFoundError(f"replay directory not found: {self.directory}")

        self.frames = {}
        self._observations = []
        for path in sorted(self.directory.glob("*.csv")):
            for signal, values, unit in _load_csv_signals(path):
                frame = SignalFrame(
                    signal=signal,
                    timestamps=values["timestamps"],
                    values=values["values"],
                    unit=unit,
                )
                self.frames[signal] = frame
                self._observations.extend(
                    Observation(
                        run_id=self.run_id,
                        participant=self.participant,
                        signal=signal,
                        source_timestamp=float(timestamp),
                        sequence=sequence,
                        values=row.astype(float).tolist(),
                        unit=unit,
                    )
                    for sequence, (timestamp, row) in enumerate(
                        zip(frame.timestamps, frame.values, strict=True)
                    )
                )
        if not self.frames:
            raise ValueError(f"no supported CSV logs found in {self.directory}")
        return self.frames

    @property
    def all_observations(self) -> list[Observation]:
        return list(self._observations)


def _load_csv_signals(
    path: Path,
) -> list[tuple[str, dict[str, np.ndarray], str]]:
    frame = pd.read_csv(path)
    if "timestamp" not in frame.columns:
        return []
    value_columns = [column for column in frame.columns if column != "timestamp"]
    if not value_columns:
        return []

    timestamps = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
    numeric = frame[value_columns].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
    valid_timestamp = timestamps.notna().to_numpy()
    epoch_seconds = timestamps.astype("int64").to_numpy(dtype=float) / 1_000_000_000
    epoch_seconds = epoch_seconds[valid_timestamp]
    numeric = numeric[valid_timestamp]

    stem = path.stem
    if stem == "odometry_pose" and numeric.shape[1] >= 7:
        return [
            ("odometry.pose", _arrays(epoch_seconds, numeric[:, :7]), "mixed"),
            ("odometry.position", _arrays(epoch_seconds, numeric[:, :3]), "m"),
            ("odometry.orientation", _arrays(epoch_seconds, numeric[:, 3:7]), "quaternion"),
        ]
    definition = _FILE_SIGNALS.get(stem)
    if definition is None:
        return []
    signal, value_slice, unit = definition
    selected = numeric if value_slice is None else numeric[:, value_slice]
    return [(signal, _arrays(epoch_seconds, selected), unit)]


def _arrays(timestamps: np.ndarray, values: np.ndarray) -> dict[str, np.ndarray]:
    return {"timestamps": timestamps, "values": values}


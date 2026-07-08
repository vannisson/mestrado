from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence
from pathlib import Path
from typing import Any, cast

import numpy as np

from dt_validation.adapters.base import AdapterCapabilities, ParticipantAdapter
from dt_validation.adapters.csv_replay import CsvReplayAdapter
from dt_validation.core.models import Command, Observation, Scenario
from dt_validation.core.series import SignalFrame


class SyntheticReplayAdapter(ParticipantAdapter):
    """Build deterministic synthetic participants from an existing CSV replay."""

    def __init__(
        self,
        participant: str,
        directory: str | Path,
        run_id: str,
        metadata: Mapping[str, Any],
    ) -> None:
        self.participant = participant
        self.directory = Path(directory)
        self.run_id = run_id
        self.metadata = metadata
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
        raise RuntimeError("synthetic replay adapters do not accept commands")

    async def observations(self) -> AsyncIterator[Observation]:
        for observation in self._observations:
            yield observation

    async def step(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    def load(self) -> dict[str, SignalFrame]:
        seed = _as_int(self.metadata.get("seed"), default=42)
        rng = np.random.default_rng(seed)
        source = CsvReplayAdapter(self.participant, self.directory, self.run_id)
        frames = {
            signal: _copy_frame(frame)
            for signal, frame in source.load().items()
        }

        for transformation in _transformations(self.metadata):
            frames = _apply_transformation(frames, transformation, rng)

        self.frames = frames
        self._observations = _observations_from_frames(
            self.run_id,
            self.participant,
            frames,
        )
        return self.frames

    @property
    def all_observations(self) -> list[Observation]:
        return list(self._observations)


def _apply_transformation(
    frames: dict[str, SignalFrame],
    transformation: Mapping[str, Any],
    rng: np.random.Generator,
) -> dict[str, SignalFrame]:
    kind = str(transformation.get("type", "identity"))
    if kind == "identity":
        return frames
    return {
        signal: _transform_frame(frame, transformation, rng)
        if _selected(signal, transformation)
        else frame
        for signal, frame in frames.items()
    }


def _transform_frame(
    frame: SignalFrame,
    transformation: Mapping[str, Any],
    rng: np.random.Generator,
) -> SignalFrame:
    kind = str(transformation.get("type", "identity"))
    if kind == "noise":
        return _add_noise(frame, transformation, rng)
    if kind == "delay":
        return _delay_values(frame, transformation)
    if kind == "drift":
        return _add_drift(frame, transformation)
    if kind == "dropout":
        return _drop_samples(frame, transformation, rng)
    raise ValueError(f"unsupported synthetic transformation: {kind}")


def _add_noise(
    frame: SignalFrame,
    transformation: Mapping[str, Any],
    rng: np.random.Generator,
) -> SignalFrame:
    std = _signal_float(
        transformation.get("std_by_signal"),
        frame.signal,
        fallback=_as_float(transformation.get("std"), default=0.0),
    )
    if std <= 0:
        return frame
    values = frame.values + rng.normal(0.0, std, size=frame.values.shape)
    return _with_values(frame, _normalize_if_quaternion(frame.signal, values))


def _delay_values(frame: SignalFrame, transformation: Mapping[str, Any]) -> SignalFrame:
    seconds = _as_float(transformation.get("seconds"), default=0.0)
    if seconds == 0:
        return frame
    elapsed = frame.timestamps - frame.timestamps[0]
    query = elapsed - seconds
    delayed = np.column_stack(
        [
            np.interp(query, elapsed, frame.values[:, dimension])
            for dimension in range(frame.values.shape[1])
        ]
    )
    return _with_values(frame, _normalize_if_quaternion(frame.signal, delayed))


def _add_drift(frame: SignalFrame, transformation: Mapping[str, Any]) -> SignalFrame:
    offset = _signal_vector(
        transformation.get("final_offset_by_signal"),
        frame.signal,
        dimensions=frame.values.shape[1],
        fallback=transformation.get("final_offset"),
    )
    if np.allclose(offset, 0.0):
        return frame
    ramp = np.linspace(0.0, 1.0, len(frame.values), dtype=float)[:, None]
    values = frame.values + ramp * offset[None, :]
    return _with_values(frame, _normalize_if_quaternion(frame.signal, values))


def _drop_samples(
    frame: SignalFrame,
    transformation: Mapping[str, Any],
    rng: np.random.Generator,
) -> SignalFrame:
    keep_every = _as_int(transformation.get("keep_every"), default=0)
    if keep_every > 1:
        mask = np.zeros(len(frame.timestamps), dtype=bool)
        mask[::keep_every] = True
        mask[-1] = True
    else:
        dropout_fraction = _as_float(transformation.get("fraction"), default=0.0)
        if not 0.0 <= dropout_fraction < 1.0:
            raise ValueError("dropout fraction must be in [0, 1)")
        mask = rng.random(len(frame.timestamps)) >= dropout_fraction
        mask[0] = True
        mask[-1] = True
    return SignalFrame(
        signal=frame.signal,
        timestamps=frame.timestamps[mask],
        values=frame.values[mask],
        unit=frame.unit,
    )


def _transformations(metadata: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    raw = metadata.get("transformations")
    if raw is None:
        mode = str(metadata.get("mode", "identity"))
        if mode == "identity":
            return [{"type": "identity"}]
        transformation = dict(metadata)
        transformation["type"] = mode
        return [transformation]
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        raise ValueError("synthetic transformations must be a list")
    transformations: list[Mapping[str, Any]] = []
    for item in raw:
        if not isinstance(item, Mapping):
            raise ValueError("each synthetic transformation must be a mapping")
        transformations.append(cast(Mapping[str, Any], item))
    return transformations


def _selected(signal: str, transformation: Mapping[str, Any]) -> bool:
    raw = transformation.get("signals")
    if raw is None:
        return True
    return signal in _string_list(raw)


def _string_list(raw: Any) -> list[str]:
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        raise ValueError("signals must be a list of strings")
    return [str(value) for value in raw]


def _signal_float(raw: Any, signal: str, *, fallback: float) -> float:
    if raw is None:
        return fallback
    if not isinstance(raw, Mapping):
        raise ValueError("per-signal numeric metadata must be a mapping")
    return _as_float(raw.get(signal), default=fallback)


def _signal_vector(
    raw: Any,
    signal: str,
    *,
    dimensions: int,
    fallback: Any,
) -> np.ndarray:
    selected = fallback
    if raw is not None:
        if not isinstance(raw, Mapping):
            raise ValueError("per-signal vector metadata must be a mapping")
        selected = raw.get(signal, fallback)
    return _as_vector(selected, dimensions=dimensions)


def _as_float(raw: Any, *, default: float) -> float:
    return default if raw is None else float(raw)


def _as_int(raw: Any, *, default: int) -> int:
    return default if raw is None else int(raw)


def _as_vector(raw: Any, *, dimensions: int) -> np.ndarray:
    if raw is None:
        return np.zeros(dimensions, dtype=float)
    if isinstance(raw, int | float):
        return np.full(dimensions, float(raw), dtype=float)
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        raise ValueError("vector metadata must be a number or a list")
    values = np.asarray([float(value) for value in raw], dtype=float)
    if len(values) != dimensions:
        raise ValueError(f"vector metadata has {len(values)} dimensions, expected {dimensions}")
    return values


def _copy_frame(frame: SignalFrame) -> SignalFrame:
    return SignalFrame(
        signal=frame.signal,
        timestamps=frame.timestamps.copy(),
        values=frame.values.copy(),
        unit=frame.unit,
    )


def _with_values(frame: SignalFrame, values: np.ndarray) -> SignalFrame:
    return SignalFrame(
        signal=frame.signal,
        timestamps=frame.timestamps.copy(),
        values=values,
        unit=frame.unit,
    )


def _normalize_if_quaternion(signal: str, values: np.ndarray) -> np.ndarray:
    if "orientation" not in signal or values.shape[1] != 4:
        return values
    norms = np.linalg.norm(values, axis=1)
    norms = np.where(norms == 0.0, 1.0, norms)
    return values / norms[:, None]


def _observations_from_frames(
    run_id: str,
    participant: str,
    frames: Mapping[str, SignalFrame],
) -> list[Observation]:
    observations: list[Observation] = []
    for frame in frames.values():
        observations.extend(
            Observation(
                run_id=run_id,
                participant=participant,
                signal=frame.signal,
                source_timestamp=float(timestamp),
                sequence=sequence,
                values=row.astype(float).tolist(),
                unit=frame.unit,
            )
            for sequence, (timestamp, row) in enumerate(
                zip(frame.timestamps, frame.values, strict=True)
            )
        )
    return observations

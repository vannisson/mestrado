from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass

from dt_validation.core.models import Command, Observation, Scenario


@dataclass(frozen=True, slots=True)
class AdapterCapabilities:
    resettable: bool
    controllable: bool
    stepped: bool
    provides_source_time: bool


class ParticipantAdapter(ABC):
    """Transport-neutral contract implemented by simulators, replays and robots."""

    @property
    @abstractmethod
    def capabilities(self) -> AdapterCapabilities: ...

    @abstractmethod
    async def prepare(self, scenario: Scenario) -> None: ...

    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def apply_command(self, command: Command) -> None: ...

    @abstractmethod
    def observations(self) -> AsyncIterator[Observation]: ...

    @abstractmethod
    async def step(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...


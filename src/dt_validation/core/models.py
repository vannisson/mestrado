from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CheckStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    INVALID = "INVALID"
    SKIPPED = "SKIPPED"


class RequirementKind(StrEnum):
    VERIFICATION = "verification"
    VALIDATION = "validation"


class ReferenceKind(StrEnum):
    SIMULATED = "simulated"
    PHYSICAL = "physical"


class Observation(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str
    participant: str
    signal: str
    source_timestamp: float
    received_timestamp: float | None = None
    sequence: int = Field(ge=0)
    values: list[float]
    unit: str = ""
    frame_id: str = ""


class Command(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Literal["target_position", "twist", "wheel_velocity"]
    timestamp: float
    values: list[float]
    unit: str = ""


class Scenario(BaseModel):
    name: str
    duration_seconds: float = Field(gt=0)
    timestep_seconds: float = Field(gt=0)
    commands: list[Command] = Field(default_factory=list)


class ParticipantSpec(BaseModel):
    name: str
    role: Literal["reference", "candidate"]
    adapter: str
    data_path: Path | None = None
    reference_kind: ReferenceKind | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SignalSpec(BaseModel):
    name: str
    unit: str = ""
    frame_id: str = ""
    dimensions: int | None = Field(default=None, gt=0)


class MetricSpec(BaseModel):
    name: str
    signal: str
    parameters: dict[str, float | int | str] = Field(default_factory=dict)


class Requirement(BaseModel):
    id: str
    kind: RequirementKind
    statement: str
    critical: bool = True
    metric: str | None = None
    signal: str | None = None
    check: str | None = None
    operator: Literal["le", "lt", "ge", "gt", "eq"] | None = None
    threshold: float | None = None
    unit: str = ""
    rationale: str = ""

    @model_validator(mode="after")
    def validate_evidence_reference(self) -> Requirement:
        metric_requirement = self.metric is not None or self.signal is not None
        if metric_requirement and not all(
            value is not None
            for value in (self.metric, self.signal, self.operator, self.threshold)
        ):
            raise ValueError("metric requirements need metric, signal, operator and threshold")
        if not metric_requirement and self.check is None:
            raise ValueError("requirement needs either metric evidence or a check")
        return self


class AlignmentSpec(BaseModel):
    time_basis: Literal["elapsed", "absolute"] = "elapsed"
    tolerance_seconds: float = Field(default=0.05, gt=0)


class ContextOfUse(BaseModel):
    purpose: str
    question: str
    operational_envelope: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class ExperimentConfig(BaseModel):
    name: str
    context_of_use: ContextOfUse
    reference: ParticipantSpec
    candidate: ParticipantSpec
    alignment: AlignmentSpec = Field(default_factory=AlignmentSpec)
    signals: list[SignalSpec] = Field(default_factory=list)
    metrics: list[MetricSpec]
    requirements: list[Requirement]
    output_dir: Path = Path("artifacts")
    seed: int = 42
    expected_status: CheckStatus | None = None

    @model_validator(mode="after")
    def validate_roles_and_ids(self) -> ExperimentConfig:
        if self.reference.role != "reference" or self.candidate.role != "candidate":
            raise ValueError(
                "reference and candidate roles must match their configuration sections"
            )
        if self.reference.reference_kind is None:
            raise ValueError("reference participant must declare reference_kind")
        ids = [requirement.id for requirement in self.requirements]
        if len(ids) != len(set(ids)):
            raise ValueError("requirement ids must be unique")
        return self


class MetricResult(BaseModel):
    name: str
    signal: str
    status: CheckStatus
    value: float | None = None
    unit: str = ""
    sample_count: int = 0
    details: dict[str, Any] = Field(default_factory=dict)


class CheckResult(BaseModel):
    id: str
    kind: RequirementKind
    status: CheckStatus
    critical: bool
    summary: str
    requirement_id: str | None = None
    evidence: list[str] = Field(default_factory=list)


class Evidence(BaseModel):
    id: str
    category: str
    description: str
    artifact: str | None = None


class RunManifest(BaseModel):
    framework_version: str
    run_id: str
    experiment: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    reference_kind: ReferenceKind
    evidence_class: Literal["simulation-to-simulation", "physical-validation"]
    git_sha: str = "unknown"
    git_dirty: bool = False
    config_sha256: str
    lock_sha256: str | None = None
    seed: int
    platform: str
    python_version: str
    metadata: dict[str, Any] = Field(default_factory=dict)

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from dt_validation.core.models import (
    CheckResult,
    CheckStatus,
    Evidence,
    ExperimentConfig,
    MetricResult,
    Requirement,
    RequirementKind,
)
from dt_validation.core.series import AlignedSignal, SignalFrame


@dataclass(frozen=True, slots=True)
class VVAssessment:
    status: CheckStatus
    coverage: float
    checks: list[CheckResult]
    evidence: list[Evidence]


def evaluate_vv(
    config: ExperimentConfig,
    reference_frames: dict[str, SignalFrame],
    candidate_frames: dict[str, SignalFrame],
    aligned: dict[str, AlignedSignal],
    metric_results: list[MetricResult],
    alignment_failures: dict[str, str],
) -> VVAssessment:
    builtins = _builtin_checks(
        config,
        reference_frames,
        candidate_frames,
        aligned,
        alignment_failures,
    )
    checks = list(builtins.values())
    metric_index = {(result.name, result.signal): result for result in metric_results}
    for requirement in config.requirements:
        checks.append(_evaluate_requirement(requirement, builtins, metric_index))

    applicable = [check for check in checks if check.status != CheckStatus.SKIPPED]
    coverage = len(applicable) / len(checks) if checks else 0.0
    critical = [check for check in checks if check.critical]
    if any(check.status == CheckStatus.FAIL for check in critical):
        status = CheckStatus.FAIL
    elif any(check.status == CheckStatus.INVALID for check in critical):
        status = CheckStatus.INVALID
    elif not checks:
        status = CheckStatus.INVALID
    else:
        status = CheckStatus.PASS

    evidence = [
        Evidence(
            id="EV-DATA-001",
            category="data",
            description="Raw participant observations used by the replay",
            artifact="observations.parquet",
        ),
        Evidence(
            id="EV-METRIC-001",
            category="validation",
            description="Computed quantitative similarity metrics",
            artifact="metrics.json",
        ),
        Evidence(
            id="EV-TRACE-001",
            category="traceability",
            description="Requirements linked to checks and metric evidence",
            artifact="traceability.csv",
        ),
    ]
    return VVAssessment(status=status, coverage=coverage, checks=checks, evidence=evidence)


def _builtin_checks(
    config: ExperimentConfig,
    reference_frames: dict[str, SignalFrame],
    candidate_frames: dict[str, SignalFrame],
    aligned: dict[str, AlignedSignal],
    failures: dict[str, str],
) -> dict[str, CheckResult]:
    common = set(reference_frames) & set(candidate_frames)
    configuration = CheckResult(
        id="VER-CONFIG",
        kind=RequirementKind.VERIFICATION,
        status=CheckStatus.PASS,
        critical=True,
        summary="Configuration schema, participant roles and requirement identifiers are valid",
        evidence=["experiment YAML"],
    )

    bad_frames = [
        f"{participant}:{signal}"
        for participant, frames in (
            ("reference", reference_frames),
            ("candidate", candidate_frames),
        )
        for signal, frame in frames.items()
        if not _valid_frame(frame)
    ]
    data_status = CheckStatus.PASS if common and not bad_frames else CheckStatus.INVALID
    data_summary = (
        f"{len(common)} common signals contain finite, monotonic observations"
        if data_status == CheckStatus.PASS
        else f"Invalid or unavailable observations: {', '.join(bad_frames) or 'no common signals'}"
    )
    data_quality = CheckResult(
        id="VER-DATA",
        kind=RequirementKind.VERIFICATION,
        status=data_status,
        critical=True,
        summary=data_summary,
        evidence=["observations.parquet"],
    )

    low_coverage = [
        signal for signal, pair in aligned.items() if pair.reference_coverage < 0.8
    ]
    if failures or low_coverage:
        alignment_status = CheckStatus.FAIL
        details = [*failures, *(f"{signal}: coverage < 80%" for signal in low_coverage)]
        alignment_summary = "Alignment problems: " + ", ".join(details)
    elif aligned:
        alignment_status = CheckStatus.PASS
        alignment_summary = f"{len(aligned)} signals aligned within the configured tolerance"
    else:
        alignment_status = CheckStatus.INVALID
        alignment_summary = "No signals could be aligned"
    alignment = CheckResult(
        id="VER-ALIGN",
        kind=RequirementKind.VERIFICATION,
        status=alignment_status,
        critical=True,
        summary=alignment_summary,
        evidence=["manifest.json", "observations.parquet"],
    )

    reproducibility = CheckResult(
        id="VER-REPRO",
        kind=RequirementKind.VERIFICATION,
        status=CheckStatus.PASS,
        critical=True,
        summary=f"Seed {config.seed}, configuration hash and dependency lock are recorded",
        evidence=["manifest.json"],
    )
    scope = CheckResult(
        id="VAL-SCOPE",
        kind=RequirementKind.VALIDATION,
        status=CheckStatus.PASS,
        critical=False,
        summary=(
            "Evidence is limited to simulation-to-simulation comparison"
            if config.reference.reference_kind == "simulated"
            else "Evidence uses a physical reference within the declared context of use"
        ),
        evidence=["manifest.json"],
    )
    return {
        "configuration": configuration,
        "data_quality": data_quality,
        "alignment": alignment,
        "reproducibility": reproducibility,
        "reference_scope": scope,
    }


def _evaluate_requirement(
    requirement: Requirement,
    builtins: dict[str, CheckResult],
    metrics: dict[tuple[str, str], MetricResult],
) -> CheckResult:
    if requirement.check is not None:
        source = builtins.get(requirement.check)
        if source is None:
            return _invalid_requirement(requirement, f"unknown check: {requirement.check}")
        return CheckResult(
            id=f"REQ-{requirement.id}",
            kind=requirement.kind,
            status=source.status,
            critical=requirement.critical,
            summary=f"{requirement.statement}: {source.summary}",
            requirement_id=requirement.id,
            evidence=source.evidence,
        )

    result = metrics.get((str(requirement.metric), str(requirement.signal)))
    if result is None:
        return _invalid_requirement(requirement, "configured metric result is missing")
    if result.status != CheckStatus.PASS or result.value is None:
        reason = result.details.get("reason", "metric could not be computed")
        return _invalid_requirement(requirement, str(reason))

    assert requirement.operator is not None
    assert requirement.threshold is not None
    passed = _compare(result.value, requirement.operator, requirement.threshold)
    status = CheckStatus.PASS if passed else CheckStatus.FAIL
    return CheckResult(
        id=f"REQ-{requirement.id}",
        kind=requirement.kind,
        status=status,
        critical=requirement.critical,
        summary=(
            f"{requirement.statement}: {result.value:.6g} {requirement.operator} "
            f"{requirement.threshold:.6g}"
        ),
        requirement_id=requirement.id,
        evidence=[f"metrics.json#{result.name}:{result.signal}"],
    )


def _invalid_requirement(requirement: Requirement, reason: str) -> CheckResult:
    return CheckResult(
        id=f"REQ-{requirement.id}",
        kind=requirement.kind,
        status=CheckStatus.INVALID,
        critical=requirement.critical,
        summary=f"{requirement.statement}: {reason}",
        requirement_id=requirement.id,
    )


def _valid_frame(frame: SignalFrame) -> bool:
    return bool(
        len(frame.timestamps)
        and len(frame.values)
        and np.all(np.isfinite(frame.timestamps))
        and np.all(np.isfinite(frame.values))
        and np.all(np.diff(frame.timestamps) >= 0)
    )


def _compare(value: float, operator: str, threshold: float) -> bool:
    operations: dict[str, Any] = {
        "le": lambda: value <= threshold,
        "lt": lambda: value < threshold,
        "ge": lambda: value >= threshold,
        "gt": lambda: value > threshold,
        "eq": lambda: value == threshold,
    }
    return bool(operations[operator]())


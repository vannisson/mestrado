from __future__ import annotations

import hashlib
import platform
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from dt_validation import __version__
from dt_validation.adapters.csv_replay import CsvReplayAdapter
from dt_validation.adapters.synthetic import SyntheticReplayAdapter
from dt_validation.core.alignment import align_nearest
from dt_validation.core.config import load_experiment
from dt_validation.core.models import (
    CheckStatus,
    MetricResult,
    ParticipantSpec,
    ReferenceKind,
    RunManifest,
)
from dt_validation.core.series import AlignedSignal
from dt_validation.metrics.registry import compute_metric
from dt_validation.reporting.artifacts import ArtifactWriter
from dt_validation.reporting.plots import create_validation_plots
from dt_validation.reporting.report import render_report
from dt_validation.vv.evaluator import VVAssessment, evaluate_vv


@dataclass(frozen=True, slots=True)
class ReplayOutcome:
    run_dir: Path
    status: CheckStatus
    metrics: list[MetricResult]
    assessment: VVAssessment


def run_replay(config_path: str | Path) -> ReplayOutcome:
    source_path = Path(config_path).resolve()
    config = load_experiment(source_path)

    run_id = _run_id()
    reference = _adapter(config.reference, run_id)
    candidate = _adapter(config.candidate, run_id)
    reference_frames = reference.load()
    candidate_frames = candidate.load()

    aligned: dict[str, AlignedSignal] = {}
    alignment_failures: dict[str, str] = {}
    for signal in sorted(set(reference_frames) & set(candidate_frames)):
        try:
            aligned[signal] = align_nearest(
                reference_frames[signal],
                candidate_frames[signal],
                tolerance_seconds=config.alignment.tolerance_seconds,
                time_basis=config.alignment.time_basis,
            )
        except ValueError as error:
            alignment_failures[signal] = str(error)

    metric_results: list[MetricResult] = []
    for spec in config.metrics:
        pair = aligned.get(spec.signal)
        if pair is None:
            metric_results.append(
                MetricResult(
                    name=spec.name,
                    signal=spec.signal,
                    status=CheckStatus.INVALID,
                    details={
                        "reason": alignment_failures.get(
                            spec.signal,
                            "signal is unavailable in one or both participants",
                        )
                    },
                )
            )
        else:
            metric_results.append(compute_metric(spec, pair))

    assessment = evaluate_vv(
        config,
        reference_frames,
        candidate_frames,
        aligned,
        metric_results,
        alignment_failures,
    )
    root = _find_project_root(source_path)
    manifest = _manifest(
        source_path,
        root,
        config.name,
        run_id,
        config.seed,
        config.reference.reference_kind,
    )
    run_dir = config.output_dir / config.name / run_id
    writer = ArtifactWriter(run_dir)
    writer.write(
        manifest,
        reference.all_observations + candidate.all_observations,
        metric_results,
        assessment,
    )
    plots = create_validation_plots(run_dir, aligned)
    render_report(run_dir / "report.html", manifest, metric_results, assessment, plots)
    return ReplayOutcome(
        run_dir=run_dir,
        status=assessment.status,
        metrics=metric_results,
        assessment=assessment,
    )


def _adapter(spec: ParticipantSpec, run_id: str) -> CsvReplayAdapter | SyntheticReplayAdapter:
    if spec.data_path is None:
        raise ValueError(f"{spec.adapter} participant must declare data_path")
    if spec.adapter == "csv":
        return CsvReplayAdapter(spec.name, spec.data_path, run_id)
    if spec.adapter == "synthetic":
        return SyntheticReplayAdapter(spec.name, spec.data_path, run_id, spec.metadata)
    raise ValueError(f"unsupported replay adapter: {spec.adapter}")


def _manifest(
    config_path: Path,
    root: Path,
    experiment: str,
    run_id: str,
    seed: int,
    reference_kind: ReferenceKind | None,
) -> RunManifest:
    if reference_kind is None:
        raise ValueError("reference_kind is required")
    git_sha, dirty = _git_state(root)
    lock_path = root / "uv.lock"
    return RunManifest(
        framework_version=__version__,
        run_id=run_id,
        experiment=experiment,
        reference_kind=reference_kind,
        evidence_class=(
            "simulation-to-simulation"
            if reference_kind == ReferenceKind.SIMULATED
            else "physical-validation"
        ),
        git_sha=git_sha,
        git_dirty=dirty,
        config_sha256=_sha256(config_path),
        lock_sha256=_sha256(lock_path) if lock_path.exists() else None,
        seed=seed,
        platform=platform.platform(),
        python_version=sys.version.split()[0],
    )


def _git_state(root: Path) -> tuple[str, bool]:
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
        return sha, dirty
    except (OSError, subprocess.CalledProcessError):
        return "unknown", False


def _find_project_root(path: Path) -> Path:
    for parent in (path.parent, *path.parents):
        if (parent / ".git").exists() or (parent / "pyproject.toml").exists():
            return parent
    return Path.cwd()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_id() -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}-{uuid4().hex[:8]}"

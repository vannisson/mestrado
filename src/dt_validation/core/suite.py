from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel

from dt_validation.core.config import load_experiment
from dt_validation.core.models import CheckStatus
from dt_validation.core.replay import run_replay


@dataclass(frozen=True, slots=True)
class SuiteCaseResult:
    config: Path
    experiment: str
    observed: CheckStatus
    expected: CheckStatus | None
    matched: bool
    run_dir: Path


@dataclass(frozen=True, slots=True)
class SuiteOutcome:
    run_dir: Path
    summary_json: Path
    summary_csv: Path
    results: list[SuiteCaseResult]

    @property
    def status(self) -> CheckStatus:
        if all(result.matched for result in self.results):
            return CheckStatus.PASS
        return CheckStatus.FAIL


class _SuiteCaseRecord(BaseModel):
    config: str
    experiment: str
    observed: CheckStatus
    expected: CheckStatus | None
    matched: bool
    run_dir: str


class _SuiteRecord(BaseModel):
    created_at: datetime
    status: CheckStatus
    cases: list[_SuiteCaseRecord]


def run_suite(path: str | Path) -> SuiteOutcome:
    suite_path = Path(path).resolve()
    configs = _configs(suite_path)
    first_config = load_experiment(configs[0])
    suite_name = suite_path.stem if suite_path.is_dir() else configs[0].stem
    run_dir = first_config.output_dir / "suites" / suite_name / _run_id()
    run_dir.mkdir(parents=True, exist_ok=True)

    results: list[SuiteCaseResult] = []
    for config_path in configs:
        config = load_experiment(config_path)
        outcome = run_replay(config_path)
        matched = config.expected_status is None or outcome.status == config.expected_status
        results.append(
            SuiteCaseResult(
                config=config_path,
                experiment=config.name,
                observed=outcome.status,
                expected=config.expected_status,
                matched=matched,
                run_dir=outcome.run_dir,
            )
        )

    summary_json = run_dir / "suite.json"
    summary_csv = run_dir / "suite.csv"
    _write_json(summary_json, results)
    _write_csv(summary_csv, results)
    return SuiteOutcome(
        run_dir=run_dir,
        summary_json=summary_json,
        summary_csv=summary_csv,
        results=results,
    )


def _configs(path: Path) -> list[Path]:
    configs = sorted(path.glob("*.yaml")) if path.is_dir() else [path]
    if not configs:
        raise ValueError(f"no YAML configurations found in {path}")
    return configs


def _write_json(path: Path, results: list[SuiteCaseResult]) -> None:
    status = CheckStatus.PASS if all(result.matched for result in results) else CheckStatus.FAIL
    record = _SuiteRecord(
        created_at=datetime.now(UTC),
        status=status,
        cases=[
            _SuiteCaseRecord(
                config=str(result.config),
                experiment=result.experiment,
                observed=result.observed,
                expected=result.expected,
                matched=result.matched,
                run_dir=str(result.run_dir),
            )
            for result in results
        ],
    )
    path.write_text(record.model_dump_json(indent=2), encoding="utf-8")


def _write_csv(path: Path, results: list[SuiteCaseResult]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=["config", "experiment", "observed", "expected", "matched", "run_dir"],
        )
        writer.writeheader()
        for result in results:
            writer.writerow(
                {
                    "config": str(result.config),
                    "experiment": result.experiment,
                    "observed": result.observed.value,
                    "expected": "" if result.expected is None else result.expected.value,
                    "matched": result.matched,
                    "run_dir": str(result.run_dir),
                }
            )


def _run_id() -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}-{uuid4().hex[:8]}"

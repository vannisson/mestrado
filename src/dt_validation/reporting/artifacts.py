from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd

from dt_validation.core.models import MetricResult, Observation, RunManifest
from dt_validation.vv.evaluator import VVAssessment


class ArtifactWriter:
    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir

    def write(
        self,
        manifest: RunManifest,
        observations: list[Observation],
        metrics: list[MetricResult],
        assessment: VVAssessment,
    ) -> None:
        self.run_dir.mkdir(parents=True, exist_ok=False)
        (self.run_dir / "logs").mkdir()
        _write_json(self.run_dir / "manifest.json", manifest.model_dump(mode="json"))
        _write_json(
            self.run_dir / "metrics.json",
            [metric.model_dump(mode="json") for metric in metrics],
        )
        _write_json(
            self.run_dir / "evidence.json",
            {
                "status": assessment.status,
                "coverage": assessment.coverage,
                "checks": [check.model_dump(mode="json") for check in assessment.checks],
                "evidence": [item.model_dump(mode="json") for item in assessment.evidence],
            },
        )
        self._write_observations(observations)
        self._write_metrics_csv(metrics)
        self._write_traceability(assessment)

    def _write_observations(self, observations: list[Observation]) -> None:
        rows = [observation.model_dump(mode="json") for observation in observations]
        frame = pd.DataFrame(rows)
        frame.to_parquet(self.run_dir / "observations.parquet", index=False)

    def _write_metrics_csv(self, metrics: list[MetricResult]) -> None:
        rows = [
            {
                "name": metric.name,
                "signal": metric.signal,
                "status": metric.status,
                "value": metric.value,
                "unit": metric.unit,
                "sample_count": metric.sample_count,
            }
            for metric in metrics
        ]
        pd.DataFrame(rows).to_csv(self.run_dir / "metrics.csv", index=False)

    def _write_traceability(self, assessment: VVAssessment) -> None:
        with (self.run_dir / "traceability.csv").open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(
                stream,
                fieldnames=["requirement_id", "check_id", "kind", "critical", "status", "evidence"],
            )
            writer.writeheader()
            for check in assessment.checks:
                writer.writerow(
                    {
                        "requirement_id": check.requirement_id or "",
                        "check_id": check.id,
                        "kind": check.kind,
                        "critical": check.critical,
                        "status": check.status,
                        "evidence": ";".join(check.evidence),
                    }
                )


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


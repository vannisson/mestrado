from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape

from dt_validation.core.models import MetricResult, RunManifest
from dt_validation.vv.evaluator import VVAssessment


def render_report(
    output: Path,
    manifest: RunManifest,
    metrics: list[MetricResult],
    assessment: VVAssessment,
    plots: list[str] | None = None,
) -> None:
    environment = Environment(
        loader=PackageLoader("dt_validation", "reporting/templates"),
        autoescape=select_autoescape(),
    )
    template = environment.get_template("report.html.j2")
    output.write_text(
        template.render(
            manifest=manifest,
            metrics=metrics,
            assessment=assessment,
            plots=plots or [],
        ),
        encoding="utf-8",
    )

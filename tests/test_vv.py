import numpy as np

from dt_validation.core.models import (
    AlignmentSpec,
    CheckStatus,
    ContextOfUse,
    ExperimentConfig,
    MetricResult,
    MetricSpec,
    ParticipantSpec,
    ReferenceKind,
    Requirement,
    RequirementKind,
)
from dt_validation.core.series import AlignedSignal, SignalFrame
from dt_validation.vv.evaluator import evaluate_vv


def test_critical_metric_requirement_controls_result() -> None:
    config = ExperimentConfig(
        name="test",
        context_of_use=ContextOfUse(purpose="test", question="is it close?"),
        reference=ParticipantSpec(
            name="reference",
            role="reference",
            adapter="csv",
            reference_kind=ReferenceKind.SIMULATED,
        ),
        candidate=ParticipantSpec(name="candidate", role="candidate", adapter="csv"),
        alignment=AlignmentSpec(),
        metrics=[MetricSpec(name="rmse", signal="speed")],
        requirements=[
            Requirement(
                id="VAL-1",
                kind=RequirementKind.VALIDATION,
                statement="speed error is acceptable",
                metric="rmse",
                signal="speed",
                operator="le",
                threshold=0.1,
            )
        ],
    )
    frame = SignalFrame("speed", np.array([0.0, 1.0]), np.array([1.0, 1.0]))
    aligned = AlignedSignal(
        signal="speed",
        timestamps=np.array([0.0, 1.0]),
        reference=frame.values,
        candidate=frame.values,
        unit="m/s",
        reference_total=2,
        candidate_total=2,
    )
    metrics = [
        MetricResult(
            name="rmse",
            signal="speed",
            status=CheckStatus.PASS,
            value=0.2,
            sample_count=2,
        )
    ]

    assessment = evaluate_vv(
        config,
        {"speed": frame},
        {"speed": frame},
        {"speed": aligned},
        metrics,
        {},
    )

    assert assessment.status == CheckStatus.FAIL
    assert any(
        check.requirement_id == "VAL-1" and check.status == CheckStatus.FAIL
        for check in assessment.checks
    )

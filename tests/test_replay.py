from pathlib import Path

import pandas as pd

from dt_validation.core.models import CheckStatus
from dt_validation.core.replay import run_replay


def test_replay_generates_complete_evidence_bundle(tmp_path: Path) -> None:
    reference_dir = tmp_path / "reference"
    candidate_dir = tmp_path / "candidate"
    reference_dir.mkdir()
    candidate_dir.mkdir()
    timestamps_reference = pd.date_range("2025-01-01", periods=4, freq="100ms")
    timestamps_candidate = pd.date_range("2025-02-01", periods=4, freq="100ms")
    _write_pose(reference_dir / "odometry_pose.csv", timestamps_reference)
    _write_pose(candidate_dir / "odometry_pose.csv", timestamps_candidate)

    config = tmp_path / "experiment.yaml"
    config.write_text(
        f"""
name: replay-test
context_of_use:
  purpose: regression test
  question: are equal logs recognized?
reference:
  name: source
  role: reference
  adapter: csv
  data_path: {reference_dir.as_posix()}
  reference_kind: simulated
candidate:
  name: twin
  role: candidate
  adapter: csv
  data_path: {candidate_dir.as_posix()}
alignment:
  time_basis: elapsed
  tolerance_seconds: 0.01
metrics:
  - name: ate_rmse
    signal: odometry.position
  - name: quaternion_geodesic_p95
    signal: odometry.orientation
requirements:
  - id: VER-DATA
    kind: verification
    statement: data must be valid
    check: data_quality
  - id: VAL-POS
    kind: validation
    statement: position must match
    metric: ate_rmse
    signal: odometry.position
    operator: le
    threshold: 0.001
output_dir: {(tmp_path / 'artifacts').as_posix()}
seed: 42
""".strip(),
        encoding="utf-8",
    )

    outcome = run_replay(config)

    assert outcome.status == CheckStatus.PASS
    for name in (
        "manifest.json",
        "observations.parquet",
        "metrics.json",
        "metrics.csv",
        "evidence.json",
        "traceability.csv",
        "report.html",
    ):
        assert (outcome.run_dir / name).exists()
    assert (outcome.run_dir / "plots" / "trajectory_xy.png").exists()
    assert (outcome.run_dir / "plots" / "odometry_position_error.png").exists()


def _write_pose(path: Path, timestamps: pd.DatetimeIndex) -> None:
    pd.DataFrame(
        {
            "timestamp": timestamps.astype(str),
            "v0": [0.0, 1.0, 2.0, 3.0],
            "v1": [0.0, 0.0, 0.0, 0.0],
            "v2": [0.0, 0.0, 0.0, 0.0],
            "v3": [0.0, 0.0, 0.0, 0.0],
            "v4": [0.0, 0.0, 0.0, 0.0],
            "v5": [0.0, 0.0, 0.0, 0.0],
            "v6": [1.0, 1.0, 1.0, 1.0],
        }
    ).to_csv(path, index=False)

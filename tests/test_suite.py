from pathlib import Path

import pandas as pd

from dt_validation.core.models import CheckStatus
from dt_validation.core.suite import run_suite


def test_suite_writes_machine_readable_summary(tmp_path: Path) -> None:
    reference_dir = tmp_path / "reference"
    reference_dir.mkdir()
    _write_pose(reference_dir / "odometry_pose.csv")

    config = tmp_path / "identity.yaml"
    config.write_text(
        f"""
name: suite-test
expected_status: PASS
context_of_use:
  purpose: regression test
  question: can the suite summarize expected outcomes?
reference:
  name: source
  role: reference
  adapter: csv
  data_path: {reference_dir.as_posix()}
  reference_kind: simulated
candidate:
  name: twin
  role: candidate
  adapter: synthetic
  data_path: {reference_dir.as_posix()}
  metadata:
    transformations:
      - type: identity
alignment:
  time_basis: elapsed
  tolerance_seconds: 0.01
metrics:
  - name: ate_rmse
    signal: odometry.position
requirements:
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

    outcome = run_suite(tmp_path)

    assert outcome.status == CheckStatus.PASS
    assert outcome.summary_json.exists()
    assert outcome.summary_csv.exists()
    assert outcome.results[0].matched


def _write_pose(path: Path) -> None:
    timestamps = pd.date_range("2025-01-01", periods=4, freq="100ms", tz="UTC")
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

from pathlib import Path

import numpy as np
import pandas as pd

from dt_validation.adapters.synthetic import SyntheticReplayAdapter
from dt_validation.core.models import CheckStatus
from dt_validation.core.replay import run_replay


def test_synthetic_adapter_delays_values_without_changing_timestamps(tmp_path: Path) -> None:
    _write_imu(tmp_path / "imu_linearVelocity.csv")
    adapter = SyntheticReplayAdapter(
        "candidate",
        tmp_path,
        "run-1",
        {
            "seed": 42,
            "transformations": [
                {
                    "type": "delay",
                    "seconds": 1.0,
                    "signals": ["imu.linear_velocity"],
                }
            ],
        },
    )

    frame = adapter.load()["imu.linear_velocity"]

    np.testing.assert_allclose(frame.values[:, 0], [0.0, 0.0, 1.0, 2.0])
    assert len(adapter.all_observations) == 4


def test_synthetic_adapter_drops_samples_deterministically(tmp_path: Path) -> None:
    _write_imu(tmp_path / "imu_linearVelocity.csv")
    adapter = SyntheticReplayAdapter(
        "candidate",
        tmp_path,
        "run-1",
        {
            "seed": 42,
            "transformations": [
                {
                    "type": "dropout",
                    "keep_every": 2,
                    "signals": ["imu.linear_velocity"],
                }
            ],
        },
    )

    frame = adapter.load()["imu.linear_velocity"]

    np.testing.assert_allclose(frame.values[:, 0], [0.0, 2.0, 3.0])


def test_replay_supports_synthetic_identity_candidate(tmp_path: Path) -> None:
    reference_dir = tmp_path / "reference"
    reference_dir.mkdir()
    _write_pose(reference_dir / "odometry_pose.csv")

    config = tmp_path / "synthetic.yaml"
    config.write_text(
        f"""
name: synthetic-test
expected_status: PASS
context_of_use:
  purpose: regression test
  question: are synthetic identity logs recognized?
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
    seed: 42
    transformations:
      - type: identity
alignment:
  time_basis: elapsed
  tolerance_seconds: 0.01
metrics:
  - name: ate_rmse
    signal: odometry.position
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


def _write_imu(path: Path) -> None:
    timestamps = pd.date_range("2025-01-01", periods=4, freq="1s", tz="UTC")
    pd.DataFrame(
        {
            "timestamp": timestamps.astype(str),
            "v0": [0.0, 1.0, 2.0, 3.0],
        }
    ).to_csv(path, index=False)


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

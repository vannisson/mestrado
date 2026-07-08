from pathlib import Path

import yaml

from dt_validation.core.models import ExperimentConfig


def load_experiment(path: str | Path) -> ExperimentConfig:
    config_path = Path(path).resolve()
    with config_path.open(encoding="utf-8") as stream:
        raw = yaml.safe_load(stream)
    if not isinstance(raw, dict):
        raise ValueError(f"experiment configuration must be a mapping: {config_path}")
    config = ExperimentConfig.model_validate(raw)
    base = config_path.parent
    if config.reference.data_path is not None and not config.reference.data_path.is_absolute():
        config.reference.data_path = (base / config.reference.data_path).resolve()
    if config.candidate.data_path is not None and not config.candidate.data_path.is_absolute():
        config.candidate.data_path = (base / config.candidate.data_path).resolve()
    if not config.output_dir.is_absolute():
        config.output_dir = (base / config.output_dir).resolve()
    return config

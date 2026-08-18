"""Configuration loading and validation utilities."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


ENV_PATTERN = re.compile(r"\$\{([^}:]+)(?::-(.*?))?\}")


def _expand_env(value: Any) -> Any:
    if isinstance(value, str):
        def repl(match: re.Match[str]) -> str:
            name, default = match.group(1), match.group(2)
            return os.getenv(name, default or "")

        return ENV_PATTERN.sub(repl, value)
    if isinstance(value, list):
        return [_expand_env(item) for item in value]
    if isinstance(value, dict):
        return {key: _expand_env(val) for key, val in value.items()}
    return value


class RuntimeConfig(BaseModel):
    dry_run: bool = True
    overwrite: bool = False
    resume: bool = True
    max_samples_per_run: int | None = None
    pilot_samples: int = 20


class ExperimentConfig(BaseModel):
    report_language: str = "vi"
    python_min_version: str = "3.10"
    models_config: str
    datasets_config: str
    output_dir: str = "outputs"
    prompts_dir: str = "prompts"
    random_seeds: list[int] = Field(default_factory=lambda: [42, 123, 2026])
    datasets: list[str]
    sample_size_per_dataset: int = 250
    default_agents: int = 5
    debate_rounds: list[int] = Field(default_factory=lambda: [0, 1, 2, 3])
    self_consistency_k: int = 5
    fair_compute: dict[str, Any] = Field(default_factory=dict)
    baselines: list[str] = Field(default_factory=list)
    debate_methods: list[str] = Field(default_factory=list)
    ablations: dict[str, Any] = Field(default_factory=dict)
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
    evaluation: dict[str, Any] = Field(default_factory=dict)


def load_yaml(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return _expand_env(yaml.safe_load(handle) or {})


def load_experiment_config(path: str | Path) -> ExperimentConfig:
    return ExperimentConfig.model_validate(load_yaml(path))


def ensure_output_dirs(output_dir: str | Path) -> None:
    base = Path(output_dir)
    for child in ["raw", "processed", "tables", "figures", "logs"]:
        (base / child).mkdir(parents=True, exist_ok=True)

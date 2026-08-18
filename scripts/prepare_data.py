"""Prepare and lock benchmark subsets."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

from src.datasets.loader import prepare_datasets
from src.utils.config import ensure_output_dirs, load_experiment_config


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/experiment.yaml")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    load_dotenv()
    cfg = load_experiment_config(args.config)
    ensure_output_dirs(cfg.output_dir)
    dry_run = args.dry_run or cfg.runtime.dry_run
    prepare_datasets(cfg.datasets_config, f"{cfg.output_dir}/processed", dry_run=dry_run)


if __name__ == "__main__":
    main()

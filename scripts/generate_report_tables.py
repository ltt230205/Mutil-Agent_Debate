"""Generate Markdown tables for the report from evaluated CSV files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from src.utils.config import load_experiment_config


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/experiment.yaml")
    args = parser.parse_args()
    cfg = load_experiment_config(args.config)
    table_dir = Path(cfg.output_dir) / "tables"
    report_dir = Path("report")
    report_dir.mkdir(exist_ok=True)
    main_results = table_dir / "main_results.csv"
    if not main_results.exists():
        raise RuntimeError("Run scripts/evaluate.py first.")
    df = pd.read_csv(main_results)
    cols = ["dataset", "method", "n", "accuracy", "mean_total_tokens", "accuracy_per_1000_tokens", "mean_latency_seconds"]
    markdown = to_markdown(df[cols])
    (report_dir / "generated_tables.md").write_text(markdown + "\n", encoding="utf-8")


def to_markdown(df: pd.DataFrame) -> str:
    headers = list(df.columns)
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for _, row in df.iterrows():
        values = [format_value(row[col]) for col in headers]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def format_value(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


if __name__ == "__main__":
    main()

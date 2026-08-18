"""Evaluate raw JSONL prediction files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
try:
    import matplotlib.pyplot as plt
except ModuleNotFoundError:
    plt = None

from src.analysis.behavioral import classify_transitions
from src.evaluation.metrics import correction_degradation, error_type_counts, semantic_diversity, summarize_predictions
from src.utils.config import ensure_output_dirs, load_experiment_config


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/experiment.yaml")
    args = parser.parse_args()
    cfg = load_experiment_config(args.config)
    ensure_output_dirs(cfg.output_dir)
    raw_dir = Path(cfg.output_dir) / "raw"
    records = read_jsonl(raw_dir / "baselines.jsonl") + read_jsonl(raw_dir / "debate.jsonl") + read_jsonl(raw_dir / "ablations.jsonl")
    if not records:
        raise RuntimeError("No raw prediction files found. Run baselines/debate first.")
    df = pd.DataFrame(records)
    processed = Path(cfg.output_dir) / "processed"
    tables = Path(cfg.output_dir) / "tables"
    df.to_csv(processed / "predictions.csv", index=False)
    summary = summarize_predictions(df)
    summary.to_csv(tables / "main_results.csv", index=False)
    write_figures(summary, Path(cfg.output_dir) / "figures")
    df["semantic_diversity"] = df["traces"].apply(semantic_diversity)
    df[["sample_id", "dataset", "method", "semantic_diversity"]].to_csv(tables / "reasoning_diversity.csv", index=False)
    error_type_counts(records).to_csv(tables / "error_taxonomy_counts.csv", index=False)
    if "single_cot" in set(df["method"]):
        before = df[df["method"] == "single_cot"]
        after = df[df["method"].str.contains("specialized_debate", na=False)]
        if len(after):
            Path(tables / "correction_degradation.json").write_text(
                json.dumps(correction_degradation(before, after), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            classify_transitions(before, after).to_csv(tables / "behavioral_transitions.csv", index=False)


def write_figures(summary: pd.DataFrame, figures_dir: Path) -> None:
    if plt is None:
        (figures_dir / "FIGURES_NOT_GENERATED.txt").parent.mkdir(parents=True, exist_ok=True)
        (figures_dir / "FIGURES_NOT_GENERATED.txt").write_text(
            "matplotlib is not installed in this environment. Install requirements.txt and rerun evaluate.py.\n",
            encoding="utf-8",
        )
        return
    figures_dir.mkdir(parents=True, exist_ok=True)
    if len(summary) == 0:
        return
    for dataset, group in summary.groupby("dataset"):
        compact = group.sort_values("accuracy", ascending=False).head(15)
        plt.figure(figsize=(10, 5))
        plt.bar(compact["method"], compact["accuracy"])
        plt.xticks(rotation=45, ha="right", fontsize=8)
        plt.ylabel("Accuracy")
        plt.title(f"Accuracy by method - {dataset}")
        plt.tight_layout()
        plt.savefig(figures_dir / f"accuracy_{dataset}.png", dpi=160)
        plt.close()

        plt.figure(figsize=(10, 5))
        plt.bar(compact["method"], compact["mean_total_tokens"])
        plt.xticks(rotation=45, ha="right", fontsize=8)
        plt.ylabel("Mean total tokens")
        plt.title(f"Token cost by method - {dataset}")
        plt.tight_layout()
        plt.savefig(figures_dir / f"token_cost_{dataset}.png", dpi=160)
        plt.close()


if __name__ == "__main__":
    main()

"""Run ablation configurations."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

from src.agents.llm_client import LlmClient
from src.datasets.loader import load_prepared_samples
from src.protocols.debate import run_debate
from src.utils.cache import JsonlCache
from src.utils.config import ensure_output_dirs, load_experiment_config, load_yaml


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/experiment.yaml")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    load_dotenv()
    cfg = load_experiment_config(args.config)
    model_cfg = load_yaml(cfg.models_config)
    ensure_output_dirs(cfg.output_dir)
    samples = load_prepared_samples(Path(cfg.output_dir) / "processed" / "samples.jsonl")
    max_samples = cfg.runtime.max_samples_per_run or (cfg.runtime.pilot_samples if (args.dry_run or cfg.runtime.dry_run) else None)
    if max_samples:
        samples = samples[:max_samples]
    out_path = Path(cfg.output_dir) / "raw" / "ablations.jsonl"
    if out_path.exists() and not cfg.runtime.overwrite:
        raise FileExistsError(f"{out_path} exists. Set runtime.overwrite=true or move the file.")
    cache = JsonlCache(Path(cfg.output_dir) / "raw" / "response_cache.jsonl")
    with out_path.open("w", encoding="utf-8") as handle:
        for seed in cfg.random_seeds:
            client = LlmClient(
                model=model_cfg["default_model"],
                cache=cache,
                dry_run=args.dry_run or cfg.runtime.dry_run or bool(model_cfg.get("mock", {}).get("enabled")),
                temperature=float(model_cfg.get("temperature", 0.2)),
                max_output_tokens=int(model_cfg.get("max_output_tokens", 700)),
                seed=seed,
            )
            for sample in samples:
                for rounds in cfg.ablations.get("rounds", [0, 1, 2, 3]):
                    record = run_debate(sample, client, cfg.prompts_dir, "ablation_rounds", rounds, cfg.default_agents, seed, True, "judge")
                    handle.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")
                for remove_role in cfg.ablations.get("remove_one_role", []):
                    role_flag = None if remove_role == "full" else remove_role
                    record = run_debate(sample, client, cfg.prompts_dir, f"ablation_{remove_role}", 2, cfg.default_agents, seed, True, "judge", role_flag)
                    handle.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")
                for decision in cfg.ablations.get("decision_protocol", []):
                    record = run_debate(sample, client, cfg.prompts_dir, f"ablation_decision_{decision}", 2, cfg.default_agents, seed, True, decision)
                    handle.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")
                for n_agents in cfg.ablations.get("num_agents", []):
                    record = run_debate(sample, client, cfg.prompts_dir, f"ablation_agents_{n_agents}", 2, n_agents, seed, True, "judge")
                    handle.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()

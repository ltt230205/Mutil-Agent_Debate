"""Run baseline methods."""

from __future__ import annotations

import argparse
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

from src.agents.llm_client import LlmClient
from src.datasets.loader import load_prepared_samples
from src.protocols.baselines import run_multi_agent_majority, run_self_consistency, run_single
from src.utils.cache import JsonlCache
from src.utils.checkpoint import open_resumable_jsonl, record_key, write_checkpoint
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
    out_path = Path(cfg.output_dir) / "raw" / "baselines.jsonl"
    cache = JsonlCache(Path(cfg.output_dir) / "raw" / "response_cache.jsonl")
    handle, completed = open_resumable_jsonl(
        out_path,
        overwrite=cfg.runtime.overwrite,
        resume=cfg.runtime.resume,
    )
    retry_cfg = model_cfg.get("retry", {})
    rate_cfg = model_cfg.get("rate_limit", {})
    with handle:
        for seed in cfg.random_seeds:
            client = LlmClient(
                model=model_cfg["default_model"],
                cache=cache,
                dry_run=args.dry_run or cfg.runtime.dry_run or bool(model_cfg.get("mock", {}).get("enabled")),
                temperature=float(model_cfg.get("temperature", 0.2)),
                max_output_tokens=int(model_cfg.get("max_output_tokens", 700)),
                max_attempts=int(retry_cfg.get("max_attempts", 3)),
                backoff_seconds=float(retry_cfg.get("backoff_seconds", 2)),
                min_delay_seconds=float(rate_cfg.get("min_delay_seconds", 0.2)),
                seed=seed,
            )
            for sample in samples:
                jobs = [
                    ("single_direct", lambda: run_single(sample, client, cfg.prompts_dir, "single_direct", seed)),
                    ("single_cot", lambda: run_single(sample, client, cfg.prompts_dir, "single_cot", seed)),
                    ("self_consistency", lambda: run_self_consistency(sample, client, cfg.prompts_dir, cfg.self_consistency_k, seed)),
                    ("multi_agent_majority", lambda: run_multi_agent_majority(sample, client, cfg.prompts_dir, cfg.default_agents, seed)),
                ]
                if cfg.fair_compute.get("run_call_matched"):
                    call_matched_k = int(cfg.fair_compute.get("call_matched_k", 10))
                    jobs.extend(
                        [
                            (
                                f"self_consistency_k{call_matched_k}_call_matched",
                                lambda: run_self_consistency(
                                    sample,
                                    client,
                                    cfg.prompts_dir,
                                    call_matched_k,
                                    seed,
                                    f"self_consistency_k{call_matched_k}_call_matched",
                                ),
                            ),
                            (
                                f"multi_agent_majority_n{call_matched_k}_call_matched",
                                lambda: run_multi_agent_majority(
                                    sample,
                                    client,
                                    cfg.prompts_dir,
                                    call_matched_k,
                                    seed,
                                    f"multi_agent_majority_n{call_matched_k}_call_matched",
                                ),
                            ),
                        ]
                    )
                for method, runner in jobs:
                    key = (seed, sample.sample_id, method)
                    if key in completed:
                        continue
                    print(f"[baseline] start seed={seed} sample={sample.sample_id} method={method}", flush=True)
                    data = asdict(runner())
                    write_checkpoint(handle, data)
                    completed.add(record_key(data))
                    print(f"[baseline] done {len(completed)} records", flush=True)


if __name__ == "__main__":
    main()

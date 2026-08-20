"""Baseline runners."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.agents.base import Agent
from src.agents.llm_client import LlmClient
from src.protocols.aggregation import majority_vote
from src.schemas.agent_outputs import SolverOutput
from src.schemas.dataset import Sample


@dataclass
class PredictionRecord:
    sample_id: str
    dataset: str
    method: str
    seed: int
    answer: str
    gold: str
    correct: bool
    confidence: float
    input_tokens: int
    output_tokens: int
    total_tokens: int
    latency_seconds: float
    traces: list[str]
    raw: list[dict[str, Any]]


def run_single(sample: Sample, client: LlmClient, prompts_dir: str, method: str, seed: int) -> PredictionRecord:
    agent = Agent("solver", Path(prompts_dir) / "solver.txt", client)
    output, response = agent.run(sample, 0, {"method": method})
    assert isinstance(output, SolverOutput)
    output.reasoning_id = f"{method}_{sample.sample_id}"
    return _record(sample, method, seed, output.answer, output.confidence, response.usage.input_tokens, response.usage.output_tokens, response.latency_seconds, [output], [output.model_dump()])


def run_self_consistency(
    sample: Sample,
    client: LlmClient,
    prompts_dir: str,
    k: int,
    seed: int,
    method: str = "self_consistency",
) -> PredictionRecord:
    outputs: list[SolverOutput] = []
    input_tokens = output_tokens = 0
    latency = 0.0
    for idx in range(k):
        agent = Agent("solver", Path(prompts_dir) / "solver.txt", client)
        output, response = agent.run(sample, 0, {"method": method, "path": idx})
        assert isinstance(output, SolverOutput)
        output.reasoning_id = f"sc_{idx}_{sample.sample_id}"
        outputs.append(output)
        input_tokens += response.usage.input_tokens
        output_tokens += response.usage.output_tokens
        latency += response.latency_seconds
    answer, confidence = majority_vote(outputs)
    return _record(sample, method, seed, answer, confidence, input_tokens, output_tokens, latency, outputs, [o.model_dump() for o in outputs])


def run_multi_agent_majority(
    sample: Sample,
    client: LlmClient,
    prompts_dir: str,
    num_agents: int,
    seed: int,
    method: str = "multi_agent_majority",
) -> PredictionRecord:
    outputs: list[SolverOutput] = []
    input_tokens = output_tokens = 0
    latency = 0.0
    for idx in range(num_agents):
        agent = Agent("solver", Path(prompts_dir) / "solver.txt", client)
        output, response = agent.run(sample, 0, {"method": method, "agent_index": idx})
        assert isinstance(output, SolverOutput)
        output.reasoning_id = f"mv_{idx}_{sample.sample_id}"
        outputs.append(output)
        input_tokens += response.usage.input_tokens
        output_tokens += response.usage.output_tokens
        latency += response.latency_seconds
    answer, confidence = majority_vote(outputs)
    return _record(sample, method, seed, answer, confidence, input_tokens, output_tokens, latency, outputs, [o.model_dump() for o in outputs])


def _record(
    sample: Sample,
    method: str,
    seed: int,
    answer: str,
    confidence: float,
    input_tokens: int,
    output_tokens: int,
    latency: float,
    outputs: list[SolverOutput],
    raw: list[dict[str, Any]],
) -> PredictionRecord:
    normalized = answer.strip().upper()[:1]
    gold = sample.answer.strip().upper()[:1]
    return PredictionRecord(
        sample_id=sample.sample_id,
        dataset=sample.dataset,
        method=method,
        seed=seed,
        answer=normalized,
        gold=gold,
        correct=normalized == gold,
        confidence=confidence,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        latency_seconds=latency,
        traces=[" ".join(o.rationale_summary) for o in outputs],
        raw=raw,
    )

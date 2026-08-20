"""Multi-agent debate orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.agents.base import Agent
from src.agents.llm_client import LlmClient
from src.protocols.aggregation import judge_to_solver_like, majority_vote, shuffle_for_blind_judge
from src.protocols.baselines import PredictionRecord, _record
from src.schemas.agent_outputs import CritiqueOutput, EvidenceCheckerOutput, JudgeOutput, SolverOutput
from src.schemas.dataset import Sample


def run_debate(
    sample: Sample,
    client: LlmClient,
    prompts_dir: str,
    method: str,
    rounds: int,
    num_agents: int,
    seed: int,
    specialized: bool = True,
    decision_protocol: str = "judge",
    remove_role: str | None = None,
) -> PredictionRecord:
    prompts = Path(prompts_dir)
    solver = Agent("solver", prompts / "solver.txt", client)
    critic = Agent("critic", prompts / "critic.txt", client)
    skeptic = Agent("skeptic", prompts / "skeptic.txt", client)
    evidence_checker = Agent("evidence_checker", prompts / "evidence_checker.txt", client)
    judge = Agent("judge", prompts / "judge.txt", client)

    responses: list[dict[str, Any]] = []
    solver_outputs: list[SolverOutput] = []
    input_tokens = output_tokens = 0
    latency = 0.0

    for idx in range(num_agents):
        output, response = solver.run(sample, 0, {"agent_index": idx, "method": method})
        assert isinstance(output, SolverOutput)
        output.reasoning_id = f"solver_{idx}_round_0"
        solver_outputs.append(output)
        responses.append(output.model_dump())
        input_tokens += response.usage.input_tokens
        output_tokens += response.usage.output_tokens
        latency += response.latency_seconds

    initial_outputs = list(solver_outputs)
    debate_state: dict[str, Any] = {"initial": [o.model_dump() for o in solver_outputs]}

    for round_id in range(1, rounds + 1):
        critiques: list[dict[str, Any]] = []
        if specialized and remove_role != "no_critic":
            critique, response = critic.run(sample, round_id, debate_state)
            assert isinstance(critique, CritiqueOutput)
            critiques.append(critique.model_dump())
            responses.append(critique.model_dump())
            input_tokens += response.usage.input_tokens
            output_tokens += response.usage.output_tokens
            latency += response.latency_seconds
        if specialized and remove_role != "no_skeptic":
            skeptical, response = skeptic.run(sample, round_id, debate_state)
            assert isinstance(skeptical, CritiqueOutput)
            critiques.append(skeptical.model_dump())
            responses.append(skeptical.model_dump())
            input_tokens += response.usage.input_tokens
            output_tokens += response.usage.output_tokens
            latency += response.latency_seconds
        if specialized and remove_role != "no_evidence_checker":
            checked, response = evidence_checker.run(sample, round_id, debate_state)
            assert isinstance(checked, EvidenceCheckerOutput)
            critiques.append(checked.model_dump())
            responses.append(checked.model_dump())
            input_tokens += response.usage.input_tokens
            output_tokens += response.usage.output_tokens
            latency += response.latency_seconds

        revised: list[SolverOutput] = []
        for idx, previous in enumerate(solver_outputs):
            output, response = solver.run(
                sample,
                round_id,
                {"previous_answer": previous.model_dump(), "critiques": critiques, "method": method, "agent_index": idx},
            )
            assert isinstance(output, SolverOutput)
            output.reasoning_id = f"solver_{idx}_round_{round_id}"
            revised.append(output)
            responses.append(output.model_dump())
            input_tokens += response.usage.input_tokens
            output_tokens += response.usage.output_tokens
            latency += response.latency_seconds
        solver_outputs = revised
        debate_state = {"previous": [o.model_dump() for o in solver_outputs], "critiques": critiques}

    if decision_protocol == "majority" or remove_role == "no_judge":
        answer, confidence = majority_vote(solver_outputs)
        final_output = SolverOutput(
            sample_id=sample.sample_id,
            agent_role="majority",
            round=rounds,
            answer=answer,
            rationale_summary=["Majority vote after debate."],
            confidence=confidence,
        )
    else:
        blind = shuffle_for_blind_judge(solver_outputs, seed)
        judged, response = judge.run(sample, rounds, {"answers": [o.model_dump() for o in blind], "decision_protocol": decision_protocol})
        assert isinstance(judged, JudgeOutput)
        final_output = judge_to_solver_like(judged)
        responses.append(judged.model_dump())
        input_tokens += response.usage.input_tokens
        output_tokens += response.usage.output_tokens
        latency += response.latency_seconds

    record = _record(
        sample,
        f"{method}_r{rounds}_{decision_protocol}",
        seed,
        final_output.answer,
        final_output.confidence,
        input_tokens,
        output_tokens,
        latency,
        solver_outputs,
        responses,
    )
    record.raw.append({"initial_outputs": [o.model_dump() for o in initial_outputs]})
    return record

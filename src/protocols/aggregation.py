"""Decision protocols."""

from __future__ import annotations

import random
from collections import Counter

from src.schemas.agent_outputs import JudgeOutput, SolverOutput


def majority_vote(outputs: list[SolverOutput]) -> tuple[str, float]:
    counts = Counter(output.answer.strip().upper() for output in outputs)
    if not counts:
        return "", 0.0
    answer, votes = counts.most_common(1)[0]
    return answer, votes / len(outputs)


def shuffle_for_blind_judge(outputs: list[SolverOutput], seed: int) -> list[SolverOutput]:
    copied = list(outputs)
    random.Random(seed).shuffle(copied)
    for idx, output in enumerate(copied):
        output.reasoning_id = output.reasoning_id or f"anonymous_{idx}"
    return copied


def judge_to_solver_like(judge: JudgeOutput) -> SolverOutput:
    return SolverOutput(
        sample_id=judge.sample_id,
        agent_role="judge",
        round=0,
        answer=judge.final_answer,
        rationale_summary=[judge.decision_reason],
        evidence=[],
        confidence=judge.confidence,
        reasoning_id=judge.selected_reasoning_id,
    )

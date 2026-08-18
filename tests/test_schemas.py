from src.schemas.agent_outputs import EvidenceItem, JudgeOutput, SolverOutput


def test_solver_output_contract() -> None:
    output = SolverOutput(
        sample_id="x",
        answer="A",
        rationale_summary=["Because premise one supports A."],
        evidence=[EvidenceItem(claim="p", source="premise_1", status="SUPPORTED")],
        confidence=0.7,
    )
    assert output.answer == "A"


def test_judge_confidence_range() -> None:
    output = JudgeOutput(sample_id="x", final_answer="B", decision_reason="short", confidence=0.2)
    assert output.confidence == 0.2

from src.schemas.agent_outputs import CritiqueOutput, EvidenceItem, Issue, JudgeOutput, SolverOutput


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


def test_critique_role_is_case_insensitive() -> None:
    output = CritiqueOutput(
        sample_id="x",
        agent_role="Skeptic",
        round=1,
        issues=["Cần kiểm tra lại giả định."],
    )
    assert output.agent_role == "skeptic"


def test_issue_alias_is_mapped_to_locked_taxonomy() -> None:
    issue = Issue(type="EVIDENCE_SUPPORT", description="Thiếu hỗ trợ.", severity="critical")
    assert issue.type == "MISSING_EVIDENCE"
    assert issue.severity == "HIGH"


def test_single_evidence_object_is_wrapped_as_list() -> None:
    output = SolverOutput(
        sample_id="x",
        answer="A",
        evidence={"claim": "p", "source": "premise", "status": "SUPPORTED"},
        confidence=0.8,
    )
    assert len(output.evidence) == 1

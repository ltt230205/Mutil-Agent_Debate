"""Pydantic contracts for agent outputs."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


EvidenceStatus = Literal["SUPPORTED", "UNSUPPORTED", "CONTRADICTED", "UNCERTAIN"]
IssueType = Literal[
    "LOGICAL_ERROR",
    "MISINTERPRETATION",
    "MISSING_EVIDENCE",
    "UNSUPPORTED_ASSUMPTION",
    "ARITHMETIC_ERROR",
    "HALLUCINATION",
    "CONFORMITY_ERROR",
    "JUDGE_ERROR",
    "ANSWER_EXTRACTION_ERROR",
    "CONTEXT_OVERLOAD",
]


class EvidenceItem(BaseModel):
    claim: str
    source: str = "question"
    status: EvidenceStatus = "UNCERTAIN"


class SolverOutput(BaseModel):
    sample_id: str
    agent_role: str = "solver"
    round: int = 0
    answer: str
    rationale_summary: list[str] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning_id: str | None = None


class Issue(BaseModel):
    type: IssueType
    target_step: int | None = None
    description: str
    severity: Literal["LOW", "MEDIUM", "HIGH"] = "MEDIUM"


class CritiqueOutput(BaseModel):
    sample_id: str
    agent_role: Literal["critic", "skeptic"]
    round: int
    issues: list[Issue] = Field(default_factory=list)
    recommended_revision: str = ""


class EvidenceCheckerOutput(BaseModel):
    sample_id: str
    agent_role: str = "evidence_checker"
    round: int
    evidence: list[EvidenceItem] = Field(default_factory=list)
    recommended_revision: str = ""


class JudgeOutput(BaseModel):
    sample_id: str
    final_answer: str
    selected_reasoning_id: str | None = None
    decision_reason: str
    confidence: float = Field(ge=0.0, le=1.0)

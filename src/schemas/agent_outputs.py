"""Pydantic contracts for agent outputs."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


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

    @field_validator("rationale_summary", mode="before")
    @classmethod
    def coerce_rationale_summary(cls, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        return value  # type: ignore[return-value]

    @field_validator("evidence", mode="before")
    @classmethod
    def coerce_evidence(cls, value: object) -> list[dict[str, str]]:
        if value is None:
            return []
        if isinstance(value, str):
            return [{"claim": value, "source": "đề bài", "status": "UNCERTAIN"}]
        if isinstance(value, list):
            normalized = []
            for item in value:
                if isinstance(item, str):
                    normalized.append({"claim": item, "source": "đề bài", "status": "UNCERTAIN"})
                else:
                    normalized.append(item)
            return normalized
        return value  # type: ignore[return-value]


class Issue(BaseModel):
    type: IssueType
    target_step: int | None = None
    description: str
    severity: Literal["LOW", "MEDIUM", "HIGH"] = "MEDIUM"

    @model_validator(mode="before")
    @classmethod
    def coerce_issue(cls, value: object) -> object:
        if isinstance(value, str):
            return {
                "type": "MISINTERPRETATION",
                "description": value,
                "severity": "MEDIUM",
            }
        if isinstance(value, dict) and "issue" in value:
            coerced = dict(value)
            coerced.setdefault("description", str(coerced.pop("issue")))
            coerced.setdefault("type", "MISINTERPRETATION")
            coerced.setdefault("severity", "MEDIUM")
            return coerced
        return value


class CritiqueOutput(BaseModel):
    sample_id: str
    agent_role: Literal["critic", "skeptic"]
    round: int
    issues: list[Issue] = Field(default_factory=list)
    recommended_revision: str = ""

    @field_validator("issues", mode="before")
    @classmethod
    def coerce_issues(cls, value: object) -> list[object]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        return value  # type: ignore[return-value]


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

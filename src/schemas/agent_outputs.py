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

    @field_validator("status", mode="before")
    @classmethod
    def normalize_status(cls, value: object) -> str:
        normalized = str(value or "UNCERTAIN").strip().upper().replace("-", "_").replace(" ", "_")
        aliases = {
            "UNKNOWN": "UNCERTAIN",
            "NOT_SUPPORTED": "UNSUPPORTED",
            "PARTIALLY_SUPPORTED": "UNCERTAIN",
        }
        normalized = aliases.get(normalized, normalized)
        if normalized not in {"SUPPORTED", "UNSUPPORTED", "CONTRADICTED", "UNCERTAIN"}:
            return "UNCERTAIN"
        return normalized


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
        if isinstance(value, dict):
            return [value]  # type: ignore[list-item]
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

    @field_validator("type", mode="before")
    @classmethod
    def normalize_issue_type(cls, value: object) -> str:
        normalized = str(value or "MISINTERPRETATION").strip().upper().replace("-", "_").replace(" ", "_")
        known = {
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
        }
        aliases = {
            "LOGIC_ERROR": "LOGICAL_ERROR",
            "EVIDENCE_SUPPORT": "MISSING_EVIDENCE",
            "UNSUPPORTED_CLAIM": "UNSUPPORTED_ASSUMPTION",
            "MISSING_INFORMATION": "MISSING_EVIDENCE",
            "AMBIGUITY": "MISINTERPRETATION",
            "FACTUAL_ERROR": "HALLUCINATION",
            "FORMAT_ERROR": "ANSWER_EXTRACTION_ERROR",
        }
        normalized = aliases.get(normalized, normalized)
        if normalized in known:
            return normalized
        if "EVIDENCE" in normalized:
            return "MISSING_EVIDENCE"
        if "LOGIC" in normalized or "INCONSIST" in normalized:
            return "LOGICAL_ERROR"
        if "ASSUMPT" in normalized:
            return "UNSUPPORTED_ASSUMPTION"
        if "ARITH" in normalized or "MATH" in normalized:
            return "ARITHMETIC_ERROR"
        if "CONFORM" in normalized or "SYCOPH" in normalized:
            return "CONFORMITY_ERROR"
        if "CONTEXT" in normalized:
            return "CONTEXT_OVERLOAD"
        return "MISINTERPRETATION"

    @field_validator("severity", mode="before")
    @classmethod
    def normalize_severity(cls, value: object) -> str:
        normalized = str(value or "MEDIUM").strip().upper()
        return {"CRITICAL": "HIGH", "MODERATE": "MEDIUM", "MINOR": "LOW"}.get(normalized, normalized)

    @field_validator("target_step", mode="before")
    @classmethod
    def normalize_target_step(cls, value: object) -> int | None:
        if value is None or value == "":
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

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

    @field_validator("agent_role", mode="before")
    @classmethod
    def normalize_agent_role(cls, value: object) -> str:
        normalized = str(value).strip().lower()
        if "skeptic" in normalized:
            return "skeptic"
        if "critic" in normalized:
            return "critic"
        return normalized

    @field_validator("issues", mode="before")
    @classmethod
    def coerce_issues(cls, value: object) -> list[object]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        if isinstance(value, dict):
            return [value]
        return value  # type: ignore[return-value]

    @field_validator("recommended_revision", mode="before")
    @classmethod
    def coerce_recommended_revision(cls, value: object) -> str:
        if isinstance(value, list):
            return " ".join(str(item) for item in value)
        return str(value or "")


class EvidenceCheckerOutput(BaseModel):
    sample_id: str
    agent_role: str = "evidence_checker"
    round: int
    evidence: list[EvidenceItem] = Field(default_factory=list)
    recommended_revision: str = ""

    @field_validator("evidence", mode="before")
    @classmethod
    def coerce_evidence(cls, value: object) -> list[object]:
        if value is None:
            return []
        if isinstance(value, str):
            return [{"claim": value, "source": "đề bài", "status": "UNCERTAIN"}]
        if isinstance(value, dict):
            return [value]
        if isinstance(value, list):
            return [
                {"claim": item, "source": "đề bài", "status": "UNCERTAIN"}
                if isinstance(item, str)
                else item
                for item in value
            ]
        return value  # type: ignore[return-value]

    @field_validator("recommended_revision", mode="before")
    @classmethod
    def coerce_recommended_revision(cls, value: object) -> str:
        if isinstance(value, list):
            return " ".join(str(item) for item in value)
        return str(value or "")


class JudgeOutput(BaseModel):
    sample_id: str
    final_answer: str
    selected_reasoning_id: str | None = None
    decision_reason: str
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("decision_reason", mode="before")
    @classmethod
    def coerce_decision_reason(cls, value: object) -> str:
        if isinstance(value, list):
            return " ".join(str(item) for item in value)
        return str(value or "")

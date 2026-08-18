"""Canonical dataset sample schema."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Choice(BaseModel):
    label: str
    text: str


class Sample(BaseModel):
    sample_id: str
    dataset: str
    question: str
    choices: list[Choice]
    answer: str
    context: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)

    def prompt_text(self) -> str:
        choices = "\n".join(f"{choice.label}. {choice.text}" for choice in self.choices)
        context = f"Ngữ cảnh:\n{self.context}\n\n" if self.context else ""
        return f"{context}Câu hỏi:\n{self.question}\n\nCác lựa chọn:\n{choices}"

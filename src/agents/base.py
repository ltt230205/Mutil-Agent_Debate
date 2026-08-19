"""Agent wrappers enforcing JSON contracts."""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from src.agents.llm_client import LlmClient, LlmResponse, parse_model_json
from src.schemas.agent_outputs import CritiqueOutput, EvidenceCheckerOutput, JudgeOutput, SolverOutput
from src.schemas.dataset import Sample


T = TypeVar("T", bound=BaseModel)


class Agent:
    def __init__(self, role: str, prompt_path: str | Path, client: LlmClient) -> None:
        self.role = role
        self.system_prompt = Path(prompt_path).read_text(encoding="utf-8")
        self.client = client

    def run(self, sample: Sample, round_id: int, context: dict[str, Any] | None = None) -> tuple[BaseModel, LlmResponse]:
        base_context = dict(context or {})
        total_input_tokens = 0
        total_output_tokens = 0
        total_latency = 0.0
        all_cached = True
        last_error: Exception | None = None

        for attempt in range(1, 3):
            attempt_context = dict(base_context)
            if last_error is not None:
                attempt_context["schema_retry"] = attempt
                attempt_context["format_correction"] = (
                    "Phản hồi trước không đúng JSON contract. Hãy trả về đúng một JSON object "
                    "với đầy đủ trường bắt buộc và đúng kiểu dữ liệu."
                )
            user_prompt = build_user_prompt(sample, round_id, attempt_context)
            response = self.client.complete_json(self.system_prompt, user_prompt, self.role)
            total_input_tokens += response.usage.input_tokens
            total_output_tokens += response.usage.output_tokens
            total_latency += response.latency_seconds
            all_cached = all_cached and response.cached
            try:
                model = self._validate(response.content)
                combined = LlmResponse(
                    content=response.content,
                    usage=type(response.usage)(total_input_tokens, total_output_tokens),
                    latency_seconds=total_latency,
                    cached=all_cached,
                )
                return model, combined
            except (ValueError, ValidationError) as exc:
                last_error = exc

        raise ValueError(f"Invalid {self.role} JSON after schema retry: {last_error}")

    def _validate(self, content: str) -> BaseModel:
        parsed = parse_model_json(content)
        schema: type[BaseModel]
        if self.role in {"solver", "revision"}:
            schema = SolverOutput
        elif self.role in {"critic", "skeptic"}:
            schema = CritiqueOutput
        elif self.role == "evidence_checker":
            schema = EvidenceCheckerOutput
        else:
            schema = JudgeOutput
        try:
            return schema.model_validate(parsed)
        except ValidationError as exc:
            raise ValueError(f"Invalid {self.role} JSON: {exc}") from exc


def build_user_prompt(sample: Sample, round_id: int, context: dict[str, Any]) -> str:
    pieces = [
        f"sample_id={sample.sample_id}",
        f"dataset={sample.dataset}",
        f"round={round_id}",
        sample.prompt_text(),
    ]
    if context:
        pieces.append("Trạng thái debate trước đó ở dạng JSON:")
        pieces.append(str(context))
    return "\n\n".join(pieces)

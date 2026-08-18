"""LLM client with OpenAI and deterministic mock modes."""

from __future__ import annotations

import json
import os
import random
import time
from dataclasses import dataclass
from typing import Any

from openai import OpenAI

from src.utils.cache import JsonlCache, cache_key
from src.utils.json import parse_json_object


@dataclass
class LlmUsage:
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class LlmResponse:
    content: str
    usage: LlmUsage
    latency_seconds: float
    cached: bool = False


class LlmClient:
    """Small OpenAI-compatible client.

    The API key is read only from environment variables. Dry-run mode returns
    deterministic JSON so tests and pipeline checks do not incur model cost.
    """

    def __init__(
        self,
        model: str,
        cache: JsonlCache,
        dry_run: bool = True,
        temperature: float = 0.2,
        max_output_tokens: int = 700,
        max_attempts: int = 3,
        backoff_seconds: float = 2.0,
        min_delay_seconds: float = 0.2,
        seed: int = 42,
    ) -> None:
        self.model = model
        self.cache = cache
        self.dry_run = dry_run
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        self.max_attempts = max_attempts
        self.backoff_seconds = backoff_seconds
        self.min_delay_seconds = min_delay_seconds
        self.random = random.Random(seed)
        self._client = None if dry_run else OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self._last_call = 0.0

    def complete_json(self, system_prompt: str, user_prompt: str, role: str) -> LlmResponse:
        request = {
            "model": self.model,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "role": role,
            "temperature": self.temperature,
            "max_output_tokens": self.max_output_tokens,
        }
        key = cache_key(request)
        cached = self.cache.get(key)
        if cached:
            return LlmResponse(
                content=cached["content"],
                usage=LlmUsage(**cached["usage"]),
                latency_seconds=cached["latency_seconds"],
                cached=True,
            )
        if self.dry_run:
            response = self._mock_response(user_prompt, role)
        else:
            response = self._openai_response(system_prompt, user_prompt)
        self.cache.set(
            key,
            {
                "content": response.content,
                "usage": response.usage.__dict__,
                "latency_seconds": response.latency_seconds,
                "model": self.model,
                "role": role,
            },
        )
        return response

    def _openai_response(self, system_prompt: str, user_prompt: str) -> LlmResponse:
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY is required when dry_run=false.")
        assert self._client is not None
        for attempt in range(1, self.max_attempts + 1):
            try:
                elapsed = time.time() - self._last_call
                if elapsed < self.min_delay_seconds:
                    time.sleep(self.min_delay_seconds - elapsed)
                start = time.time()
                completion = self._client.chat.completions.create(
                    model=self.model,
                    temperature=self.temperature,
                    max_tokens=self.max_output_tokens,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                )
                self._last_call = time.time()
                usage = completion.usage
                return LlmResponse(
                    content=completion.choices[0].message.content or "{}",
                    usage=LlmUsage(
                        input_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,
                        output_tokens=getattr(usage, "completion_tokens", 0) if usage else 0,
                    ),
                    latency_seconds=time.time() - start,
                )
            except Exception:
                if attempt == self.max_attempts:
                    raise
                time.sleep(self.backoff_seconds * attempt)
        raise RuntimeError("Unreachable retry state.")

    def _mock_response(self, user_prompt: str, role: str) -> LlmResponse:
        start = time.time()
        sample_id = _extract_between(user_prompt, "sample_id=", "\n") or "mock_sample"
        labels = _extract_choice_labels(user_prompt) or ["A", "B", "C", "D", "E"]
        chosen = labels[abs(hash((user_prompt, role))) % len(labels)]
        if role in {"solver", "revision"}:
            payload: dict[str, Any] = {
                "sample_id": sample_id,
                "agent_role": "solver",
                "round": _extract_round(user_prompt),
                "answer": chosen,
                "rationale_summary": [
                    "Lập luận chạy thử được tạo từ câu hỏi hiển thị.",
                    "Đây là dữ liệu mô phỏng xác định để kiểm tra quy trình.",
                ],
                "evidence": [{"claim": "Nhận định mô phỏng dùng để kiểm tra định dạng.", "source": "đề bài", "status": "UNCERTAIN"}],
                "confidence": 0.55,
            }
        elif role in {"critic", "skeptic"}:
            payload = {
                "sample_id": sample_id,
                "agent_role": role,
                "round": _extract_round(user_prompt),
                "issues": [
                    {
                        "type": "MISSING_EVIDENCE",
                        "target_step": 1,
                        "description": "Vấn đề chạy thử dùng để kiểm tra luồng phản biện.",
                        "severity": "MEDIUM",
                    }
                ],
                "recommended_revision": "Hãy kiểm tra lại lựa chọn dựa trên tất cả tiền đề.",
            }
        elif role == "evidence_checker":
            payload = {
                "sample_id": sample_id,
                "agent_role": "evidence_checker",
                "round": _extract_round(user_prompt),
                "evidence": [{"claim": "Nhận định mô phỏng dùng để kiểm tra bằng chứng.", "source": "đề bài", "status": "UNCERTAIN"}],
                "recommended_revision": "Ưu tiên các claim được hỗ trợ trực tiếp bởi đề bài.",
            }
        else:
            payload = {
                "sample_id": sample_id,
                "final_answer": chosen,
                "selected_reasoning_id": None,
                "decision_reason": "Quyết định chạy thử của Judge dùng để kiểm tra quy trình.",
                "confidence": 0.56,
            }
        content = json.dumps(payload, ensure_ascii=False)
        tokens = max(1, len(system_safe(user_prompt).split()))
        return LlmResponse(content=content, usage=LlmUsage(tokens, len(content.split())), latency_seconds=time.time() - start)


def _extract_between(text: str, prefix: str, suffix: str) -> str | None:
    start = text.find(prefix)
    if start < 0:
        return None
    start += len(prefix)
    end = text.find(suffix, start)
    return text[start:] if end < 0 else text[start:end]


def _extract_choice_labels(text: str) -> list[str]:
    labels: list[str] = []
    for line in text.splitlines():
        if len(line) > 2 and line[1:3] == ". " and line[0].isalnum():
            labels.append(line[0])
    return labels


def _extract_round(text: str) -> int:
    marker = "round="
    pos = text.find(marker)
    if pos < 0:
        return 0
    fragment = text[pos + len(marker) :].split()[0]
    return int("".join(ch for ch in fragment if ch.isdigit()) or "0")


def system_safe(text: str) -> str:
    return text.replace("\x00", "")


def parse_model_json(text: str) -> dict[str, Any]:
    return parse_json_object(text)

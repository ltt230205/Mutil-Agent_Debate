"""JSON parsing helpers for model responses."""

from __future__ import annotations

import json
import re
from typing import Any


JSON_BLOCK = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def parse_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    match = JSON_BLOCK.search(stripped)
    if match:
        stripped = match.group(1).strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end >= start:
        stripped = stripped[start : end + 1]
    return json.loads(stripped)

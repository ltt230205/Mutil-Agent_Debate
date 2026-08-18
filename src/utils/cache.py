"""JSONL response cache."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def cache_key(payload: dict[str, Any]) -> str:
    stable = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()


class JsonlCache:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._items: dict[str, dict[str, Any]] = {}
        if self.path.exists():
            with self.path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if line.strip():
                        item = json.loads(line)
                        self._items[item["cache_key"]] = item

    def get(self, key: str) -> dict[str, Any] | None:
        return self._items.get(key)

    def set(self, key: str, value: dict[str, Any]) -> None:
        item = {"cache_key": key, **value}
        self._items[key] = item
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")

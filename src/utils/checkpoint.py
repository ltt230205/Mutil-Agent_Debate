"""Small JSONL checkpoint helpers for resumable experiment scripts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import IO, Any


RecordKey = tuple[int, str, str]


def record_key(record: dict[str, Any]) -> RecordKey:
    """Return the stable identity of one prediction record."""
    return (int(record["seed"]), str(record["sample_id"]), str(record["method"]))


def open_resumable_jsonl(
    path: str | Path,
    *,
    overwrite: bool,
    resume: bool,
) -> tuple[IO[str], set[RecordKey]]:
    """Open a JSONL output and return keys already completed."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)

    if output.exists() and overwrite:
        return output.open("w", encoding="utf-8"), set()
    if output.exists() and not resume:
        raise FileExistsError(
            f"{output} exists. Set runtime.resume=true, runtime.overwrite=true, or use a new output_dir."
        )

    completed: set[RecordKey] = set()
    if output.exists():
        with output.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    completed.add(record_key(json.loads(line)))
                except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                    raise ValueError(f"Invalid checkpoint line {line_number} in {output}: {exc}") from exc
        return output.open("a", encoding="utf-8"), completed

    return output.open("w", encoding="utf-8"), completed


def write_checkpoint(handle: IO[str], record: dict[str, Any]) -> None:
    """Append one prediction record and flush it for interruption safety."""
    handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    handle.flush()

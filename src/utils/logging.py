"""Structured logging helpers."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
        }
        if hasattr(record, "extra_payload"):
            payload.update(getattr(record, "extra_payload"))
        return json.dumps(payload, ensure_ascii=False)


def setup_logger(log_path: str | Path) -> logging.Logger:
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("mad_research")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.addHandler(logging.StreamHandler())
    return logger


def log_event(logger: logging.Logger, message: str, **payload: Any) -> None:
    logger.info(message, extra={"extra_payload": payload})

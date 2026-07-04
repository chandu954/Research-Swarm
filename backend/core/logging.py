"""Structured JSON logging configuration."""
from __future__ import annotations
import os
import sys
import json
import logging
from datetime import datetime, timezone
from typing import Any
from loguru import logger


_initialized = False


class JSONFormatter:
    """Formats log records as JSON lines for machine parsing."""

    def __call__(self, record: dict[str, Any]) -> str:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record["level"].name,
            "logger": record["name"],
            "module": record["module"],
            "function": record["function"],
            "line": record["line"],
            "message": record["message"],
        }
        extra = record.get("extra", {})
        if extra:
            entry["extra"] = extra
        if record.get("exception"):
            entry["exception"] = str(record["exception"])
        return json.dumps(entry, default=str)


def setup_logging(*, json_format: bool | None = None) -> None:
    """Configure loguru with structured JSON or human-readable output.

    Args:
        json_format: If True, output JSON. If None, reads LOG_FORMAT env var
            (defaults to False for dev).
    """
    global _initialized
    if _initialized:
        return

    use_json = json_format if json_format is not None else os.getenv("LOG_FORMAT", "text").lower() == "json"

    logger.remove()

    if use_json:
        logger.add(sys.stdout, serialize=True)
    else:
        logger.add(
            sys.stdout,
            format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            colorize=True,
        )

    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logger.add(
        "./data/logs/research-swarm.log",
        serialize=True,
        rotation="100 MB",
        retention=7,
        level=log_level,
    )

    # Bridge Python stdlib logging to loguru
    class InterceptHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            level = logger.level(record.levelname).name
            logger.opt(depth=6, exception=record.exc_info).log(level, record.getMessage())

    logging.basicConfig(handlers=[InterceptHandler()], level=logging.WARNING, force=True)

    _initialized = True
    logger.info(f"Logging configured — format={'json' if use_json else 'text'}, level={log_level}")

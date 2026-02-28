# utils/logger.py
# AdaptLab — Structured JSON logger used by every module.
# Imports from: nothing (zero internal dependencies by design).

import logging
import json
import sys
import traceback
from datetime import datetime, timezone
from typing import Any


class JSONFormatter(logging.Formatter):
    """
    Formats every log record as a single-line JSON object.
    Fields: timestamp, level, component, event, and any extra kwargs.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_obj: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level":     record.levelname,
            "component": getattr(record, "component", record.name),
            "event":     record.getMessage(),
        }

        # Attach any extra structured fields passed via `extra=`
        reserved = {
            "name", "msg", "args", "levelname", "levelno", "pathname",
            "filename", "module", "exc_info", "exc_text", "stack_info",
            "lineno", "funcName", "created", "msecs", "relativeCreated",
            "thread", "threadName", "processName", "process", "message",
            "component",
        }
        for key, value in record.__dict__.items():
            if key not in reserved:
                log_obj[key] = value

        # Attach exception info if present
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        elif record.exc_text:
            log_obj["exception"] = record.exc_text

        return json.dumps(log_obj, default=str)


def get_logger(component: str) -> "AdaptLabLogger":
    """
    Factory function. Every module calls get_logger(__name__) or
    get_logger("component_name") to obtain its logger.

    Usage:
        from utils.logger import get_logger
        log = get_logger("capability_engine")
        log.info("score_updated", student_id="s1", concept="loops", new_score=0.62)
    """
    return AdaptLabLogger(component)


class AdaptLabLogger:
    """
    Thin wrapper around stdlib Logger that:
    - Enforces JSON-only output
    - Injects `component` into every record
    - Exposes structured log methods (info, warning, error, debug, critical)
    - Accepts arbitrary kwargs as structured fields
    """

    def __init__(self, component: str) -> None:
        self.component = component
        self._logger = logging.getLogger(f"adaptlab.{component}")

        if not self._logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(JSONFormatter())
            self._logger.addHandler(handler)
            self._logger.setLevel(logging.DEBUG)
            self._logger.propagate = False

    def _make_extra(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        kwargs["component"] = self.component
        return kwargs

    def info(self, event: str, **kwargs: Any) -> None:
        self._logger.info(event, extra=self._make_extra(kwargs))

    def debug(self, event: str, **kwargs: Any) -> None:
        self._logger.debug(event, extra=self._make_extra(kwargs))

    def warning(self, event: str, **kwargs: Any) -> None:
        self._logger.warning(event, extra=self._make_extra(kwargs))

    def error(self, event: str, **kwargs: Any) -> None:
        self._logger.error(event, extra=self._make_extra(kwargs))

    def critical(self, event: str, **kwargs: Any) -> None:
        self._logger.critical(event, extra=self._make_extra(kwargs))

    def exception(self, event: str, **kwargs: Any) -> None:
        """Logs ERROR level with full traceback attached automatically."""
        kwargs["component"] = self.component
        kwargs["traceback"] = traceback.format_exc()
        self._logger.error(event, extra=kwargs)


# ─────────────────────────────────────────────
# Module-level root logger for one-off use
# ─────────────────────────────────────────────
_root_handler = logging.StreamHandler(sys.stdout)
_root_handler.setFormatter(JSONFormatter())
logging.root.setLevel(logging.DEBUG)
if not logging.root.handlers:
    logging.root.addHandler(_root_handler)

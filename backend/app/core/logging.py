"""Structured JSON logging with configurable levels and retention."""

import json
import logging
import sys
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# Log retention: maximum log level for production to control volume
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# Sensitive fields that should never be logged
SENSITIVE_FIELDS = {
    "password",
    "token",
    "refresh_token",
    "access_token",
    "api_key",
    "secret",
    "authorization",
    "cookie",
    "credit_card",
    "ssn",
    "hashed_password",
    "mfa_secret",
}


def _sanitize_value(key: str, value: Any) -> Any:
    """Redact sensitive values from log records."""
    key_lower = key.lower()
    if any(s in key_lower for s in SENSITIVE_FIELDS):
        return "***REDACTED***"
    return value


def _sanitize_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively sanitize a dictionary for safe logging."""
    if not isinstance(data, dict):
        return data
    result = {}
    for key, value in data.items():
        if isinstance(value, dict):
            result[key] = _sanitize_dict(value)
        elif isinstance(value, list):
            result[key] = [
                _sanitize_dict(v) if isinstance(v, dict) else _sanitize_value(key, v)
                for v in value
            ]
        else:
            result[key] = _sanitize_value(key, value)
    return result


class JSONFormatter(logging.Formatter):
    """Emit structured JSON log lines compatible with Fluentd/CloudWatch."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "event": getattr(record, "event", record.msg),
        }

        # Add request ID if available
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id

        # Add extra fields from record
        for key, value in record.__dict__.items():
            if key not in (
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "message",
                "asctime",
                "event",
                "request_id",
            ):
                log_entry[key] = value

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Sanitize before output
        log_entry = _sanitize_dict(log_entry)
        return json.dumps(log_entry, default=str)


class StructLogger:
    """Wrapper around logging.Logger that supports keyword arguments for structured logging.

    Usage:
        logger = get_logger(__name__)
        logger.info("user_login", user_id="123", ip="1.2.3.4")
    """

    def __init__(self, logger: logging.Logger):
        self._logger = logger

    def _log(self, level: int, msg: str, **kwargs: Any) -> None:
        extra = {"event": msg}
        extra.update(kwargs)
        self._logger.log(level, msg, extra=extra)

    def debug(self, msg: str, **kwargs: Any) -> None:
        self._log(logging.DEBUG, msg, **kwargs)

    def info(self, msg: str, **kwargs: Any) -> None:
        self._log(logging.INFO, msg, **kwargs)

    def warning(self, msg: str, **kwargs: Any) -> None:
        self._log(logging.WARNING, msg, **kwargs)

    def error(self, msg: str, **kwargs: Any) -> None:
        self._log(logging.ERROR, msg, **kwargs)

    def critical(self, msg: str, **kwargs: Any) -> None:
        self._log(logging.CRITICAL, msg, **kwargs)

    def exception(self, msg: str, **kwargs: Any) -> None:
        extra = {"event": msg}
        extra.update(kwargs)
        self._logger.exception(msg, extra=extra)

    # Expose underlying logger methods for compatibility
    @property
    def name(self) -> str:
        return self._logger.name

    def isEnabledFor(self, level: int) -> bool:
        return self._logger.isEnabledFor(level)


def configure_logging() -> None:
    """Configure root logger for structured JSON output."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())

    root_logger = logging.getLogger()
    root_logger.handlers = []
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str) -> StructLogger:
    """Get a structured logger instance."""
    return StructLogger(logging.getLogger(name))

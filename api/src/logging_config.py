"""Logging setup."""

from __future__ import annotations

import json
import logging
import logging.config
import os
from typing import Any

from flask import g, has_request_context


class RequestIdFilter(logging.Filter):
    """Inject %(request_id)s for log formats, falling back to "-" outside request
    contexts."""

    def filter(self, record: logging.LogRecord) -> bool:
        if has_request_context():
            record.request_id = getattr(g, "request_id", "-")
        else:
            record.request_id = "-"
        return True


class JsonFormatter(logging.Formatter):
    """One JSON object per record, so a log pipeline indexes fields directly."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, "request_id", "-"),
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def build_logging_config() -> dict[str, Any]:
    """Build logging config for gunicorn (not applied directly)."""
    resolved = os.environ.get("LOG_LEVEL", "INFO").upper()
    env = os.environ.get("ENVIRONMENT", "production").strip().lower()
    log_format = (
        os.environ.get("LOG_FORMAT") or ("json" if env == "production" else "text")
    ).lower()
    handler_formatter = "json" if log_format == "json" else "default"

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "request_id": {"()": "src.logging_config.RequestIdFilter"},
        },
        "formatters": {
            "default": {
                "format": (
                    "[%(asctime)s] %(levelname)s %(name)s "
                    "[req=%(request_id)s] %(message)s"
                ),
                "datefmt": "%Y-%m-%dT%H:%M:%S%z",
            },
            "json": {"()": "src.logging_config.JsonFormatter"},
        },
        "handlers": {
            "stderr": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stderr",
                "formatter": handler_formatter,
                "filters": ["request_id"],
            },
        },
        "root": {"level": resolved, "handlers": ["stderr"]},
        "loggers": {
            "werkzeug": {"level": "INFO"},
            "sqlalchemy.engine": {"level": "WARNING"},
            "flask_smorest": {"level": "INFO"},
            "gunicorn.access": {
                "level": "INFO",
                "handlers": ["stderr"],
                "propagate": False,
            },
            "gunicorn.error": {
                "level": resolved,
                "handlers": ["stderr"],
                "propagate": False,
            },
        },
    }


def configure_logging() -> None:
    """Apply logging config; safe to call multiple times (dictConfig replaces
    handlers)."""
    logging.config.dictConfig(build_logging_config())

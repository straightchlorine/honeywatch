"""Logging setup."""

from __future__ import annotations

import logging
import logging.config
import os
from typing import Any

from flask import g, has_request_context


class RequestIdFilter(logging.Filter):
    """Inject ``%(request_id)s`` into log records.

    Reads ``flask.g.request_id`` when a request is in flight (see
    :mod:`src.request_id`); otherwise emits ``-`` so the format string never
    raises on background / CLI log lines.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if has_request_context():
            record.request_id = getattr(g, "request_id", "-")
        else:
            record.request_id = "-"
        return True


_configured = False


def configure_logging(level: str | None = None) -> None:
    """Configure root + ``app`` + key library loggers via ``dictConfig``.

    Idempotent: callable from create_app, tests, CLI without doubling handlers.
    ``LOG_LEVEL`` env var overrides the default (INFO).
    """
    global _configured
    if _configured:
        return

    resolved = (level or os.environ.get("LOG_LEVEL", "INFO")).upper()

    config: dict[str, Any] = {
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
        },
        "handlers": {
            "stderr": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stderr",
                "formatter": "default",
                "filters": ["request_id"],
            },
        },
        "root": {"level": resolved, "handlers": ["stderr"]},
        "loggers": {
            "werkzeug": {"level": "INFO"},
            "sqlalchemy.engine": {"level": "WARNING"},
            "flask_smorest": {"level": "INFO"},
        },
    }
    logging.config.dictConfig(config)
    _configured = True

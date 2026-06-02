"""Logging setup."""

from __future__ import annotations

import json
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


class JsonFormatter(logging.Formatter):
    """Emit one JSON object per record so a log pipeline (Loki/ELK) can index
    ``request_id``, ``level``, ``logger`` and ``message`` without regex."""

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


def build_logging_config(level: str | None = None) -> dict[str, Any]:
    """Build the ``dictConfig`` dict for the API's structured logging.

    Returned (not applied) so gunicorn can hand it to its own
    ``logconfig_dict`` and route ``gunicorn.access`` / ``gunicorn.error``
    through the same JSON handler as the Flask app (see ``gunicorn.conf.py``),
    giving prod one structured log stream instead of two mismatched formats.

    ``LOG_LEVEL`` env var overrides the default (INFO); ``LOG_FORMAT`` /
    ``ENVIRONMENT`` choose json vs text.
    """
    resolved = (level or os.environ.get("LOG_LEVEL", "INFO")).upper()
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
            # Gunicorn installs its own plaintext handlers by default. Pin them
            # to the shared stderr/json handler (propagate=False so they don't
            # also bubble to root and double-log). The access line already
            # carries the request id via the access_log_format string; the
            # source IP (%(h)s) is deliberately dropped there.
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


def configure_logging(level: str | None = None) -> None:
    """Configure root + ``app`` + key library loggers via ``dictConfig``.

    Idempotent: ``dictConfig`` replaces (not appends) the root handler list, so
    calling this from create_app, tests, and CLI never doubles handlers.
    ``LOG_LEVEL`` env var overrides the default (INFO).
    """
    logging.config.dictConfig(build_logging_config(level))

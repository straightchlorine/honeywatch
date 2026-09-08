"""Unhandled exceptions must return clean 500 envelopes with no internals leaked; Flask
under TESTING propagates exceptions by default (bypassing @errorhandler), so we force
PROPAGATE_EXCEPTIONS=False to exercise the real production behavior."""

from __future__ import annotations

from typing import Any

import src.services.stats.activity as activity_mod


def test_unhandled_exception_returns_clean_500_envelope(
    app: Any, client: Any, monkeypatch: Any
) -> None:
    def boom(_db: Any) -> Any:
        raise RuntimeError("secret dsn=postgresql://u:p@h/db internal detail")

    monkeypatch.setattr(activity_mod, "totals", boom)
    app.config["PROPAGATE_EXCEPTIONS"] = False
    try:
        response = client.get("/api/v1/stats/totals")
    finally:
        # Restore default to prevent test pollution.
        app.config["PROPAGATE_EXCEPTIONS"] = None

    assert response.status_code == 500
    assert response.mimetype == "application/json"
    body = response.get_json()
    assert body["code"] == 500
    assert body["message"] == "An internal error occurred."

    blob = response.get_data(as_text=True)
    for leak in ("secret", "dsn=", "Traceback", "RuntimeError"):
        assert leak not in blob, f"500 body leaked {leak!r}: {blob}"

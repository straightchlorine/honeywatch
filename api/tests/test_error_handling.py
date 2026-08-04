"""Unhandled-exception path: a clean 500 envelope, no internals leaked.

Under `TESTING` Flask propagates exceptions by default, so the
`@errorhandler(Exception)` 500 branch is bypassed in the test client. We
force `PROPAGATE_EXCEPTIONS=False` to actually exercise it (the real
production behavior), mirroring how `test_health.py` simulates a DB outage.
"""

from __future__ import annotations

from typing import Any

import src.services.stats as stats_mod


def test_unhandled_exception_returns_clean_500_envelope(
    app: Any, client: Any, monkeypatch: Any
) -> None:
    def boom(_self: Any) -> Any:
        raise RuntimeError("secret dsn=postgresql://u:p@h/db internal detail")

    monkeypatch.setattr(stats_mod.StatsService, "totals", boom)
    app.config["PROPAGATE_EXCEPTIONS"] = False
    try:
        response = client.get("/api/v1/stats/totals")
    finally:
        # Restore Flask's default (None = auto: propagate under TESTING/DEBUG)
        # so this does not leak into other tests sharing the session app.
        app.config["PROPAGATE_EXCEPTIONS"] = None

    assert response.status_code == 500
    assert response.mimetype == "application/json"
    body = response.get_json()
    assert body["code"] == 500
    assert body["message"] == "An internal error occurred."

    blob = response.get_data(as_text=True)
    for leak in ("secret", "dsn=", "Traceback", "RuntimeError"):
        assert leak not in blob, f"500 body leaked {leak!r}: {blob}"

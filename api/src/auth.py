import functools
from typing import Any, cast

from flask import Response, current_app, request


def require_auth(f: Any) -> Any:
    @functools.wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        auth = request.authorization
        if not auth or not _check_credentials(auth.username, auth.password):
            return Response(
                '{"error": "Unauthorized"}',
                status=401,
                mimetype="application/json",
                headers={"WWW-Authenticate": 'Basic realm="honeywatch"'},
            )
        return f(*args, **kwargs)

    return decorated


def _check_credentials(username: str | None, password: str | None) -> bool:
    expected_user = cast(str, current_app.config["DASHBOARD_USER"])
    expected_pass = cast(str, current_app.config["DASHBOARD_PASSWORD"])
    return bool(username == expected_user and password == expected_pass)

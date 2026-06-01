from __future__ import annotations

# Canonical session classification, shared by the SQL filter (services/sessions),
# the marshmallow `category` validation/response field (schemas/sessions) and the
# serializer. The dashboard consumes the emitted `category` and only maps it to a
# label, so this module is the single source of truth for the partition.
#
# The classes are mutually exclusive and evaluated in priority order: a session
# that ran commands is "active" even if it also logged in, and so on.
SESSION_CATEGORIES: tuple[str, ...] = ("active", "login", "failed", "probe")


def classify_category(
    command_count: int,
    login_success: bool,
    auth_attempt_count: int,
) -> str:
    """Return the session class for the given per-session counters.

    Args:
        command_count: Number of shell commands recorded in the session.
        login_success: Whether any auth attempt in the session succeeded.
        auth_attempt_count: Number of authentication attempts in the session.

    Returns:
        One of :data:`SESSION_CATEGORIES`: ``"active"`` (ran commands),
        ``"login"`` (login accepted, no commands), ``"failed"`` (attempts made,
        none accepted), or ``"probe"`` (no login attempts).
    """
    if command_count > 0:
        return "active"
    if login_success:
        return "login"
    if auth_attempt_count > 0:
        return "failed"
    return "probe"

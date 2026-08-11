from __future__ import annotations

# Mutually exclusive, in priority order: a session that ran commands is
# "active" even though it also logged in, and so on down the list.
SESSION_CATEGORIES: tuple[str, ...] = ("active", "login", "failed", "probe")

CATEGORY_DESCRIPTION = (
    "Session class (mutually exclusive): 'active' ran a command, 'login' "
    "logged in without running one, 'failed' tried to log in but never "
    "succeeded, 'probe' never attempted a login."
)


def classify_category(
    command_count: int,
    login_success: bool,
    auth_attempt_count: int,
) -> str:
    """Return the SESSION_CATEGORIES entry matching these counters.

    Arguments:
      command_count: number of commands executed
      login_success: whether login succeeded
      auth_attempt_count: number of login attempts

    Returns:
      str — one of SESSION_CATEGORIES
    """
    if command_count > 0:
        return "active"
    if login_success:
        return "login"
    if auth_attempt_count > 0:
        return "failed"
    return "probe"

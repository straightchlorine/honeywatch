"""What the attackers try to log in with (Credentials page)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import BigInteger, case, cast, func, nulls_last, select, tuple_
from sqlalchemy.orm import Session as DbSession

from src.models.auth_attempt import AuthAttempt
from src.models.session import Session
from src.services.stats.common import DEFAULT_TOP_N, require_one_of, scope_to_country
from src.services.types import (
    AuthOutcomesDict,
    CharsetClassDict,
    CredentialLengthDict,
    PasswordCompositionDict,
    TopCredentialDict,
    TopPasswordDict,
)

VALID_CRED_GROUPINGS = frozenset({"pair", "username", "password"})
VALID_CRED_METRICS = frozenset({"attempts", "ip_fanout"})
VALID_CRED_OUTCOMES = frozenset({"any", "success", "failed"})

# Longer passwords all land in the top bucket of the length histogram.
PASSWORD_LENGTH_CAP = 16


def top_passwords(db: DbSession, top_n: int = DEFAULT_TOP_N) -> list[TopPasswordDict]:
    """Top-N passwords by attempt count, descending."""
    rows = db.execute(
        select(AuthAttempt.password, func.count().label("count"))
        .group_by(AuthAttempt.password)
        .order_by(func.count().desc())
        .limit(top_n)
    ).all()
    return [{"password": row[0], "count": row[1]} for row in rows]


def top_credentials(
    db: DbSession,
    by: str = "pair",
    metric: str = "attempts",
    outcome: str = "any",
    country: str | None = None,
    top_n: int = DEFAULT_TOP_N,
) -> list[TopCredentialDict]:
    """Top-N credentials, grouped and ranked by metric.

    Arguments:
      by: "pair" | "username" | "password"; the ungrouped field returns None
      metric: "attempts" (try count) or "ip_fanout" (distinct source IPs);
        ip_fanout sets distinct_ips, attempts leaves it None
      outcome: "any" | "success" | "failed"
      country: alpha-2 code or UNKNOWN_COUNTRY; filters to that geo bucket
      top_n: max results to return

    Returns:
      list of TopCredentialDict with username, password, count, distinct_ips (or None)

    Raises:
      ValueError: unrecognized by / metric / outcome
    """
    require_one_of(by, VALID_CRED_GROUPINGS, "by")
    require_one_of(metric, VALID_CRED_METRICS, "metric")
    require_one_of(outcome, VALID_CRED_OUTCOMES, "outcome")

    if by == "password":
        group_cols = [AuthAttempt.password]
    elif by == "pair":
        group_cols = [AuthAttempt.username, AuthAttempt.password]
    else:  # "username"
        group_cols = [AuthAttempt.username]

    # ip_fanout needs the source IP in scope: it pre-groups by
    # (credential, src_ip) below and counts the resulting rows.
    count_col = func.count().label("count")
    if metric == "ip_fanout":
        selected: list[Any] = [*group_cols, Session.src_ip, func.count().label("cnt")]
    else:
        selected = [*group_cols, count_col]

    stmt = select(*selected).select_from(AuthAttempt)
    if metric == "ip_fanout" or country is not None:
        stmt = stmt.join(Session, Session.id == AuthAttempt.session_id)
    stmt = scope_to_country(stmt, country)
    if outcome == "success":
        stmt = stmt.where(AuthAttempt.success.is_(True))
    elif outcome == "failed":
        stmt = stmt.where(AuthAttempt.success.is_(False))

    if metric == "ip_fanout":
        pre = stmt.group_by(*group_cols, Session.src_ip).subquery()
        pre_group = [pre.c[col.key] for col in group_cols]
        sum_col = cast(func.sum(pre.c.cnt), BigInteger).label("count")
        fanout_col = func.count().label("distinct_ips")
        stmt = (
            select(*pre_group, sum_col, fanout_col)
            .group_by(*pre_group)
            .order_by(fanout_col.desc(), sum_col.desc())
        )
    else:
        stmt = stmt.group_by(*group_cols).order_by(count_col.desc())
    stmt = stmt.limit(top_n)

    # Row layout is group_cols, count, then distinct_ips for ip_fanout.
    keys = [col.key for col in group_cols]
    out: list[TopCredentialDict] = []
    for row in db.execute(stmt).all():
        *grouped, count = row[: len(keys) + 1]
        values = dict(zip(keys, grouped))
        out.append(
            {
                "username": values.get("username"),
                "password": values.get("password"),
                "count": count,
                "distinct_ips": row[-1] if metric == "ip_fanout" else None,
            }
        )
    return out


def auth_outcomes(db: DbSession) -> AuthOutcomesDict:
    """Accept/reject split plus wordlist size across all auth attempts."""
    distinct_passwords = select(AuthAttempt.password).distinct().subquery()
    distinct_usernames = select(AuthAttempt.username).distinct().subquery()
    row = db.execute(
        select(
            select(func.count())
            .select_from(AuthAttempt)
            .scalar_subquery()
            .label("total"),
            select(func.count())
            .select_from(AuthAttempt)
            .where(AuthAttempt.success.is_(True))
            .scalar_subquery()
            .label("successful"),
            select(func.count())
            .select_from(distinct_passwords)
            .scalar_subquery()
            .label("unique_passwords"),
            select(func.count())
            .select_from(distinct_usernames)
            .scalar_subquery()
            .label("unique_usernames"),
        )
    ).one()
    total = row.total
    successful = row.successful
    failed = total - successful
    success_rate = round(successful / total * 100, 2) if total else None
    return {
        "total": total,
        "successful": successful,
        "failed": failed,
        "success_rate": success_rate,
        "unique_passwords": row.unique_passwords,
        "unique_usernames": row.unique_usernames,
    }


def password_composition(db: DbSession) -> PasswordCompositionDict:
    """Length histogram and charset-class breakdown of attempted passwords.

    Both breakdowns come from one grouping-sets query (same attempt set).
    Lengths capped at PASSWORD_LENGTH_CAP.

    Arguments:
      db: database session

    Returns:
      dict with total, capped_at, lengths (list), classes (list)
    """
    pw = (
        select(AuthAttempt.password, func.count().label("cnt"))
        .group_by(AuthAttempt.password)
        .cte("pw")
    )
    password = pw.c.password
    length_expr = func.least(func.char_length(password), PASSWORD_LENGTH_CAP).label(
        "length"
    )
    charset = case(
        (func.char_length(password) == 0, "empty"),
        (password.op("~")("[^A-Za-z0-9]"), "symbol"),
        (password.op("~")("^[0-9]+$"), "digits"),
        (password.op("~")("^[a-z]+$"), "lower"),
        (password.op("~")("^[A-Z]+$"), "upper"),
        else_="alnum",
    ).label("name")
    count_col = cast(func.sum(pw.c.cnt), BigInteger).label("count")
    rows = db.execute(
        select(length_expr, charset, count_col)
        .group_by(func.grouping_sets(tuple_(length_expr), tuple_(charset)))
        .order_by(nulls_last(length_expr), count_col.desc())
    ).all()
    # Grouping sets interleave both breakdowns; a null length marks the
    # charset-class rows.
    lengths: list[CredentialLengthDict] = [
        {"length": int(r[0]), "count": r[2]} for r in rows if r[0] is not None
    ]
    classes: list[CharsetClassDict] = [
        {"name": r[1], "count": r[2]} for r in rows if r[0] is None
    ]
    total = sum(c["count"] for c in classes)
    return {
        "total": total,
        "capped_at": PASSWORD_LENGTH_CAP,
        "lengths": lengths,
        "classes": classes,
    }


def passwords_by_length(
    db: DbSession, length: int, top_n: int = DEFAULT_TOP_N
) -> list[TopPasswordDict]:
    """Top-N passwords of a given length (histogram drill-down).

    At PASSWORD_LENGTH_CAP, matches length-or-longer to align with password_composition.

    Arguments:
      db: database session
      length: target length; ≥PASSWORD_LENGTH_CAP includes all longer passwords
      top_n: max results to return

    Returns:
      list of TopPasswordDict with password and count
    """
    length_col = func.char_length(AuthAttempt.password)
    predicate = (
        length_col >= length if length >= PASSWORD_LENGTH_CAP else length_col == length
    )
    rows = db.execute(
        select(AuthAttempt.password, func.count().label("count"))
        .where(predicate)
        .group_by(AuthAttempt.password)
        .order_by(func.count().desc())
        .limit(top_n)
    ).all()
    return [{"password": row[0], "count": row[1]} for row in rows]

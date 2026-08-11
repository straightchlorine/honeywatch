"""Asserts ORM models and migrated schema stay in sync for ssh_clients,
client_fingerprints, and direct_tcpip_requests.

Drift fails CI here rather than silently at runtime.
"""

from __future__ import annotations

import pytest
from sqlalchemy import String, text
from sqlalchemy.orm import Session

from src.extensions import Base
from src.models.client_fingerprint import ClientFingerprint
from src.models.direct_tcpip import DirectTcpipRequest
from src.models.ssh_client import SshClient

_NEW_MODELS: list[type[Base]] = [SshClient, ClientFingerprint, DirectTcpipRequest]


@pytest.mark.parametrize("model", _NEW_MODELS, ids=lambda m: m.__tablename__)
def test_new_model_columns_match_migrated_schema(
    db_session: Session, model: type[Base]
) -> None:
    table = model.__tablename__
    rows = db_session.execute(
        text(
            "SELECT column_name, character_maximum_length "
            "FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND table_name = :t"
        ),
        {"t": table},
    ).fetchall()
    assert rows, f"{table} is missing from the migrated schema"
    db_cols = {row[0]: row[1] for row in rows}

    model_cols = {col.name for col in model.__table__.columns}
    assert model_cols == set(db_cols), (
        f"{table}: model columns {model_cols} != schema columns {set(db_cols)}. "
        f"Model and migration drifted."
    )

    for col in model.__table__.columns:
        if isinstance(col.type, String) and col.type.length is not None:
            assert db_cols[col.name] == col.type.length, (
                f"{table}.{col.name}: model String({col.type.length}) "
                f"!= DB varchar({db_cols[col.name]})"
            )

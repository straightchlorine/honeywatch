"""split the wide ssh_clients table into ssh_client_profiles + a narrow ssh_clients

Revision ID: a3c5e7f9b1d4
Revises: b8f3e6a1d942
Create Date: 2026-10-14 12:00:00.000000

Each ssh_clients row carried ~1.2 kB of hassh and algorithm lists, but only a
few hundred distinct values exist across all sessions. They now live once in
ssh_client_profiles; ssh_clients keeps (session_id, client_version, profile_id,
first_seen). The API only ever read client_version, and the Sessions layout
pass joins this table over every session, so it shrinks from ~1.1 GB to ~100 MB.

The rewrite is one transaction. The copy runs under a SHARE lock (readers carry
on, ingestor writes wait, none are lost); only the swap at the end takes ACCESS
EXCLUSIVE. The old table is dropped, which returns its space to the OS. The
downgrade rebuilds the wide table losslessly from the profiles.

profile `digest` is md5(row(<the seven columns>)::text), the same expression the
ingestor's upsert uses, so a profile written before and after this migration is
the same row.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "a3c5e7f9b1d4"
down_revision: Union[str, Sequence[str], None] = "b8f3e6a1d942"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PROFILE_COLS = (
    "hassh, hassh_algorithms, kex_algorithms, key_algorithms, "
    "encryption_algorithms, mac_algorithms, compression_algorithms"
)
_W_COLS = ", ".join(f"w.{c}" for c in _PROFILE_COLS.split(", "))
_P_COLS = ", ".join(f"p.{c}" for c in _PROFILE_COLS.split(", "))


def upgrade() -> None:
    # SHARE: readers carry on, the ingestor's writes wait. The copy below is the
    # slow part; the ACCESS EXCLUSIVE rename at the end is brief.
    op.execute("LOCK TABLE ssh_clients IN SHARE MODE")
    # One md5 pass over the wide rows; everything after joins on the digest.
    op.execute(
        f"""
        CREATE TEMP TABLE _digests ON COMMIT DROP AS
        SELECT session_id, md5(row({_PROFILE_COLS})::text) AS digest,
               num_nonnulls({_PROFILE_COLS}) > 0 AS has_profile
        FROM ssh_clients
        """
    )
    op.execute(
        """
        CREATE TABLE ssh_client_profiles (
            id serial PRIMARY KEY,
            digest varchar(32) NOT NULL UNIQUE,
            hassh varchar(64),
            hassh_algorithms varchar(1024),
            kex_algorithms text,
            key_algorithms text,
            encryption_algorithms text,
            mac_algorithms text,
            compression_algorithms text
        )
        """
    )
    op.execute(
        f"""
        INSERT INTO ssh_client_profiles (digest, {_PROFILE_COLS})
        SELECT r.digest, {_W_COLS}
        FROM (SELECT DISTINCT ON (digest) digest, session_id
              FROM _digests WHERE has_profile ORDER BY digest, session_id) r
        JOIN ssh_clients w USING (session_id)
        """
    )
    op.execute(
        """
        CREATE TABLE ssh_clients_narrow AS
        SELECT w.session_id, w.client_version, p.id AS profile_id, w.first_seen
        FROM ssh_clients w
        JOIN _digests d USING (session_id)
        LEFT JOIN ssh_client_profiles p ON p.digest = d.digest
        """
    )
    op.execute(
        "ALTER TABLE ssh_clients_narrow "
        "ALTER COLUMN first_seen SET DEFAULT now(), "
        "ALTER COLUMN first_seen SET NOT NULL"
    )

    op.execute("DROP TABLE ssh_clients")
    op.execute("ALTER TABLE ssh_clients_narrow RENAME TO ssh_clients")
    op.execute(
        """
        ALTER TABLE ssh_clients
            ADD CONSTRAINT ssh_clients_pkey PRIMARY KEY (session_id),
            ADD CONSTRAINT ssh_clients_session_id_fkey
                FOREIGN KEY (session_id) REFERENCES sessions (id) ON DELETE CASCADE,
            ADD CONSTRAINT ssh_clients_profile_id_fkey
                FOREIGN KEY (profile_id) REFERENCES ssh_client_profiles (id)
        """
    )
    op.execute("ANALYZE ssh_clients")
    op.execute("ANALYZE ssh_client_profiles")


def downgrade() -> None:
    op.execute(
        """
        CREATE TABLE ssh_clients_wide (
            session_id varchar(64) PRIMARY KEY
                REFERENCES sessions (id) ON DELETE CASCADE,
            client_version varchar(256),
            hassh varchar(64),
            hassh_algorithms varchar(1024),
            kex_algorithms text,
            key_algorithms text,
            encryption_algorithms text,
            mac_algorithms text,
            compression_algorithms text,
            first_seen timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        f"""
        INSERT INTO ssh_clients_wide
            (session_id, client_version, {_PROFILE_COLS}, first_seen)
        SELECT c.session_id, c.client_version,
               {_P_COLS}, c.first_seen
        FROM ssh_clients c
        LEFT JOIN ssh_client_profiles p ON p.id = c.profile_id
        """
    )
    op.execute("DROP TABLE ssh_clients")
    op.execute("DROP TABLE ssh_client_profiles")
    op.execute("ALTER TABLE ssh_clients_wide RENAME TO ssh_clients")
    op.execute(
        "ALTER TABLE ssh_clients RENAME CONSTRAINT ssh_clients_wide_pkey "
        "TO ssh_clients_pkey"
    )
    op.execute(
        "ALTER TABLE ssh_clients RENAME CONSTRAINT ssh_clients_wide_session_id_fkey "
        "TO ssh_clients_session_id_fkey"
    )
    op.execute("CREATE INDEX ix_ssh_clients_hassh ON ssh_clients (hassh)")

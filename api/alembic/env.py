import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# Imported for the side effect: registers every table on Base.metadata.
from src import models  # noqa: F401
from src.extensions import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Read at migration time, not via src.config.Config: Config binds POSTGRES_* at
# import, and conftest re-points those vars at the test DB after that import.
pg_user = os.environ.get("POSTGRES_USER", "honeywatch")
pg_pass = os.environ.get("POSTGRES_PASSWORD", "testpass")
pg_host = os.environ.get("POSTGRES_HOST", "localhost")
pg_port = os.environ.get("POSTGRES_PORT", "5432")
pg_db = os.environ.get("POSTGRES_DB", "honeywatch")

database_url = f"postgresql+psycopg://{pg_user}:{pg_pass}@{pg_host}:{pg_port}/{pg_db}"
config.set_main_option("sqlalchemy.url", database_url)


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    raise SystemExit("offline (--sql) mode is not used in this project")
run_migrations_online()

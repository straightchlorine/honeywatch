import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

import src.models  # noqa: F401 - ensure all models are registered
from alembic import context
from src.extensions import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

pg_user = os.environ.get("POSTGRES_USER", "honeywatch")
pg_pass = os.environ.get("POSTGRES_PASSWORD", "changeme")
pg_host = os.environ.get("POSTGRES_HOST", "localhost")
pg_db = os.environ.get("POSTGRES_DB", "honeywatch")

database_url = f"postgresql+psycopg://{pg_user}:{pg_pass}@{pg_host}:5432/{pg_db}"
config.set_main_option("sqlalchemy.url", database_url)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


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
    run_migrations_offline()
else:
    run_migrations_online()

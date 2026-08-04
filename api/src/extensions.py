from flask import Flask, current_app, g
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def init_db(app: Flask, database_url: str) -> None:
    """Attach a SQLAlchemy engine and session factory to a Flask app.

    Args:
        app: The Flask application to attach the DB machinery to.
        database_url: SQLAlchemy-style connection URL.

    Returns:
        None. Sets `app.extensions['db_engine']` and
        `app.extensions['db_session_factory']`.
    """
    engine = create_engine(
        database_url,
        pool_size=5,
        max_overflow=5,
        pool_pre_ping=True,
        pool_recycle=1800,
    )
    app.extensions["db_engine"] = engine
    app.extensions["db_session_factory"] = sessionmaker(
        bind=engine, expire_on_commit=False
    )

    @app.teardown_appcontext
    def _close_db(_exc: BaseException | None) -> None:  # pyright: ignore[reportUnusedFunction]
        db: Session | None = g.pop("_db", None)
        if db is not None:
            db.close()


def get_session_factory() -> sessionmaker[Session]:
    """Return the session factory bound to the current Flask app.

    Returns:
        The `sessionmaker` stored on `current_app.extensions`.

    Raises:
        RuntimeError: If the DB was not initialized on this app.
    """
    factory = current_app.extensions.get("db_session_factory")
    if factory is None:
        raise RuntimeError(
            "Database is not initialized on this Flask app. "
            "Call init_db(app, database_url) in create_app()."
        )
    return factory


def get_db() -> Session:
    """Return the request-scoped SQLAlchemy session, created lazily on `g`.

    One read-only session per request, closed automatically at app-context
    teardown (registered in :func:`init_db`). Centralizes the per-request
    session so route handlers don't each manage a `with` block.
    """
    db: Session | None = getattr(g, "_db", None)
    if db is None:
        db = get_session_factory()()
        g._db = db
    return db

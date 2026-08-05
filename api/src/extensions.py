from flask import Flask, current_app, g
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def init_db(app: Flask, database_url: str) -> None:
    """Set up `db_engine` and `db_session_factory` on `app.extensions`.

    Also registers the teardown that closes the request-scoped session.
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
    """Session factory for the current app; raises if init_db never ran."""
    factory = current_app.extensions.get("db_session_factory")
    if factory is None:
        raise RuntimeError(
            "Database is not initialized on this Flask app. "
            "Call init_db(app, database_url) in create_app()."
        )
    return factory


def get_db() -> Session:
    """The request's SQLAlchemy session, opened on first use.

    One session per request, closed at app-context teardown, so handlers do not
    need their own `with` block.
    """
    db: Session | None = getattr(g, "_db", None)
    if db is None:
        db = get_session_factory()()
        g._db = db
    return db

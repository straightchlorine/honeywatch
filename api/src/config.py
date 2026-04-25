import os


def require_secret_key() -> str:
    """Resolve the Flask secret key, failing fast in production.

    The secret key is always read from ``FLASK_SECRET_KEY``. If unset, a
    known test value is returned only when either ``FLASK_ENV=development``
    or ``TESTING=1`` is set; otherwise a ``RuntimeError`` is raised.

    Returns:
        The secret key string.

    Raises:
        RuntimeError: If ``FLASK_SECRET_KEY`` is unset and no explicit
            development / testing flag is in the environment.
    """
    value = os.environ.get("FLASK_SECRET_KEY")
    if value:
        return value
    if os.environ.get("FLASK_ENV") == "development" or os.environ.get("TESTING") == "1":
        return "dev-only-insecure-key"
    raise RuntimeError(
        "FLASK_SECRET_KEY is not set. Set it in the environment, or set "
        "FLASK_ENV=development / TESTING=1 to use the insecure dev fallback."
    )


class Config:
    """Base application configuration.

    ``FLASK_SECRET_KEY`` must be set in the environment for any non-dev
    deployment; see :func:`require_secret_key`. The key is resolved when
    ``create_app`` calls :func:`apply_secret_key` so importing this module
    never fails on a missing env var.
    """

    TESTING = False

    POSTGRES_USER = os.environ.get("POSTGRES_USER", "honeywatch")
    POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "changeme")
    POSTGRES_DB = os.environ.get("POSTGRES_DB", "honeywatch")
    POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "localhost")

    SQLALCHEMY_DATABASE_URI = (
        f"postgresql+psycopg://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
        f"@{POSTGRES_HOST}:5432/{POSTGRES_DB}"
    )


class TestConfig(Config):
    """Test configuration.

    Forces ``TESTING=1`` into the environment so the test fallback secret
    key is acceptable, and points the database URI at ``TEST_DATABASE_URL``
    (or a localhost default).
    """

    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+psycopg://honeywatch:testpass@localhost:5432/honeywatch_test",
    )

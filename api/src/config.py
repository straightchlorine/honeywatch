import os

VALID_ENVS = ("development", "production")


def current_env() -> str:
    """Return the active deployment environment.

    Reads `ENVIRONMENT`; defaults to `production` so an unset deployment
    fails closed (e.g. forces a real `FLASK_SECRET_KEY`). Unrecognised
    values raise `RuntimeError`.
    """
    value = os.environ.get("ENVIRONMENT", "production").strip().lower()
    if value not in VALID_ENVS:
        raise RuntimeError(
            f"ENVIRONMENT={value!r} is invalid. Expected one of: "
            + ", ".join(VALID_ENVS)
        )
    return value


def _require_secret(env_var: str, dev_fallback: str) -> str:
    """Read `env_var`, falling back to a known-insecure value in development
    only; anywhere else, an unset value raises rather than booting insecurely."""
    value = os.environ.get(env_var)
    if value:
        return value
    if current_env() == "development":
        return dev_fallback
    raise RuntimeError(
        f"{env_var} is not set; refusing to start with the insecure default. "
        "Set it in the environment, or set ENVIRONMENT=development."
    )


def require_secret_key() -> str:
    """Resolve the Flask secret key, failing fast outside development."""
    return _require_secret("FLASK_SECRET_KEY", "dev-only-insecure-key")


def require_db_password() -> str:
    """Resolve the Postgres password, failing fast outside development."""
    return _require_secret("POSTGRES_PASSWORD", "changeme")


class Config:
    """Base application configuration.

    `FLASK_SECRET_KEY` must be set in the environment for any non-dev
    deployment; see :func:`require_secret_key`. The key is resolved when
    `create_app` calls :func:`require_secret_key` so importing this
    module never fails on a missing env var.
    """

    DEBUG = False
    TESTING = False

    POSTGRES_USER = os.environ.get("POSTGRES_USER", "honeywatch")
    POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "changeme")
    POSTGRES_DB = os.environ.get("POSTGRES_DB", "honeywatch")
    POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "localhost")
    POSTGRES_PORT = os.environ.get("POSTGRES_PORT", "5432")
    POSTGRES_SSLMODE = os.environ.get("POSTGRES_SSLMODE", "disable")

    SQLALCHEMY_DATABASE_URI = (
        f"postgresql+psycopg://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
        f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}?sslmode={POSTGRES_SSLMODE}"
    )


class DevelopmentConfig(Config):
    """Development configuration.

    `DEBUG` is intentionally NOT set in code (per Flask docs:
    https://flask.palletsprojects.com/en/stable/config/#DEBUG — setting
    it in code "may behave inconsistently"). Use `flask run --debug`
    or `FLASK_DEBUG=1` for the dev server.
    """


class TestingConfig(Config):
    """Testing configuration (opt-in via `create_app(TestingConfig)`).

    Not selected by `ENVIRONMENT`. Flask's `TESTING` flag is set so
    :attr:`flask.Flask.testing` is `True` and error handlers propagate
    exceptions. The database URI points at `TEST_DATABASE_URL` (or a
    localhost default).
    """

    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+psycopg://honeywatch:testpass@localhost:5432/honeywatch_test",
    )


_CONFIG_BY_ENV: dict[str, type[Config]] = {
    "development": DevelopmentConfig,
    "production": Config,
}


def select_config() -> type[Config]:
    """Pick the config class matching the current :func:`current_env`."""
    return _CONFIG_BY_ENV[current_env()]

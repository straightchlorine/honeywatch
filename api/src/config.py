import os

VALID_ENVS = ("development", "production")


def current_env() -> str:
    """Active deployment environment from `ENVIRONMENT`.

    Defaults to production so an unset deployment fails closed - that is what
    forces a real secret key. Unrecognised values raise RuntimeError.
    """
    value = os.environ.get("ENVIRONMENT", "production").strip().lower()
    if value not in VALID_ENVS:
        raise RuntimeError(
            f"ENVIRONMENT={value!r} is invalid. Expected one of: "
            + ", ".join(VALID_ENVS)
        )
    return value


def _require_secret(env_var: str, dev_fallback: str) -> str:
    """Read `env_var`; fall back to the insecure default in development only.

    Anywhere else an unset value raises rather than booting insecurely.
    """
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
    """Base configuration, also used as-is in production.

    The secret key is not a class attribute on purpose: create_app resolves it
    via require_secret_key, so importing this module never needs the env var.
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
    pass


class TestingConfig(Config):
    """Opt-in via create_app(TestingConfig); never selected by ENVIRONMENT.

    Points at TEST_DATABASE_URL, and TESTING lets error handlers propagate
    exceptions instead of swallowing them into a 500.
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
    """Config class for the current environment."""
    return _CONFIG_BY_ENV[current_env()]

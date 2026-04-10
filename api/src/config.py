import os


class Config:
    TESTING = False
    FLASK_SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key")
    SECRET_KEY = FLASK_SECRET_KEY

    POSTGRES_USER = os.environ.get("POSTGRES_USER", "honeywatch")
    POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "changeme")
    POSTGRES_DB = os.environ.get("POSTGRES_DB", "honeywatch")
    POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "localhost")

    SQLALCHEMY_DATABASE_URI = (
        f"postgresql+psycopg://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
        f"@{POSTGRES_HOST}:5432/{POSTGRES_DB}"
    )

    DASHBOARD_USER = os.environ.get("DASHBOARD_USER", "admin")
    DASHBOARD_PASSWORD = os.environ.get("DASHBOARD_PASSWORD", "admin")


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+psycopg://honeywatch:changeme@localhost:5432/honeywatch_test",
    )
    DASHBOARD_USER = "testuser"
    DASHBOARD_PASSWORD = "testpass"

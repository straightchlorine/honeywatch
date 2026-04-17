from flask import Flask

from src.routes.health import health_bp
from src.routes.sessions import api_bp


def register_blueprints(app: Flask) -> None:
    app.register_blueprint(health_bp)
    app.register_blueprint(api_bp)

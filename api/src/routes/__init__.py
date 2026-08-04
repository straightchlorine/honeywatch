from flask_smorest import Api

from src.routes.health import health_bp
from src.routes.sessions import sessions_bp
from src.routes.stats import stats_bp


def register_blueprints(smorest_api: Api) -> None:
    """Register blueprints on the flask-smorest `Api`.

    flask-smorest's `register_blueprint` mounts the blueprint on the Flask
    app and tracks it for OpenAPI introspection.
    """
    smorest_api.register_blueprint(health_bp)
    smorest_api.register_blueprint(sessions_bp)
    smorest_api.register_blueprint(stats_bp)

# backend/app/__init__.py
# Application factory. Cada modulo se registra como blueprint propio.

from flask import Flask
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy

from config import Config

db = SQLAlchemy()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)

    # CORS acotado a /api y a los origenes del .env, no a todo el server
    CORS(
        app,
        resources={r'/api/*': {'origins': app.config['CORS_ORIGINS']}},
        supports_credentials=True,
    )

    register_blueprints(app)

    return app


def register_blueprints(app):
    """Registra los blueprints de cada modulo bajo el prefijo /api."""
    from app.routes.health import health_bp

    app.register_blueprint(health_bp, url_prefix='/api')

    # Entrega 1: auth_bp, pacientes_bp, objetivos_bp, sesiones_bp,
    # evoluciones_bp se registran aca a medida que se implementen.

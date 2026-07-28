# backend/app/__init__.py
# Application factory. Cada modulo se registra como blueprint propio.

import logging

from flask import Flask, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import SQLAlchemyError

from config import Config

db = SQLAlchemy()


def create_app(config_class=Config):
    # Antes que nada: si faltan los secretos, la app no arranca. Ver
    # Config.validar() para el motivo.
    config_class.validar()

    app = Flask(__name__)
    app.config.from_object(config_class)

    configurar_logging(app)

    db.init_app(app)

    # CORS acotado a /api y a los origenes del .env, no a todo el server
    CORS(
        app,
        resources={r'/api/*': {'origins': app.config['CORS_ORIGINS']}},
        supports_credentials=True,
    )

    registrar_manejadores_de_error(app)
    register_blueprints(app)

    return app


def configurar_logging(app):
    """El log del servidor es donde van los errores crudos, no la respuesta."""
    nivel = logging.DEBUG if app.config.get('DEBUG') else logging.INFO
    logging.basicConfig(
        level=nivel,
        format='%(asctime)s %(levelname)s [%(name)s] %(message)s',
    )


def registrar_manejadores_de_error(app):
    """
    Traduce excepciones a JSON. Ver app/utils/errors.py para el criterio.

    Todas las respuestas de error del backend tienen la misma forma:
    {"mensaje": "...", "codigo": "..."} — asi el frontend las maneja en un
    solo lugar en vez de adivinar el formato segun el endpoint.
    """
    from app.utils.errors import ErrorAplicacion, traducir_error_db

    @app.errorhandler(ErrorAplicacion)
    def manejar_error_aplicacion(error):
        # Mensaje de negocio: escrito para el usuario, se devuelve tal cual
        return jsonify({
            'mensaje': error.mensaje,
            'codigo': 'error_aplicacion',
        }), error.http_status

    @app.errorhandler(SQLAlchemyError)
    def manejar_error_db(error):
        # El crudo se loguea dentro de traducir_error_db y NO sale de aca
        db.session.rollback()
        return jsonify({
            'mensaje': traducir_error_db(error),
            'codigo': 'error_base_de_datos',
        }), 400

    @app.errorhandler(404)
    def manejar_no_encontrado(error):
        return jsonify({
            'mensaje': 'El recurso solicitado no existe.',
            'codigo': 'no_encontrado',
        }), 404

    @app.errorhandler(405)
    def manejar_metodo_no_permitido(error):
        return jsonify({
            'mensaje': 'Metodo no permitido para este recurso.',
            'codigo': 'metodo_no_permitido',
        }), 405

    @app.errorhandler(Exception)
    def manejar_error_inesperado(error):
        # Red final: nada que no este contemplado arriba puede filtrar su
        # texto al cliente. El detalle completo queda en el log.
        app.logger.exception('Error no controlado: %s', error)
        db.session.rollback()
        return jsonify({
            'mensaje': 'Ocurrio un error inesperado. Intente nuevamente.',
            'codigo': 'error_interno',
        }), 500


def register_blueprints(app):
    """Registra los blueprints de cada modulo bajo el prefijo /api."""
    from app.routes.auth import auth_bp
    from app.routes.health import health_bp

    app.register_blueprint(health_bp, url_prefix='/api')
    app.register_blueprint(auth_bp, url_prefix='/api')

    # Entrega 1: pacientes_bp, objetivos_bp, sesiones_bp y evoluciones_bp
    # se registran aca a medida que se implementen.
    #
    # El modulo de RRHH va en su PROPIO blueprint aislado, que solo puede
    # llamar a p_reporte_sesiones_periodo y v_resumen_sesiones. Es la
    # mitigacion acordada para el hallazgo A3 de AUDITORIA.md: no hay
    # usuario de MySQL separado por rol, asi que el limite lo sostiene esa
    # separacion. No mezclar endpoints de RRHH en otro blueprint.

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
    from app.utils.errors import (
        ErrorAplicacion, campo_para_mensaje, traducir_error_db,
    )

    @app.errorhandler(ErrorAplicacion)
    def manejar_error_aplicacion(error):
        # Mensaje de negocio: escrito para el usuario, se devuelve tal cual.
        # `campo` es metadato al lado, para que el cliente marque el input
        # correcto sin adivinar leyendo el texto.
        return jsonify({
            'mensaje': error.mensaje,
            'codigo': 'error_aplicacion',
            'campo': error.campo or campo_para_mensaje(error.mensaje),
        }), error.http_status

    @app.errorhandler(SQLAlchemyError)
    def manejar_error_db(error):
        # El crudo se loguea dentro de traducir_error_db y NO sale de aca
        db.session.rollback()
        mensaje = traducir_error_db(error)
        return jsonify({
            'mensaje': mensaje,
            'codigo': 'error_base_de_datos',
            'campo': campo_para_mensaje(mensaje),
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
    from app.routes.agenda_recurrente import agenda_recurrente_bp
    from app.routes.asignaciones import asignaciones_bp
    from app.routes.renglones import renglones_bp
    from app.routes.auth import auth_bp
    from app.routes.evoluciones import evoluciones_bp
    from app.routes.health import health_bp
    from app.routes.objetivos import objetivos_bp
    from app.routes.pacientes import pacientes_bp
    from app.routes.rrhh import rrhh_bp
    from app.routes.sesiones import sesiones_bp

    app.register_blueprint(health_bp, url_prefix='/api')
    app.register_blueprint(auth_bp, url_prefix='/api')
    app.register_blueprint(pacientes_bp, url_prefix='/api')
    app.register_blueprint(asignaciones_bp, url_prefix='/api')
    app.register_blueprint(renglones_bp, url_prefix='/api')
    app.register_blueprint(agenda_recurrente_bp, url_prefix='/api')
    app.register_blueprint(objetivos_bp, url_prefix='/api')
    app.register_blueprint(sesiones_bp, url_prefix='/api')
    app.register_blueprint(evoluciones_bp, url_prefix='/api')
    #
    # El modulo de RRHH va en su PROPIO blueprint aislado, que solo puede
    # llamar a p_reporte_sesiones_periodo y v_resumen_sesiones. Es la
    # mitigacion acordada para el hallazgo A3 de AUDITORIA.md: no hay
    # usuario de MySQL separado por rol, asi que el limite lo sostiene esa
    # separacion. No mezclar endpoints de RRHH en otro blueprint.
    #
    # Construido el 2026-09-13 con el primer lote del modulo. Hoy expone un
    # solo endpoint y llama a un solo procedimiento; `v_resumen_sesiones`
    # todavia no la usa nadie. La separacion vale igual desde el primer dia:
    # es mas barata de sostener que de reconstruir cuando ya haya cinco
    # endpoints escritos en otro lado.
    app.register_blueprint(rrhh_bp, url_prefix='/api')

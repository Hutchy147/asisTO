# backend/app/__init__.py
# Application factory. Cada modulo se registra como blueprint propio.

import logging

from flask import Flask, jsonify, request
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
    registrar_acentuacion_de_mensajes(app)
    registrar_validacion_de_cuerpo(app)
    register_blueprints(app)

    return app


def configurar_logging(app):
    """El log del servidor es donde van los errores crudos, no la respuesta."""
    nivel = logging.DEBUG if app.config.get('DEBUG') else logging.INFO
    logging.basicConfig(
        level=nivel,
        format='%(asctime)s %(levelname)s [%(name)s] %(message)s',
    )


def _es_dato_con_tipo_equivocado(error):
    """AttributeError de str sobre otro tipo, o parametro SQL que no es escalar."""
    texto = str(error)
    if isinstance(error, AttributeError):
        return ' object has no attribute ' in texto and texto.rsplit("'", 2)[-2] in (
            'strip', 'lower', 'upper', 'split', 'encode', 'isdigit',
        )
    if isinstance(error, TypeError):
        return 'can not be used as parameter' in texto
    # Una fecha valida pero extrema (9999-12-31) desborda al sumarle dias.
    if isinstance(error, OverflowError):
        return 'date value out of range' in texto
    return False


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
        # Datos con el tipo equivocado (un numero o una lista donde iba un
        # texto): los servicios llaman `.strip()` sobre lo que llega y fallan
        # recien ahi. Es un error de quien manda la solicitud, no del servidor.
        if _es_dato_con_tipo_equivocado(error):
            app.logger.warning('Dato con tipo invalido en %s %s: %s',
                               request.method, request.path, error)
            db.session.rollback()
            mensaje = (
                'Alguna de las fechas indicadas está fuera del rango permitido.'
                if isinstance(error, OverflowError)
                else 'Alguno de los datos enviados tiene un formato inválido.'
            )
            return jsonify({
                'mensaje': mensaje,
                'codigo': 'error_aplicacion',
            }), 400
        # Red final: nada que no este contemplado arriba puede filtrar su
        # texto al cliente. El detalle completo queda en el log.
        app.logger.exception('Error no controlado: %s', error)
        db.session.rollback()
        return jsonify({
            'mensaje': 'Ocurrió un error inesperado. Intente nuevamente.',
            'codigo': 'error_interno',
        }), 500


def registrar_validacion_de_cuerpo(app):
    """
    Todos los endpoints esperan un objeto JSON. Si llega otra cosa (una lista,
    un texto, un numero) se rechaza aca con 400 en vez de dejar que cada
    servicio falle con un 500 al llamar `.get` sobre algo que no es un dict.
    """
    from flask import request
    from app.utils.errors import ErrorAplicacion

    @app.before_request
    def exigir_cuerpo_objeto():
        if request.method not in ('POST', 'PUT', 'PATCH', 'DELETE'):
            return None
        if not request.is_json or not request.get_data(cache=True):
            return None
        cuerpo = request.get_json(silent=True)
        if cuerpo is not None and not isinstance(cuerpo, dict):
            raise ErrorAplicacion('El cuerpo de la solicitud debe ser un objeto JSON.')
        return None


def registrar_acentuacion_de_mensajes(app):
    """
    Restituye las tildes del `mensaje` de primer nivel de cada respuesta JSON.

    Los mensajes del sistema (los de los procedimientos y los de la capa de
    aplicacion) se escriben en ASCII; las tildes se ponen aca, en un solo
    lugar, para que no dependan de que cada servicio se acuerde de hacerlo.
    Solo toca `mensaje`: lo que escribe la gente nunca pasa por aca.
    """
    from app.utils.textos import acentuar

    @app.after_request
    def acentuar_respuesta(respuesta):
        if respuesta.mimetype != 'application/json' or respuesta.direct_passthrough:
            return respuesta
        datos = respuesta.get_data()
        if b'"mensaje"' not in datos:
            return respuesta
        cuerpo = respuesta.get_json(silent=True)
        if not isinstance(cuerpo, dict) or not isinstance(cuerpo.get('mensaje'), str):
            return respuesta
        acentuado = acentuar(cuerpo['mensaje'])
        if acentuado != cuerpo['mensaje']:
            cuerpo['mensaje'] = acentuado
            respuesta.set_data(app.json.dumps(cuerpo) + '\n')
        return respuesta


def register_blueprints(app):
    """Registra los blueprints de cada modulo bajo el prefijo /api."""
    from app.routes.agenda_recurrente import agenda_recurrente_bp
    from app.routes.asignaciones import asignaciones_bp
    from app.routes.renglones import renglones_bp
    from app.routes.auth import auth_bp
    from app.routes.evoluciones import evoluciones_bp
    from app.routes.familiares import familiares_bp
    from app.routes.health import health_bp
    from app.routes.informes import informes_bp
    from app.routes.ingreso import ingreso_bp
    from app.routes.notificaciones import notificaciones_bp
    from app.routes.objetivos import objetivos_bp
    from app.routes.plantillas_objetivos import plantillas_objetivos_bp
    from app.routes.pacientes import pacientes_bp
    from app.routes.portal_familiar import portal_familiar_bp
    from app.routes.portal_paciente import portal_paciente_bp
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
    app.register_blueprint(familiares_bp, url_prefix='/api')
    app.register_blueprint(portal_familiar_bp, url_prefix='/api')
    app.register_blueprint(portal_paciente_bp, url_prefix='/api')
    app.register_blueprint(informes_bp, url_prefix='/api')
    app.register_blueprint(notificaciones_bp, url_prefix='/api')
    app.register_blueprint(ingreso_bp, url_prefix='/api')
    app.register_blueprint(plantillas_objetivos_bp, url_prefix='/api')
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

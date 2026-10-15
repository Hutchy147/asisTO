# backend/app/routes/rrhh.py
# Endpoints de RRHH. Solo el rol rrhh.
#
# RRHH verifica asistencias: quien atendio a quien y quien falto. NO accede
# a contenido clinico, y ese limite hoy no lo sostiene la base (hallazgo A3):
# lo sostienen la proyeccion del procedimiento y COLUMNAS_REPORTE. Ver
# rrhh_service.py.
#
# El rol terapeuta NO entra a este blueprint, y es a proposito: no es que le
# falte nada del reporte, es que el reporte no es una vista suya. El terapeuta
# ya tiene sus sesiones por /api/sesiones, con su contenido clinico incluido.

from flask import Blueprint, jsonify, request

from app.services.auditoria_service import listar_accesos
from app.services.rrhh_service import (
    listar_observaciones, registrar_observacion, reporte_sesiones,
)
from app.utils.security import requiere_rol

rrhh_bp = Blueprint('rrhh', __name__)


@rrhh_bp.get('/rrhh/reporte-sesiones')
@requiere_rol('rrhh')
def reporte():
    """
    Reporte de asistencias del periodo.

    Query: desde=AAAA-MM-DD, hasta=AAAA-MM-DD, id_terapeuta (opcional).

    Un periodo sin sesiones devuelve 200 con `sesiones: []` y un resumen en
    cero, no un 404: "no hubo sesiones" es una respuesta del reporte, no la
    ausencia del reporte.
    """
    return jsonify(reporte_sesiones(
        request.args.get('desde'),
        request.args.get('hasta'),
        request.args.get('id_terapeuta'),
    )), 200


# ---------------------------------------------------------------------
# OBSERVACIONES TECNICAS — el unico camino de ESCRITURA del rol rrhh.
#
# Cuelgan de la sesion (`/rrhh/sesiones/<id>/observaciones`) y no de una
# coleccion propia (`/rrhh/observaciones`) porque una observacion no existe
# sin la sesion que comenta: la URL dice de que es.
#
# Sigue sin haber PUT ni DELETE, y es una decision: una observacion
# administrativa es una constancia de algo que paso. Editarla o borrarla
# despues es reescribir el registro, que es justo lo que una constancia no
# tiene que permitir. Si alguna vez hace falta corregir una, se agrega otra.
# ---------------------------------------------------------------------

@rrhh_bp.get('/rrhh/sesiones/<int:id_sesion>/observaciones')
@requiere_rol('rrhh')
def observaciones(id_sesion):
    return jsonify(listar_observaciones(id_sesion)), 200


@rrhh_bp.post('/rrhh/sesiones/<int:id_sesion>/observaciones')
@requiere_rol('rrhh')
def crear_observacion(id_sesion):
    """
    Registra una observacion tecnica sobre la sesion.

    El AUTOR no viaja en el cuerpo: sale del token. Aceptarlo del cliente
    dejaria que cualquiera con rol rrhh firme con el legajo de otro.
    """
    datos = request.get_json(silent=True) or {}
    observacion, mensaje = registrar_observacion(id_sesion, datos)

    return jsonify({
        'observacion': observacion.to_dict(),
        # p_mensaje del procedimiento, propagado tal cual
        'mensaje': mensaje,
    }), 201


@rrhh_bp.get('/rrhh/auditoria-accesos')
@requiere_rol('rrhh')
def auditoria_accesos():
    """
    Auditoria de accesos: quien intento entrar, cuando y con que resultado.

    Query: desde, hasta (AAAA-MM-DD; por omision los ultimos 7 dias),
    resultado (exitoso|fallido|bloqueado), email (parcial), limite (max 500).
    No expone contrasenas: la tabla nunca las guarda.
    """
    return jsonify(listar_accesos(
        request.args.get('desde'),
        request.args.get('hasta'),
        request.args.get('resultado'),
        request.args.get('email'),
        request.args.get('limite'),
    )), 200

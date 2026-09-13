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

from app.services.rrhh_service import reporte_sesiones
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

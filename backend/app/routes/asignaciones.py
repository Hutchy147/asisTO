# backend/app/routes/asignaciones.py
# Asignacion paciente-terapeuta (HDU 11). Solo el rol terapeuta.

from flask import Blueprint, jsonify, request

from app.services.asignaciones_service import (
    abrir_asignacion, cerrar_asignacion, listar_de_paciente, listar_terapeutas,
)
from app.utils.security import requiere_rol

asignaciones_bp = Blueprint('asignaciones', __name__)


@asignaciones_bp.get('/terapeutas')
@requiere_rol('terapeuta')
def terapeutas():
    lista = listar_terapeutas()
    return jsonify({'terapeutas': lista, 'total': len(lista)}), 200


@asignaciones_bp.get('/pacientes/<int:id_paciente>/asignaciones')
@requiere_rol('terapeuta')
def del_paciente(id_paciente):
    """Historial de asignaciones. Lectura abierta entre terapeutas."""
    return jsonify(listar_de_paciente(id_paciente)), 200


@asignaciones_bp.post('/pacientes/<int:id_paciente>/asignaciones')
@requiere_rol('terapeuta')
def abrir(id_paciente):
    datos = request.get_json(silent=True) or {}
    asignacion, mensaje = abrir_asignacion(id_paciente, datos)
    return jsonify({'asignacion': asignacion, 'mensaje': mensaje}), 201


@asignaciones_bp.post('/asignaciones/<int:id_asignacion>/cierre')
@requiere_rol('terapeuta')
def cerrar(id_asignacion):
    """
    Cierra la asignacion. POST a un sub-recurso y no DELETE: no se borra
    nada, la asignacion queda en el historial con su fecha_hasta.
    """
    datos = request.get_json(silent=True) or {}
    asignacion, mensaje = cerrar_asignacion(id_asignacion, datos)
    return jsonify({'asignacion': asignacion, 'mensaje': mensaje}), 200

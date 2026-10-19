# backend/app/routes/asignaciones.py
# Asignacion paciente-terapeuta (HDU 11).
# Lectura: terapeuta y administrador. Alta y cierre de asignaciones: solo el
# administrador; un terapeuta no decide quien atiende a quien.

from flask import Blueprint, jsonify, request

from app.services.asignaciones_service import (
    abrir_asignacion, cerrar_asignacion, listar_de_paciente, listar_pacientes_admin,
    listar_terapeutas,
)
from app.utils.security import requiere_rol

asignaciones_bp = Blueprint('asignaciones', __name__)


@asignaciones_bp.get('/terapeutas')
@requiere_rol('terapeuta', 'admin')
def terapeutas():
    lista = listar_terapeutas()
    return jsonify({'terapeutas': lista, 'total': len(lista)}), 200


@asignaciones_bp.get('/pacientes/<int:id_paciente>/asignaciones')
@requiere_rol('terapeuta', 'admin')
def del_paciente(id_paciente):
    """Historial de asignaciones. Lectura abierta entre terapeutas."""
    return jsonify(listar_de_paciente(id_paciente)), 200


@asignaciones_bp.post('/pacientes/<int:id_paciente>/asignaciones')
@requiere_rol('admin')
def abrir(id_paciente):
    datos = request.get_json(silent=True) or {}
    asignacion, mensaje = abrir_asignacion(id_paciente, datos)
    return jsonify({'asignacion': asignacion, 'mensaje': mensaje}), 201


@asignaciones_bp.post('/asignaciones/<int:id_asignacion>/cierre')
@requiere_rol('admin')
def cerrar(id_asignacion):
    """
    Cierra la asignacion. POST a un sub-recurso y no DELETE: no se borra
    nada, la asignacion queda en el historial con su fecha_hasta.
    """
    datos = request.get_json(silent=True) or {}
    asignacion, mensaje = cerrar_asignacion(id_asignacion, datos)
    return jsonify({'asignacion': asignacion, 'mensaje': mensaje}), 200


@asignaciones_bp.get('/admin/pacientes')
@requiere_rol('admin')
def pacientes_para_asignar():
    """Pacientes con sus responsables vigentes. Sin datos clinicos."""
    lista = listar_pacientes_admin()
    return jsonify({'pacientes': lista, 'total': len(lista)}), 200

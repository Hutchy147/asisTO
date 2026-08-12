# backend/app/routes/pacientes.py
# Endpoints de pacientes. Solo el rol terapeuta.

from flask import Blueprint, jsonify, request

from app.services.pacientes_service import (
    alta_paciente, baja_paciente, listar_pacientes, obtener_detalle,
    reactivar_paciente,
)
from app.services.sesiones_service import listar_por_paciente as listar_sesiones_de_paciente
from app.utils.security import requiere_rol

pacientes_bp = Blueprint('pacientes', __name__)


@pacientes_bp.get('/pacientes')
@requiere_rol('terapeuta')
def listar():
    pacientes = listar_pacientes()
    return jsonify({'pacientes': pacientes, 'total': len(pacientes)}), 200


@pacientes_bp.post('/pacientes')
@requiere_rol('terapeuta')
def crear():
    datos = request.get_json(silent=True) or {}
    paciente, mensaje = alta_paciente(datos)

    return jsonify({
        'paciente': paciente.to_dict_clinico(),
        # p_mensaje del procedimiento, propagado tal cual
        'mensaje': mensaje,
    }), 201


@pacientes_bp.get('/pacientes/<int:id_paciente>')
@requiere_rol('terapeuta')
def detalle(id_paciente):
    return jsonify(obtener_detalle(id_paciente)), 200


@pacientes_bp.post('/pacientes/<int:id_paciente>/baja')
@requiere_rol('terapeuta')
def baja(id_paciente):
    """
    Baja logica del paciente.

    POST y no DELETE a proposito: DELETE anuncia que el recurso deja de
    existir, y aca no desaparece nada — el paciente sigue estando, con su
    historia entera, y hasta se puede reactivar. Un DELETE que no borra es
    una promesa falsa en el contrato de la API.
    """
    paciente, resumen = baja_paciente(id_paciente)

    return jsonify({
        'paciente': paciente.to_dict_clinico(),
        # Cuantos objetivos y asignaciones arrastro la baja. La interfaz lo
        # muestra: son efectos que el usuario no pidio explicitamente.
        'objetivos_archivados': resumen['objetivos_archivados'],
        'asignaciones_cerradas': resumen['asignaciones_cerradas'],
        'mensaje': resumen['mensaje'],
    }), 200


@pacientes_bp.post('/pacientes/<int:id_paciente>/reactivacion')
@requiere_rol('terapeuta')
def reactivacion(id_paciente):
    """
    Deshace la baja. Los objetivos archivados NO vuelven solos.

    Es un sub-recurso propio y no un PUT sobre el paciente con activo=true:
    reactivar es una operacion con reglas propias, no la edicion de un campo.
    """
    paciente, mensaje = reactivar_paciente(id_paciente)

    return jsonify({
        'paciente': paciente.to_dict_clinico(),
        'mensaje': mensaje,
    }), 200


@pacientes_bp.get('/pacientes/<int:id_paciente>/sesiones')
@requiere_rol('terapeuta')
def sesiones_del_paciente(id_paciente):
    """
    Historial de sesiones del paciente, de TODOS los terapeutas.

    La ruta vive en este blueprint y no en el de sesiones porque el recurso
    es "las sesiones de este paciente": es donde alguien las va a buscar.
    La logica sigue estando en sesiones_service.
    """
    return jsonify(listar_sesiones_de_paciente(id_paciente)), 200

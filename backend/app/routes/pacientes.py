# backend/app/routes/pacientes.py
# Endpoints de pacientes. Solo el rol terapeuta.

from flask import Blueprint, jsonify, request

from app.services.pacientes_service import (
    alta_paciente, listar_pacientes, obtener_detalle,
)
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

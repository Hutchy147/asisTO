# backend/app/routes/evoluciones.py
# Endpoints de evoluciones. Solo el rol terapeuta.

from flask import Blueprint, jsonify, request

from app.services.evoluciones_service import corregir_evolucion, listar_por_sesion, registrar_evolucion
from app.utils.security import requiere_rol

evoluciones_bp = Blueprint('evoluciones', __name__)


@evoluciones_bp.post('/evoluciones')
@requiere_rol('terapeuta')
def crear():
    datos = request.get_json(silent=True) or {}
    evolucion, mensaje = registrar_evolucion(datos)

    return jsonify({
        'evolucion': evolucion.to_dict(),
        # p_mensaje del procedimiento, propagado tal cual
        'mensaje': mensaje,
    }), 201


@evoluciones_bp.get('/evoluciones/sesion/<int:id_sesion>')
@requiere_rol('terapeuta')
def listar_de_sesion(id_sesion):
    return jsonify(listar_por_sesion(id_sesion)), 200


@evoluciones_bp.put('/evoluciones/<int:id_evolucion>')
@requiere_rol('terapeuta')
def corregir(id_evolucion):
    """Corrige una calificacion con el registro de la sesion abierto."""
    datos = request.get_json(silent=True) or {}
    return jsonify({'mensaje': corregir_evolucion(id_evolucion, datos)}), 200


@evoluciones_bp.delete('/evoluciones/<int:id_evolucion>')
@requiere_rol('terapeuta')
def quitar(id_evolucion):
    """Quita una calificacion: el objetivo vuelve a quedar sin calificar."""
    return jsonify({'mensaje': corregir_evolucion(id_evolucion, {}, quitar=True)}), 200

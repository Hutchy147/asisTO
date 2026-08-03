# backend/app/routes/sesiones.py
# Endpoints de sesiones. Solo el rol terapeuta.

from flask import Blueprint, jsonify, request

from app.services.sesiones_service import (
    listar_de_hoy, listar_pendientes_de_evolucion, listar_por_rango,
    obtener_detalle, registrar_sesion,
)
from app.utils.security import requiere_rol

sesiones_bp = Blueprint('sesiones', __name__)


@sesiones_bp.get('/sesiones')
@requiere_rol('terapeuta')
def listar():
    return jsonify(listar_por_rango(
        request.args.get('desde'), request.args.get('hasta')
    )), 200


# Antes que /sesiones/<int:id> no hace falta por el convertidor int, pero
# se declaran las rutas literales primero para que quede explicito.
@sesiones_bp.get('/sesiones/hoy')
@requiere_rol('terapeuta')
def hoy():
    return jsonify(listar_de_hoy()), 200


@sesiones_bp.get('/sesiones/pendientes-evolucion')
@requiere_rol('terapeuta')
def pendientes_evolucion():
    return jsonify(listar_pendientes_de_evolucion()), 200


@sesiones_bp.post('/sesiones')
@requiere_rol('terapeuta')
def crear():
    datos = request.get_json(silent=True) or {}
    sesion, mensaje = registrar_sesion(datos)

    return jsonify({
        'sesion': sesion.to_dict(),
        # p_mensaje del procedimiento, propagado tal cual
        'mensaje': mensaje,
    }), 201


@sesiones_bp.get('/sesiones/<int:id_sesion>')
@requiere_rol('terapeuta')
def detalle(id_sesion):
    return jsonify(obtener_detalle(id_sesion)), 200

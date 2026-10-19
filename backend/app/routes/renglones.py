# backend/app/routes/renglones.py
# Renglones de la sesion (notas de campo). Solo el rol terapeuta.

from flask import Blueprint, jsonify, request

from app.services.renglones_service import (
    agregar_renglon, borrar_renglon, cerrar_renglon, editar_renglon,
    listar_de_sesion, marcar_objetivo,
)
from app.utils.security import requiere_rol

renglones_bp = Blueprint('renglones', __name__)


@renglones_bp.get('/sesiones/<int:id_sesion>/renglones')
@requiere_rol('terapeuta')
def listar(id_sesion):
    return jsonify(listar_de_sesion(id_sesion)), 200


@renglones_bp.post('/sesiones/<int:id_sesion>/renglones')
@requiere_rol('terapeuta')
def crear(id_sesion):
    datos = request.get_json(silent=True) or {}
    renglon, mensaje = agregar_renglon(id_sesion, datos)
    return jsonify({'renglon': renglon, 'mensaje': mensaje}), 201


@renglones_bp.put('/renglones/<int:id_renglon>')
@requiere_rol('terapeuta')
def editar(id_renglon):
    datos = request.get_json(silent=True) or {}
    renglon, mensaje = editar_renglon(id_renglon, datos)
    return jsonify({'renglon': renglon, 'mensaje': mensaje}), 200


@renglones_bp.post('/renglones/<int:id_renglon>/cierre')
@requiere_rol('terapeuta')
def cerrar(id_renglon):
    datos = request.get_json(silent=True) or {}
    renglon, mensaje = cerrar_renglon(id_renglon, datos)
    return jsonify({'renglon': renglon, 'mensaje': mensaje}), 200


@renglones_bp.delete('/renglones/<int:id_renglon>')
@requiere_rol('terapeuta')
def borrar(id_renglon):
    return jsonify({'mensaje': borrar_renglon(id_renglon)}), 200


@renglones_bp.post('/sesiones/<int:id_sesion>/objetivos')
@requiere_rol('terapeuta')
def objetivo_del_plan(id_sesion):
    """Marca (`marcado: true`, por defecto) o desmarca un objetivo a trabajar."""
    datos = request.get_json(silent=True) or {}
    mensaje = marcar_objetivo(id_sesion, datos)
    return jsonify({'mensaje': mensaje}), 200

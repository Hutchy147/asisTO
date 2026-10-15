# backend/app/routes/agenda_recurrente.py
# Agenda semanal recurrente. Solo el rol terapeuta; cada una la suya.

from flask import Blueprint, jsonify, request

from app.services.agenda_recurrente_service import (
    crear_plantilla, generar_agenda, listar_plantillas, quitar_plantilla,
)
from app.utils.security import requiere_rol

agenda_recurrente_bp = Blueprint('agenda_recurrente', __name__)


@agenda_recurrente_bp.get('/agenda-recurrente')
@requiere_rol('terapeuta')
def listar():
    return jsonify(listar_plantillas()), 200


@agenda_recurrente_bp.post('/agenda-recurrente')
@requiere_rol('terapeuta')
def crear():
    datos = request.get_json(silent=True) or {}
    return jsonify({'turno': crear_plantilla(datos)}), 201


@agenda_recurrente_bp.delete('/agenda-recurrente/<int:id_plantilla>')
@requiere_rol('terapeuta')
def quitar(id_plantilla):
    return jsonify(quitar_plantilla(id_plantilla)), 200


@agenda_recurrente_bp.post('/agenda-recurrente/generar')
@requiere_rol('terapeuta')
def generar():
    datos = request.get_json(silent=True) or {}
    return jsonify(generar_agenda(datos)), 200

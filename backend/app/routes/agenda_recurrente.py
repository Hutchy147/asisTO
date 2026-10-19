# backend/app/routes/agenda_recurrente.py
# Agenda semanal recurrente. Solo el rol terapeuta; cada una la suya.

from flask import Blueprint, jsonify, request

from app.services.agenda_recurrente_service import (
    crear_plantilla, generar_agenda, listar_plantillas, quitar_plantilla,
    sumar_companero,
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
    # Con `id_paciente_2` el turno nace en dupla (dos turnos de una vez)
    return jsonify(crear_plantilla(datos)), 201


@agenda_recurrente_bp.delete('/agenda-recurrente/<int:id_plantilla>')
@requiere_rol('terapeuta')
def quitar(id_plantilla):
    # ?dupla=1 quita la dupla entera; sin eso, solo el turno indicado
    completa = request.args.get('dupla') in ('1', 'true')
    return jsonify(quitar_plantilla(id_plantilla, dupla_completa=completa)), 200


@agenda_recurrente_bp.post('/agenda-recurrente/<int:id_plantilla>/companero')
@requiere_rol('terapeuta')
def sumar(id_plantilla):
    datos = request.get_json(silent=True) or {}
    return jsonify(sumar_companero(id_plantilla, datos.get('id_paciente'))), 201


@agenda_recurrente_bp.post('/agenda-recurrente/generar')
@requiere_rol('terapeuta')
def generar():
    datos = request.get_json(silent=True) or {}
    return jsonify(generar_agenda(datos)), 200

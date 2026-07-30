# backend/app/routes/objetivos.py
# Endpoints de objetivos terapeuticos. Solo el rol terapeuta.

from flask import Blueprint, jsonify, request

from app.services.objetivos_service import (
    archivar_objetivo, crear_objetivo, editar_descripcion, listar_por_paciente,
)
from app.utils.security import requiere_rol

objetivos_bp = Blueprint('objetivos', __name__)


@objetivos_bp.get('/objetivos/paciente/<int:id_paciente>')
@requiere_rol('terapeuta')
def listar_de_paciente(id_paciente):
    return jsonify(listar_por_paciente(id_paciente)), 200


@objetivos_bp.post('/objetivos')
@requiere_rol('terapeuta')
def crear():
    datos = request.get_json(silent=True) or {}
    objetivo = crear_objetivo(datos)

    return jsonify({
        'objetivo': objetivo.to_dict(),
        'mensaje': 'Objetivo creado correctamente.',
    }), 201


@objetivos_bp.put('/objetivos/<int:id_objetivo>')
@requiere_rol('terapeuta')
def editar(id_objetivo):
    datos = request.get_json(silent=True) or {}
    objetivo = editar_descripcion(id_objetivo, datos)

    return jsonify({
        'objetivo': objetivo.to_dict(),
        'mensaje': 'Objetivo actualizado correctamente.',
    }), 200


@objetivos_bp.delete('/objetivos/<int:id_objetivo>')
@requiere_rol('terapeuta')
def archivar(id_objetivo):
    """
    Archiva, no borra. Ver archivar_objetivo(): las evoluciones historicas
    dependen de esta fila.
    """
    objetivo = archivar_objetivo(id_objetivo)

    return jsonify({
        'objetivo': objetivo.to_dict(),
        'mensaje': 'Objetivo archivado. Las evoluciones cargadas se conservan.',
    }), 200

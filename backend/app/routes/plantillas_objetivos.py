# backend/app/routes/plantillas_objetivos.py
# Plantillas de objetivos por area (Entrega 5). Lee el terapeuta (al crear un
# objetivo) y el administrador; solo el administrador modifica el catalogo.

from flask import Blueprint, jsonify, request

from app.services import plantillas_objetivos_service as servicio
from app.utils.security import requiere_rol

plantillas_objetivos_bp = Blueprint('plantillas_objetivos', __name__)


@plantillas_objetivos_bp.get('/plantillas-objetivos')
@requiere_rol('terapeuta', 'admin')
def listar():
    return jsonify(servicio.listar_plantillas()), 200


@plantillas_objetivos_bp.post('/plantillas-objetivos')
@requiere_rol('admin')
def crear():
    return jsonify({'plantilla': servicio.crear_plantilla(request.get_json(silent=True) or {})}), 201


@plantillas_objetivos_bp.put('/plantillas-objetivos/<int:id_plantilla>')
@requiere_rol('admin')
def editar(id_plantilla):
    return jsonify({'plantilla': servicio.editar_plantilla(id_plantilla, request.get_json(silent=True) or {})}), 200


@plantillas_objetivos_bp.delete('/plantillas-objetivos/<int:id_plantilla>')
@requiere_rol('admin')
def quitar(id_plantilla):
    return jsonify({'mensaje': servicio.quitar_plantilla(id_plantilla)}), 200

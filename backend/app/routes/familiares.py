# backend/app/routes/familiares.py
# Vinculo familiar-paciente (Entrega 4). Lo gestiona SOLO el administrador (alta,
# candidatos y desvinculacion); la terapeuta asignada solo lo consulta; el familiar solo consume el portal (portal_familiar).

from flask import Blueprint, jsonify, request

from app.services.familiares_service import (
    desvincular, listar_candidatos, listar_de_paciente, vincular,
)
from app.utils.security import requiere_rol

familiares_bp = Blueprint('familiares', __name__)


@familiares_bp.get('/pacientes/<int:id_paciente>/familiares')
@requiere_rol('terapeuta', 'admin')
def del_paciente(id_paciente):
    return jsonify(listar_de_paciente(id_paciente)), 200


@familiares_bp.get('/pacientes/<int:id_paciente>/familiares/candidatos')
@requiere_rol('admin')
def candidatos(id_paciente):
    return jsonify(listar_candidatos(id_paciente, request.args.get('q'))), 200


@familiares_bp.post('/pacientes/<int:id_paciente>/familiares')
@requiere_rol('admin')
def alta(id_paciente):
    datos = request.get_json(silent=True) or {}
    familiar, contrasena, mensaje = vincular(id_paciente, datos)
    respuesta = {'familiar': familiar, 'mensaje': mensaje}
    if contrasena:
        # Se muestra una sola vez; la base solo guarda el hash.
        respuesta['contrasena_temporal'] = contrasena
    return jsonify(respuesta), 201


@familiares_bp.post('/pacientes/<int:id_paciente>/familiares/<int:id_familiar>/desvinculacion')
@requiere_rol('admin')
def baja(id_paciente, id_familiar):
    """POST a un sub-recurso: no se borra la cuenta, solo el acceso."""
    mensaje = desvincular(id_paciente, id_familiar)
    return jsonify({'mensaje': mensaje}), 200

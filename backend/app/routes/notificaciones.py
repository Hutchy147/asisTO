# backend/app/routes/notificaciones.py
# Avisos del familiar (Entrega 4). Solo rol `familiar`, solo los propios.

from flask import Blueprint, jsonify, request

from app.services import notificaciones_service as servicio
from app.utils.errors import ErrorAplicacion
from app.utils.security import requiere_rol

notificaciones_bp = Blueprint('notificaciones', __name__)


@notificaciones_bp.get('/familiar/notificaciones')
@requiere_rol('familiar')
def listado():
    a = request.args
    return jsonify(servicio.listar(
        tipo=a.get('tipo'), leida=a.get('leida'), id_paciente=a.get('id_paciente'),
        limite=a.get('limite', 50), desplazamiento=a.get('desplazamiento', 0),
    )), 200


@notificaciones_bp.get('/familiar/notificaciones/no-leidas')
@requiere_rol('familiar')
def no_leidas():
    return jsonify(servicio.contar_no_leidas()), 200


@notificaciones_bp.post('/familiar/notificaciones/lectura-masiva')
@requiere_rol('familiar')
def lectura_masiva():
    marcadas = servicio.marcar_todas()
    return jsonify({'marcadas': marcadas, 'mensaje': 'Todos los avisos quedaron como leídos.'}), 200


@notificaciones_bp.post('/familiar/notificaciones/<int:id_notificacion>/lectura')
@requiere_rol('familiar')
def lectura(id_notificacion):
    datos = request.get_json(silent=True) or {}
    leida = datos.get('leida', True)
    if not isinstance(leida, bool):
        raise ErrorAplicacion('Indique si el aviso queda leído o no.', campo='leida')
    return jsonify({'notificacion': servicio.marcar(id_notificacion, leida)}), 200


@notificaciones_bp.get('/familiar/notificaciones/preferencias')
@requiere_rol('familiar')
def preferencias():
    return jsonify(servicio.listar_preferencias()), 200


@notificaciones_bp.put('/familiar/notificaciones/preferencias/<tipo>')
@requiere_rol('familiar')
def preferencia(tipo):
    datos = request.get_json(silent=True) or {}
    return jsonify(servicio.guardar_preferencia(tipo, datos.get('habilitada'))), 200

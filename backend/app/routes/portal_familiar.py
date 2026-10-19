# backend/app/routes/portal_familiar.py
# Portal del familiar (Entrega 4). Solo rol `familiar`, y solo sobre los
# pacientes vinculados a su cuenta. Prefijo propio (/api/familiar) para que
# la separacion con las rutas clinicas sea evidente al leer el codigo.

from flask import Blueprint, jsonify, request

from app.services.portal_familiar_service import (
    evolucion_vinculada, listar_pacientes_vinculados,
)
from app.utils.security import requiere_rol

portal_familiar_bp = Blueprint('portal_familiar', __name__)


@portal_familiar_bp.get('/familiar/pacientes')
@requiere_rol('familiar')
def pacientes():
    return jsonify(listar_pacientes_vinculados()), 200


@portal_familiar_bp.get('/familiar/pacientes/<int:id_paciente>/evolucion')
@requiere_rol('familiar')
def evolucion(id_paciente):
    datos = evolucion_vinculada(
        id_paciente, request.args.get('desde'), request.args.get('hasta')
    )
    return jsonify(datos), 200

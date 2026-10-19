# backend/app/routes/portal_paciente.py
# Portal del paciente (Entrega 6). Solo rol `paciente`, y siempre sobre su
# propia ficha: el endpoint no recibe ningun id de paciente.

from flask import Blueprint, jsonify, request

from app.services.portal_paciente_service import mi_progreso
from app.utils.security import requiere_rol

portal_paciente_bp = Blueprint('portal_paciente', __name__)


@portal_paciente_bp.get('/paciente/mi-progreso')
@requiere_rol('paciente')
def progreso():
    datos = mi_progreso(request.args.get('desde'), request.args.get('hasta'))
    return jsonify(datos), 200

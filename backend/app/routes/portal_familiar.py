# backend/app/routes/portal_familiar.py
# Portal del familiar (Entrega 4). Solo rol `familiar`, y solo sobre los
# pacientes vinculados a su cuenta. Prefijo propio (/api/familiar) para que
# la separacion con las rutas clinicas sea evidente al leer el codigo.

from flask import Blueprint, Response, jsonify, request

from app.services.portal_familiar_service import (
    evolucion_vinculada, listar_informes_vinculados, listar_pacientes_vinculados,
    obtener_informe_vinculado, pdf_informe_vinculado,
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


# --- Informes publicados (Entrega 6, HDU 8) ---------------------------------
@portal_familiar_bp.get('/familiar/pacientes/<int:id_paciente>/informes')
@requiere_rol('familiar')
def informes(id_paciente):
    return jsonify(listar_informes_vinculados(id_paciente)), 200


@portal_familiar_bp.get('/familiar/pacientes/<int:id_paciente>/informes/<int:id_informe>')
@requiere_rol('familiar')
def informe(id_paciente, id_informe):
    return jsonify(obtener_informe_vinculado(id_paciente, id_informe)), 200


@portal_familiar_bp.get('/familiar/pacientes/<int:id_paciente>/informes/<int:id_informe>/pdf')
@requiere_rol('familiar')
def informe_pdf(id_paciente, id_informe):
    contenido, nombre = pdf_informe_vinculado(id_paciente, id_informe)
    return Response(
        contenido, mimetype='application/pdf',
        headers={'Content-Disposition': f'attachment; filename="{nombre}"'},
    )

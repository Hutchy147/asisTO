# backend/app/routes/informes.py
# Informes del tratamiento (Entrega 6, HDU 5 y 8). Solo terapeutas: RRHH y el
# administrador no acceden a contenido clinico. La escritura la limita la base
# al terapeuta asignado en el periodo del informe.

from flask import Blueprint, Response, jsonify, request

from app.services import informes_pdf, informes_service as servicio
from app.utils.security import requiere_rol

informes_bp = Blueprint('informes', __name__)


@informes_bp.get('/pacientes/<int:id_paciente>/informes')
@requiere_rol('terapeuta')
def historial(id_paciente):
    return jsonify(servicio.listar_de_paciente(id_paciente)), 200


@informes_bp.get('/pacientes/<int:id_paciente>/informes/diarios')
@requiere_rol('terapeuta')
def diarios(id_paciente):
    datos = servicio.diarios(id_paciente, request.args.get('tipo', ''), request.args.get('periodo', ''))
    return jsonify(datos), 200


@informes_bp.post('/pacientes/<int:id_paciente>/informes')
@requiere_rol('terapeuta')
def generar(id_paciente):
    cuerpo = request.get_json(silent=True) or {}
    return jsonify(servicio.generar(id_paciente, cuerpo)), 201


@informes_bp.get('/informes/control')
@requiere_rol('terapeuta')
def control():
    return jsonify(servicio.control_mensual(request.args.get('mes'))), 200


@informes_bp.get('/informes/<int:id_informe>')
@requiere_rol('terapeuta')
def obtener(id_informe):
    return jsonify(servicio.obtener(id_informe)), 200


@informes_bp.get('/informes/<int:id_informe>/diarios')
@requiere_rol('terapeuta')
def diarios_del_informe(id_informe):
    return jsonify(servicio.diarios_de_informe(id_informe)), 200


@informes_bp.put('/informes/<int:id_informe>')
@requiere_rol('terapeuta')
def editar(id_informe):
    cuerpo = request.get_json(silent=True) or {}
    return jsonify(servicio.editar(id_informe, cuerpo.get('contenido'))), 200


@informes_bp.post('/informes/<int:id_informe>/publicacion')
@requiere_rol('terapeuta')
def publicar(id_informe):
    return jsonify(servicio.publicar(id_informe)), 200


@informes_bp.post('/informes/<int:id_informe>/correccion')
@requiere_rol('terapeuta')
def corregir(id_informe):
    return jsonify(servicio.corregir(id_informe)), 201


@informes_bp.delete('/informes/<int:id_informe>')
@requiere_rol('terapeuta')
def descartar(id_informe):
    return jsonify(servicio.descartar(id_informe)), 200


@informes_bp.get('/informes/<int:id_informe>/pdf')
@requiere_rol('terapeuta')
def pdf(id_informe):
    datos = servicio.obtener(id_informe)
    nombre = datos['paciente']['nombre_completo']
    contenido = informes_pdf.generar_pdf(datos, nombre, datos.get('autor'))
    return Response(
        contenido, mimetype='application/pdf',
        headers={'Content-Disposition': f'attachment; filename="{informes_pdf.nombre_de_archivo(datos, nombre)}"'},
    )

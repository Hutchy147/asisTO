# backend/app/routes/ingreso.py
# Flujo de ingreso e historia clinica (Entrega 4).
# Lectura y escritura: terapeuta (la escritura la limita la base a quien tiene
# la asignacion vigente). Configuracion del formulario: solo administrador,
# que NO ve respuestas.

from flask import Blueprint, jsonify, request

from app.services import ingreso_service as servicio
from app.utils.security import requiere_rol

ingreso_bp = Blueprint('ingreso', __name__)


@ingreso_bp.get('/pacientes/<int:id_paciente>/ingreso')
@requiere_rol('terapeuta')
def obtener(id_paciente):
    return jsonify(servicio.obtener_ingreso(id_paciente)), 200


@ingreso_bp.post('/pacientes/<int:id_paciente>/ingreso')
@requiere_rol('terapeuta')
def iniciar(id_paciente):
    datos, mensaje = servicio.iniciar_ingreso(id_paciente)
    return jsonify(dict(datos, mensaje=mensaje)), 201


@ingreso_bp.put('/pacientes/<int:id_paciente>/ingreso/etapas/<etapa>')
@requiere_rol('terapeuta')
def guardar(id_paciente, etapa):
    cuerpo = request.get_json(silent=True) or {}
    datos, mensaje = servicio.guardar_etapa(id_paciente, etapa, cuerpo.get('respuestas'))
    return jsonify(dict(datos, mensaje=mensaje)), 200


@ingreso_bp.post('/pacientes/<int:id_paciente>/ingreso/etapas/<etapa>/cierre')
@requiere_rol('terapeuta')
def cerrar(id_paciente, etapa):
    datos, mensaje = servicio.cerrar_etapa(id_paciente, etapa)
    return jsonify(dict(datos, mensaje=mensaje)), 200


@ingreso_bp.post('/pacientes/<int:id_paciente>/ingreso/etapas/<etapa>/reapertura')
@requiere_rol('terapeuta')
def reabrir(id_paciente, etapa):
    datos, mensaje = servicio.reabrir_etapa(id_paciente, etapa)
    return jsonify(dict(datos, mensaje=mensaje)), 200


@ingreso_bp.post('/pacientes/<int:id_paciente>/ingreso/completado')
@requiere_rol('terapeuta')
def completar(id_paciente):
    datos, mensaje = servicio.completar_ingreso(id_paciente)
    return jsonify(dict(datos, mensaje=mensaje)), 200


@ingreso_bp.get('/pacientes/<int:id_paciente>/historia-clinica')
@requiere_rol('terapeuta')
def historia(id_paciente):
    return jsonify(servicio.historia_clinica(id_paciente)), 200


# --- Configuracion del formulario (administrador) ---

@ingreso_bp.get('/admin/ingreso/campos')
@requiere_rol('admin')
def campos():
    return jsonify(servicio.listar_campos_admin()), 200


@ingreso_bp.post('/admin/ingreso/campos')
@requiere_rol('admin')
def crear_campo():
    return jsonify({'campo': servicio.crear_campo(request.get_json(silent=True) or {})}), 201


@ingreso_bp.put('/admin/ingreso/campos/<int:id_campo>')
@requiere_rol('admin')
def editar_campo(id_campo):
    return jsonify({'campo': servicio.editar_campo(id_campo, request.get_json(silent=True) or {})}), 200

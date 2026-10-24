# backend/app/routes/usuarios.py
# Gestión de cuentas de acceso. Solo el administrador.

from flask import Blueprint, jsonify, request

from app.services import usuarios_service as servicio
from app.utils.security import requiere_rol

usuarios_bp = Blueprint('usuarios', __name__)


@usuarios_bp.get('/admin/usuarios')
@requiere_rol('admin')
def listar():
    lista = servicio.listar(
        rol=request.args.get('rol') or None,
        busqueda=request.args.get('busqueda'),
        estado=request.args.get('estado') or None,
    )
    return jsonify({'usuarios': lista, 'total': len(lista)}), 200


@usuarios_bp.get('/admin/usuarios/contrasena-sugerida')
@requiere_rol('admin')
def sugerida():
    return jsonify({'contrasena': servicio.contrasena_sugerida()}), 200


@usuarios_bp.post('/admin/usuarios')
@requiere_rol('admin')
def crear():
    usuario = servicio.crear(request.get_json(silent=True) or {})
    return jsonify({'usuario': usuario, 'mensaje': 'Cuenta creada correctamente'}), 201


@usuarios_bp.put('/admin/usuarios/<int:id_usuario>/estado')
@requiere_rol('admin')
def estado(id_usuario):
    datos = request.get_json(silent=True) or {}
    usuario = servicio.cambiar_estado(id_usuario, datos.get('activo'))
    texto = 'Cuenta habilitada' if usuario['activo'] else 'Cuenta deshabilitada'
    return jsonify({'usuario': usuario, 'mensaje': texto}), 200


@usuarios_bp.put('/admin/usuarios/<int:id_usuario>/contrasena')
@requiere_rol('admin')
def contrasena(id_usuario):
    datos = request.get_json(silent=True) or {}
    usuario = servicio.restablecer_contrasena(id_usuario, datos.get('contrasena'))
    return jsonify({'usuario': usuario, 'mensaje': 'Contraseña restablecida'}), 200

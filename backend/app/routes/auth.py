# backend/app/routes/auth.py
# Endpoints de autenticacion. Solo traducen HTTP: la logica esta en
# app/services/auth_service.py.

from flask import Blueprint, g, jsonify, request

from app.services.auth_service import (
    autenticar, enlace_de_recuperacion_vigente, obtener_perfil,
    restablecer_contrasena, solicitar_recuperacion,
)
from app.utils.security import requiere_rol

auth_bp = Blueprint('auth', __name__)


@auth_bp.post('/auth/login')
def login():
    datos = request.get_json(silent=True) or {}

    token, usuario, perfil = autenticar(
        datos.get('email'), datos.get('contrasena')
    )

    return jsonify({
        'token': token,
        'usuario': usuario.to_dict(),
        'perfil': perfil,
    }), 200


@auth_bp.post('/auth/logout')
@requiere_rol()
def logout():
    """
    Cierre de sesion.

    El JWT no tiene estado en el servidor, asi que el cierre efectivo es
    que el cliente descarte el token. Este endpoint existe igual para
    dejar registro en el log y para que el frontend tenga un unico lugar
    donde cerrar sesion.

    LIMITACION CONOCIDA: un token robado sigue siendo valido hasta que
    expira. Invalidarlo de verdad requiere una lista de revocacion, que se
    evaluara junto con el refresh token. Ver ESTADO.md.
    """
    return jsonify({'mensaje': 'Sesion cerrada correctamente.'}), 200


@auth_bp.get('/auth/me')
@requiere_rol()
def me():
    """Usuario actual segun el token. Lo usa el frontend al recargar."""
    usuario = g.usuario_actual

    return jsonify({
        'usuario': usuario.to_dict(),
        'perfil': obtener_perfil(usuario),
    }), 200


@auth_bp.post('/auth/recuperar')
def recuperar():
    """Pide un enlace de recuperacion. Responde igual exista o no la cuenta."""
    datos = request.get_json(silent=True) or {}
    mensaje, token = solicitar_recuperacion(datos.get('email'))

    cuerpo = {'mensaje': mensaje}
    if token:
        # Solo con RECUPERACION_MOSTRAR_TOKEN (desarrollo, sin servidor de mail).
        cuerpo['token_desarrollo'] = token
    return jsonify(cuerpo), 200


@auth_bp.post('/auth/restablecer/verificar')
def verificar_enlace():
    """Si el enlace de recuperacion todavia sirve. POST: el token no va en la URL."""
    datos = request.get_json(silent=True) or {}
    return jsonify({'vigente': enlace_de_recuperacion_vigente(datos.get('token'))}), 200


@auth_bp.post('/auth/restablecer')
def restablecer():
    datos = request.get_json(silent=True) or {}
    mensaje = restablecer_contrasena(
        datos.get('token'), datos.get('contrasena_nueva')
    )
    return jsonify({'mensaje': mensaje}), 200

# backend/app/routes/auth.py
# Endpoints de autenticacion. Solo traducen HTTP: la logica esta en
# app/services/auth_service.py.

from flask import Blueprint, current_app, g, jsonify, request
from sqlalchemy import text

from app import db
from app.utils import limites
from app.utils.errors import ErrorAplicacion

from app.services.auth_service import (
    autenticar, enlace_de_recuperacion_vigente, intentos_fallidos_previos, obtener_perfil,
    restablecer_contrasena, solicitar_recuperacion,
)
from app.utils.security import requiere_rol

auth_bp = Blueprint('auth', __name__)


def _poner_cookie(respuesta, token):
    """
    La sesion del navegador: HttpOnly (el JavaScript no la lee), SameSite
    Strict (no viaja en pedidos que nacen en otro sitio) y Secure fuera de
    desarrollo. Path /api: no se manda al pedir la pagina ni los archivos.
    """
    cfg = current_app.config
    respuesta.set_cookie(
        cfg['COOKIE_SESION'], token,
        max_age=cfg['JWT_ACCESS_TOKEN_EXPIRES'], path='/api',
        httponly=True, secure=cfg['COOKIE_SEGURA'], samesite=cfg['COOKIE_SAMESITE'],
    )


def _borrar_cookie(respuesta):
    cfg = current_app.config
    respuesta.delete_cookie(
        cfg['COOKIE_SESION'], path='/api',
        httponly=True, secure=cfg['COOKIE_SEGURA'], samesite=cfg['COOKIE_SAMESITE'],
    )


@auth_bp.post('/auth/login')
def login():
    datos = request.get_json(silent=True) or {}

    # Limite por IP: antes de verificar nada (la respuesta no depende del email).
    limites.verificar('login_fallido')
    try:
        token, usuario, perfil = autenticar(
            datos.get('email'), datos.get('contrasena')
        )
    except ErrorAplicacion as error:
        if error.http_status in (401, 429):
            limites.registrar('login_fallido')
        raise

    # El token tambien va en el cuerpo para los clientes de la API (pruebas,
    # scripts). El frontend no lo guarda: usa la cookie.
    respuesta = jsonify({
        'token': token,
        'usuario': usuario.to_dict(),
        'perfil': perfil,
        'intentos_fallidos': intentos_fallidos_previos(usuario.id),
    })
    _poner_cookie(respuesta, token)
    return respuesta, 200


@auth_bp.post('/auth/logout')
@requiere_rol()
def logout():
    """
    Cierre de sesion.

    El JWT no tiene estado en el servidor, asi que el cierre efectivo es
    que el cliente descarte el token. Este endpoint existe igual para
    dejar registro en el log y para que el frontend tenga un unico lugar
    donde cerrar sesion.

    Ademas de borrar la cookie, REVOCA todos los tokens emitidos hasta ahora
    para este usuario (sesiones_validas_desde): un token copiado o robado
    deja de servir en el acto, y se cierra la sesion en todos los equipos.
    """
    db.session.execute(
        text('UPDATE usuarios SET sesiones_validas_desde = NOW(6) WHERE id = :id'),
        {'id': g.usuario_actual.id},
    )
    db.session.commit()
    respuesta = jsonify({'mensaje': 'Sesion cerrada correctamente.'})
    _borrar_cookie(respuesta)
    return respuesta, 200


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
    limites.consumir('recuperar')
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
    limites.consumir('restablecer')
    return jsonify({'vigente': enlace_de_recuperacion_vigente(datos.get('token'))}), 200


@auth_bp.post('/auth/restablecer')
def restablecer():
    datos = request.get_json(silent=True) or {}
    limites.consumir('restablecer')
    mensaje = restablecer_contrasena(
        datos.get('token'), datos.get('contrasena_nueva')
    )
    return jsonify({'mensaje': mensaje}), 200

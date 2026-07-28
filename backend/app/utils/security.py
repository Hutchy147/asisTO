# backend/app/utils/security.py
# Hashing de contrasenas, emision/validacion de JWT y control de acceso
# por rol (RBAC).

import datetime as dt
import logging
from functools import wraps

import bcrypt
import jwt
from flask import current_app, g, jsonify, request

logger = logging.getLogger(__name__)

# Codigos que viajan en la respuesta junto al mensaje. El frontend decide
# con esto: 'token_expirado' manda al login sin mostrar error de sesion,
# 'rol_no_autorizado' muestra el 403 propio. Distinguirlos por el texto del
# mensaje seria fragil.
CODIGO_TOKEN_FALTANTE = 'token_faltante'
CODIGO_TOKEN_INVALIDO = 'token_invalido'
CODIGO_TOKEN_EXPIRADO = 'token_expirado'
CODIGO_ROL_NO_AUTORIZADO = 'rol_no_autorizado'
CODIGO_USUARIO_INACTIVO = 'usuario_inactivo'


# --- Contrasenas ---------------------------------------------------------

def hashear_contrasena(contrasena):
    """Hash bcrypt. El salt se genera solo y queda dentro del hash."""
    return bcrypt.hashpw(contrasena.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verificar_contrasena(contrasena, hash_almacenado):
    """
    Compara en tiempo constante (lo hace bcrypt.checkpw).

    Devuelve False ante cualquier hash corrupto o con formato invalido en
    vez de propagar: los hashes placeholder del seed original no son bcrypt
    valido y harian reventar el login con un 500 en lugar de un rechazo.
    """
    if not contrasena or not hash_almacenado:
        return False
    try:
        return bcrypt.checkpw(
            contrasena.encode('utf-8'), hash_almacenado.encode('utf-8')
        )
    except (ValueError, TypeError):
        logger.warning('Hash de contrasena con formato invalido en la base')
        return False


# --- JWT -----------------------------------------------------------------

def generar_token(usuario):
    """Emite un JWT firmado con el id y el rol del usuario en los claims."""
    ahora = dt.datetime.now(dt.timezone.utc)
    segundos = current_app.config['JWT_ACCESS_TOKEN_EXPIRES']

    payload = {
        'sub': str(usuario.id),   # str: PyJWT valida que 'sub' sea string
        'rol': usuario.rol,
        'email': usuario.email,
        'iat': ahora,
        'exp': ahora + dt.timedelta(seconds=segundos),
    }

    return jwt.encode(
        payload,
        current_app.config['JWT_SECRET_KEY'],
        algorithm=current_app.config['JWT_ALGORITHM'],
    )


def decodificar_token(token):
    """
    Devuelve (payload, None) o (None, codigo_de_error).

    No lanza: el llamador decide el status HTTP segun el codigo.
    """
    try:
        payload = jwt.decode(
            token,
            current_app.config['JWT_SECRET_KEY'],
            algorithms=[current_app.config['JWT_ALGORITHM']],
        )
        return payload, None
    except jwt.ExpiredSignatureError:
        return None, CODIGO_TOKEN_EXPIRADO
    except jwt.InvalidTokenError:
        # Firma mal, algoritmo distinto, payload corrupto: todo lo mismo
        # para el cliente. El detalle va al log.
        logger.info('Token JWT invalido recibido')
        return None, CODIGO_TOKEN_INVALIDO


def obtener_token_del_header():
    """Extrae el token de 'Authorization: Bearer <token>'."""
    header = request.headers.get('Authorization', '')
    if not header.startswith('Bearer '):
        return None
    token = header[len('Bearer '):].strip()
    return token or None


def _respuesta_error(mensaje, codigo, status):
    return jsonify({'mensaje': mensaje, 'codigo': codigo}), status


# --- Control de acceso ---------------------------------------------------

def requiere_rol(*roles):
    """
    Valida el JWT y, si se pasan roles, que el usuario tenga uno de ellos.

    401 si el token falta, es invalido o expiro.
    403 si el token es valido pero el rol no corresponde.

    La distincion importa: 401 significa "volve a autenticarte" y 403
    significa "estas autenticado pero esto no es para vos". Devolver 403
    ante un token vencido dejaria al frontend mostrando un error de
    permisos en vez de mandar al login.

    Sin argumentos (@requiere_rol()) exige token valido y cualquier rol.
    """
    def decorador(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Import local: los modelos importan db desde app
            from app.models import Usuario

            token = obtener_token_del_header()
            if not token:
                return _respuesta_error(
                    'Falta el token de autenticacion.',
                    CODIGO_TOKEN_FALTANTE, 401,
                )

            payload, error = decodificar_token(token)
            if error == CODIGO_TOKEN_EXPIRADO:
                return _respuesta_error(
                    'La sesion expiro. Volve a iniciar sesion.',
                    CODIGO_TOKEN_EXPIRADO, 401,
                )
            if error:
                return _respuesta_error(
                    'El token de autenticacion no es valido.',
                    CODIGO_TOKEN_INVALIDO, 401,
                )

            usuario = db_obtener_usuario(Usuario, payload.get('sub'))

            # El token puede seguir siendo criptograficamente valido despues
            # de que al usuario lo den de baja: se revalida contra la base
            # en cada request, no se confia solo en los claims.
            if usuario is None or not usuario.activo:
                return _respuesta_error(
                    'La cuenta no esta habilitada.',
                    CODIGO_USUARIO_INACTIVO, 401,
                )

            if roles and usuario.rol not in roles:
                logger.info(
                    'Acceso denegado: usuario %s (rol %s) intento %s',
                    usuario.id, usuario.rol, request.path,
                )
                return _respuesta_error(
                    'No tenes permisos para acceder a este recurso.',
                    CODIGO_ROL_NO_AUTORIZADO, 403,
                )

            # Disponible para el endpoint sin volver a consultar
            g.usuario_actual = usuario

            return func(*args, **kwargs)

        return wrapper
    return decorador


def db_obtener_usuario(modelo_usuario, id_usuario):
    """Busca el usuario del token tolerando un 'sub' no numerico."""
    try:
        return modelo_usuario.query.get(int(id_usuario))
    except (TypeError, ValueError):
        return None

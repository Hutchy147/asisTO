# backend/app/utils/security.py
# Hashing de contrasenas, emision/validacion de JWT y control de acceso
# por rol (RBAC).

import datetime as dt
import logging
import secrets
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
CODIGO_SOLICITUD_NO_CONFIABLE = 'solicitud_no_confiable'

# Cabecera que manda el frontend en cada pedido. Un formulario o una imagen de
# otro sitio no pueden ponerla, y un fetch de otro origen con esa cabecera
# dispara una verificacion CORS que el servidor rechaza: es la defensa contra
# CSRF cuando la sesion viaja en cookie.
CABECERA_CLIENTE = 'X-AsisTO'
METODOS_SEGUROS = ('GET', 'HEAD', 'OPTIONS')


# --- Contrasenas ---------------------------------------------------------

# bcrypt ignora todo lo que pase de 72 bytes, y en bcrypt 4.x una entrada
# mas larga levanta ValueError. Se trunca explicitamente: si no, una
# contrasena larguisima saldria por la rama de excepcion sin llegar a
# ejecutar el hash, y responderia mucho mas rapido. Eso seria un canal de
# temporizacion nuevo, justo el que se esta cerrando mas abajo.
LIMITE_BCRYPT_BYTES = 72


def _preparar(contrasena):
    return (contrasena or '').encode('utf-8')[:LIMITE_BCRYPT_BYTES]


def hashear_contrasena(contrasena):
    """Hash bcrypt. El salt se genera solo y queda dentro del hash."""
    return bcrypt.hashpw(_preparar(contrasena), bcrypt.gensalt()).decode('utf-8')


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
        return bcrypt.checkpw(_preparar(contrasena), hash_almacenado.encode('utf-8'))
    except (ValueError, TypeError):
        logger.warning('Hash de contrasena con formato invalido en la base')
        return False


# Hash dummy para igualar tiempos cuando el email no existe.
#
# Se genera una sola vez al importar el modulo, con hashear_contrasena, de
# modo que siempre lleva el MISMO cost factor que los hashes reales: si
# manana se sube el costo, esta rama sube sola y no queda desfasada.
#
# Se genera al importar y no en la primera llamada a proposito: hacerlo
# perezoso dejaria el primer login post-arranque pagando el costo de
# generar el hash, que es un pico visible desde afuera.
#
# El valor hasheado es aleatorio y no se guarda: no hay ninguna contrasena
# real que pueda coincidir con el.
_HASH_DUMMY = hashear_contrasena(secrets.token_urlsafe(32))


def consumir_tiempo_de_verificacion(contrasena):
    """
    Ejecuta un bcrypt real contra un hash descartable y devuelve False.

    Se llama cuando el email no existe, para que esa rama tarde lo mismo
    que la que si encuentra usuario. Sin esto, el login responde en ~2 ms
    cuando el email no esta registrado y en ~214 ms cuando si lo esta: una
    diferencia de dos ordenes de magnitud que permite enumerar que
    direcciones tienen cuenta, aunque el mensaje sea identico.

    Es trabajo real de CPU, no un sleep. Un retardo fijo se distingue igual
    de facil (varianza casi nula frente a la de bcrypt) y no acompana los
    cambios de cost factor.
    """
    bcrypt.checkpw(_preparar(contrasena), _HASH_DUMMY.encode('utf-8'))
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
        # Con decimales (no se redondea al segundo): la revocacion compara
        # contra sesiones_validas_desde, que guarda microsegundos.
        'iat': ahora.timestamp(),
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


def obtener_token():
    """
    (token, viene_de_cookie). El navegador usa la cookie HttpOnly; los
    clientes de la API (pruebas, scripts) pueden seguir mandando el header.
    """
    token = obtener_token_del_header()
    if token:
        return token, False
    token = request.cookies.get(current_app.config.get('COOKIE_SESION', 'asisto_sesion'))
    return (token or None), bool(token)


def token_revocado(usuario, payload):
    """True si el token se emitio antes del ultimo cierre de sesion o cambio de clave."""
    desde = getattr(usuario, 'sesiones_validas_desde_epoch', None)
    if desde is None:
        return False
    try:
        return float(payload.get('iat', 0)) < float(desde)
    except (TypeError, ValueError):
        return True


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

            token, de_cookie = obtener_token()
            if not token:
                return _respuesta_error(
                    'Falta el token de autenticacion.',
                    CODIGO_TOKEN_FALTANTE, 401,
                )

            payload, error = decodificar_token(token)
            if error == CODIGO_TOKEN_EXPIRADO:
                return _respuesta_error(
                    'La sesión expiró. Vuelva a iniciar sesión.',
                    CODIGO_TOKEN_EXPIRADO, 401,
                )
            if error:
                return _respuesta_error(
                    'El token de autenticacion no es valido.',
                    CODIGO_TOKEN_INVALIDO, 401,
                )

            # CSRF: con la sesion en cookie, un pedido que modifica datos tiene
            # que traer la cabecera propia del frontend (ver CABECERA_CLIENTE).
            if de_cookie and request.method not in METODOS_SEGUROS \
                    and request.headers.get(CABECERA_CLIENTE) != '1':
                logger.warning('Pedido con cookie sin cabecera del cliente: %s %s',
                               request.method, request.path)
                return _respuesta_error(
                    'La solicitud no se pudo verificar. Recargue la página e intente nuevamente.',
                    CODIGO_SOLICITUD_NO_CONFIABLE, 403,
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

            # Cerro sesion o cambio la clave despues de emitido este token.
            if token_revocado(usuario, payload):
                return _respuesta_error(
                    'La sesión se cerró. Vuelva a iniciar sesión.',
                    CODIGO_TOKEN_INVALIDO, 401,
                )

            if roles and usuario.rol not in roles:
                logger.info(
                    'Acceso denegado: usuario %s (rol %s) intento %s',
                    usuario.id, usuario.rol, request.path,
                )
                return _respuesta_error(
                    'No tiene permisos para acceder a este recurso.',
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

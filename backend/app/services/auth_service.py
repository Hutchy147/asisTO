# backend/app/services/auth_service.py
# Logica de autenticacion. Las rutas solo traducen HTTP; las decisiones
# viven aca.

import hashlib
import logging
import re
import secrets
import time

from flask import current_app, request
from sqlalchemy import text

from app import db
from app.models import Familiar, Paciente, Rrhh, Terapeuta, Usuario
from app.models.usuario import (
    ROL_FAMILIAR, ROL_PACIENTE, ROL_RRHH, ROL_TERAPEUTA,
)
from app.utils.errors import ErrorAplicacion
from app.utils.security import (
    consumir_tiempo_de_verificacion, generar_token, hashear_contrasena,
    verificar_contrasena,
)
from app.utils.db import reintentar_en_deadlock

logger = logging.getLogger(__name__)

# UN SOLO mensaje para los tres casos de fallo: email inexistente,
# contrasena incorrecta y cuenta deshabilitada.
#
# Si el mensaje distinguiera "ese email no existe" de "contrasena
# incorrecta", cualquiera podria averiguar que direcciones estan dadas de
# alta probando emails de a uno. Con una sola respuesta no se puede.
# Lo mismo con la cuenta inactiva: confirmar que existe pero esta
# deshabilitada ya es informacion.
MENSAJE_CREDENCIALES = 'Email o contrasena incorrectos.'

# Bloqueo por intentos fallidos (Entrega 3). La cuenta se bloquea tras
# MAX_INTENTOS contrasenas incorrectas seguidas y se libera sola pasados
# BLOQUEO_MINUTOS, o antes si la persona restablece su contrasena. El
# contador y el bloqueo viven en la base (p_registrar_login_fallido).
MAX_INTENTOS = 5
BLOQUEO_MINUTOS = 15

# Recuperacion de contrasena: el enlace vale una hora y es de un solo uso.
RECUPERACION_MINUTOS = 60
LARGO_MINIMO_CONTRASENA = 8

MENSAJE_RECUPERACION = (
    'Si el email corresponde a una cuenta activa, se genero un enlace para '
    'restablecer la contrasena.'
)


def _mensaje_bloqueo(segundos):
    minutos = max(1, -(-int(segundos) // 60))  # redondeo hacia arriba
    unidad = 'minuto' if minutos == 1 else 'minutos'
    return (
        'Demasiados intentos fallidos. Intente nuevamente en '
        f'{minutos} {unidad} o restablezca su contraseña.'
    )


def _segundos_de_bloqueo(id_usuario):
    """Segundos que faltan para que termine el bloqueo (0 si no hay)."""
    restantes = db.session.execute(
        text(
            'SELECT TIMESTAMPDIFF(SECOND, NOW(), bloqueado_hasta) '
            'FROM usuarios WHERE id = :id'
        ),
        {'id': id_usuario},
    ).scalar()
    db.session.rollback()  # cierra la transaccion de lectura
    return restantes if restantes and restantes > 0 else 0


def _segundos_de_bloqueo_sin_cuenta(email):
    """
    Bloqueo de un email SIN cuenta, con la misma regla que tiene una cuenta
    real: MAX_INTENTOS fallos en BLOQUEO_MINUTOS. Sin esto, el 429 aparecia
    solo para los emails que existen y permitia averiguar cuales tienen
    cuenta. El contador sale de auditoria_accesos (los fallos sin usuario).
    """
    restantes = db.session.execute(
        text(
            'SELECT TIMESTAMPDIFF(SECOND, NOW(), '
            'DATE_ADD(fecha, INTERVAL :minutos MINUTE)) '
            'FROM auditoria_accesos '
            "WHERE email = :email AND id_usuario IS NULL AND resultado = 'fallido' "
            'AND fecha > DATE_SUB(NOW(), INTERVAL :minutos MINUTE) '
            'ORDER BY fecha DESC, id DESC LIMIT 1 OFFSET :corte'
        ),
        {'email': email[:180], 'minutos': BLOQUEO_MINUTOS, 'corte': MAX_INTENTOS - 1},
    ).scalar()
    db.session.rollback()  # cierra la transaccion de lectura
    return restantes if restantes and restantes > 0 else 0


def _auditar(id_usuario, email, resultado):
    """
    Deja constancia del intento en auditoria_accesos (p_registrar_acceso).

    Si la auditoria falla NO se rompe el login: se loguea y se sigue. La
    alternativa —que una falla de auditoria impida entrar a todos— es peor
    que perder una fila.
    """
    try:
        db.session.execute(
            text('CALL p_registrar_acceso(:id, :email, :resultado, :ip)'),
            {
                'id': id_usuario,
                'email': (email or '')[:180],
                'resultado': resultado,
                'ip': (request.remote_addr or '')[:45] or None,
            },
        )
        db.session.commit()
    except Exception:  # noqa: BLE001 - la auditoria nunca debe tumbar el login
        db.session.rollback()
        logger.exception('No se pudo registrar el acceso en la auditoria')


@reintentar_en_deadlock()
def _registrar_fallo(id_usuario):
    """Suma un intento fallido via procedimiento. -> (bloqueado, segundos)."""
    db.session.execute(
        text(
            'CALL p_registrar_login_fallido(:id, :maximo, :minutos, '
            '@p_bloqueado, @p_hasta)'
        ),
        {'id': id_usuario, 'maximo': MAX_INTENTOS, 'minutos': BLOQUEO_MINUTOS},
    )
    bloqueado = db.session.execute(text('SELECT @p_bloqueado')).scalar()
    db.session.commit()
    return bool(bloqueado)


@reintentar_en_deadlock()
def _registrar_acierto(id_usuario):
    db.session.execute(text('CALL p_registrar_login_ok(:id)'), {'id': id_usuario})
    db.session.commit()


def autenticar(email, contrasena):
    """
    Valida credenciales y devuelve (token, usuario, perfil).

    Lanza ErrorAplicacion con el mismo mensaje ante cualquier fallo.
    """
    if not email or not contrasena:
        raise ErrorAplicacion(MENSAJE_CREDENCIALES, http_status=401)

    email = email.strip().lower()
    usuario = Usuario.query.filter_by(email=email).first()

    # El mensaje identico no alcanza: el TIEMPO tambien delata. Sin esta
    # llamada, cuando el email no existe se sale sin ejecutar bcrypt y la
    # respuesta llega en ~2 ms contra los ~214 ms de la rama que si lo
    # ejecuta. Esos dos ordenes de magnitud permiten enumerar que emails
    # tienen cuenta midiendo el tiempo de respuesta, sin leer el mensaje.
    #
    # Que se filtre no es una contrasena: es si una direccion esta
    # registrada en un centro de terapia ocupacional, que ya es informacion
    # sensible por si sola. Por la misma razon el bloqueo por intentos
    # tambien corre para los emails sin cuenta (ver
    # _segundos_de_bloqueo_sin_cuenta): si solo bloqueara a los reales, el
    # 429 diria cuales existen.
    if usuario is None:
        consumir_tiempo_de_verificacion(contrasena)
        logger.info('Login fallido: email inexistente')
        segundos = _segundos_de_bloqueo_sin_cuenta(email)
        if segundos:
            _auditar(None, email, 'bloqueado')
            raise ErrorAplicacion(_mensaje_bloqueo(segundos), http_status=429)
        _auditar(None, email, 'fallido')
        # El fallo que completa el cupo se bloquea igual que en una cuenta real.
        segundos = _segundos_de_bloqueo_sin_cuenta(email)
        if segundos:
            raise ErrorAplicacion(_mensaje_bloqueo(segundos), http_status=429)
        raise ErrorAplicacion(MENSAJE_CREDENCIALES, http_status=401)

    id_usuario = usuario.id
    contrasena_ok = verificar_contrasena(contrasena, usuario.contrasena_hash)

    # Con la cuenta bloqueada se rechaza AUNQUE la contrasena sea correcta
    # (si no, el bloqueo no frenaria a quien adivina). Se verifico igual
    # antes, para no abrir un canal de tiempos nuevo.
    segundos = _segundos_de_bloqueo(id_usuario)
    if segundos:
        logger.info('Login rechazado: usuario %s bloqueado', id_usuario)
        _auditar(id_usuario, email, 'bloqueado')
        raise ErrorAplicacion(_mensaje_bloqueo(segundos), http_status=429)

    if not contrasena_ok:
        bloqueado = _registrar_fallo(id_usuario)
        logger.info('Login fallido: contrasena incorrecta para usuario %s', id_usuario)
        _auditar(id_usuario, email, 'bloqueado' if bloqueado else 'fallido')
        if bloqueado:
            raise ErrorAplicacion(
                _mensaje_bloqueo(BLOQUEO_MINUTOS * 60), http_status=429
            )
        raise ErrorAplicacion(MENSAJE_CREDENCIALES, http_status=401)

    # El chequeo de activo va DESPUES de verificar la contrasena, y el orden
    # importa: adelantarlo haria que la cuenta deshabilitada respondiera sin
    # pagar el costo de bcrypt, reabriendo el mismo canal por otra rama.
    if not usuario.activo:
        logger.info('Login rechazado: usuario %s esta inactivo', id_usuario)
        # Para quien intenta es el mismo rechazo; en la auditoria se distingue.
        _auditar(id_usuario, email, 'inactiva')
        raise ErrorAplicacion(MENSAJE_CREDENCIALES, http_status=401)

    _registrar_acierto(id_usuario)
    _auditar(id_usuario, email, 'exitoso')
    token = generar_token(usuario)
    logger.info('Login exitoso: usuario %s (rol %s)', usuario.id, usuario.rol)

    return token, usuario, obtener_perfil(usuario)


def obtener_perfil(usuario):
    """
    Datos del perfil segun el rol. None si el rol no tiene perfil cargado.

    Para el rol 'paciente' el perfil sale de la tabla pacientes, que es la
    fuente de verdad de la identidad clinica (regla 5). El vinculo se
    resuelve por pacientes.id_usuario, que puede no existir.
    """
    if usuario.rol == ROL_TERAPEUTA:
        perfil = Terapeuta.query.filter_by(id_usuario=usuario.id).first()
    elif usuario.rol == ROL_RRHH:
        perfil = Rrhh.query.filter_by(id_usuario=usuario.id).first()
    elif usuario.rol == ROL_FAMILIAR:
        perfil = Familiar.query.filter_by(id_usuario=usuario.id).first()
    elif usuario.rol == ROL_PACIENTE:
        perfil = Paciente.query.filter_by(id_usuario=usuario.id).first()
    else:
        perfil = None

    return perfil.to_dict() if perfil else None


# --- Recuperacion de contrasena ------------------------------------------

def _hash_token(token):
    """SHA-256 del token: en la base solo vive el hash, nunca el token."""
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


# Piso de tiempo de la recuperacion: con cuenta el pedido escribe un token
# (~50 ms) y sin cuenta no (~5 ms); esa diferencia delataba que emails existen.
# Los dos caminos tardan al menos esto.
TIEMPO_MINIMO_RECUPERACION = 0.3


def _igualar_tiempo(inicio):
    faltante = TIEMPO_MINIMO_RECUPERACION - (time.perf_counter() - inicio)
    if faltante > 0:
        time.sleep(faltante)


@reintentar_en_deadlock()
def solicitar_recuperacion(email):
    """
    Genera un enlace de recuperacion. Devuelve (mensaje, token_o_None).

    La RESPUESTA es la misma exista o no la cuenta: lo contrario permitiria
    enumerar que emails estan registrados. El token solo se devuelve (para
    mostrarlo en pantalla) cuando RECUPERACION_MOSTRAR_TOKEN esta activo, que
    es el modo de desarrollo: todavia no hay servidor de mail. En produccion
    el token sale por correo y la API no lo devuelve nunca.
    """
    email = (email or '').strip().lower()
    if not email:
        raise ErrorAplicacion('Ingrese su email.', campo='email')

    inicio = time.perf_counter()
    token = secrets.token_urlsafe(32)
    db.session.execute(
        text(
            'CALL p_solicitar_recuperacion(:email, :hash, :minutos, @p_id)'
        ),
        {'email': email, 'hash': _hash_token(token), 'minutos': RECUPERACION_MINUTOS},
    )
    id_usuario = db.session.execute(text('SELECT @p_id')).scalar()
    db.session.commit()
    _auditar(id_usuario, email, 'recuperacion')

    if id_usuario is None:
        logger.info('Recuperacion pedida para un email sin cuenta activa')
        _igualar_tiempo(inicio)
        return MENSAJE_RECUPERACION, None

    logger.info('Recuperacion generada para usuario %s', id_usuario)
    if current_app.config.get('RECUPERACION_MOSTRAR_TOKEN'):
        # Solo desarrollo: sin mail, el enlace se loguea y se devuelve.
        logger.warning('ENLACE DE RECUPERACION (usuario %s): /restablecer/%s', id_usuario, token)
        _igualar_tiempo(inicio)
        return MENSAJE_RECUPERACION, token
    _igualar_tiempo(inicio)
    return MENSAJE_RECUPERACION, None


def enlace_de_recuperacion_vigente(token):
    """
    True si el enlace todavia sirve (existe, no vencio y no se uso). Lo pide
    la pantalla al abrirse, para no hacer completar dos contrasenas y recien
    entonces avisar que el enlace no sirve (F1.3). No dice de quien es.
    """
    if not token or not isinstance(token, str) or len(token) > 200:
        return False
    vigente = db.session.execute(
        text(
            'SELECT 1 FROM usuarios WHERE token_recuperacion = :h AND activo = TRUE '
            'AND token_expira IS NOT NULL AND token_expira >= NOW()'
        ),
        {'h': _hash_token(token)},
    ).scalar()
    db.session.rollback()
    return bool(vigente)


def _validar_contrasena_nueva(contrasena):
    if not contrasena or len(contrasena) < LARGO_MINIMO_CONTRASENA:
        raise ErrorAplicacion(
            f'La contrasena tiene que tener al menos {LARGO_MINIMO_CONTRASENA} caracteres.',
            campo='contrasena_nueva',
        )
    if len(contrasena.encode('utf-8')) > 72:
        raise ErrorAplicacion(
            'La contrasena no puede superar los 72 caracteres.',
            campo='contrasena_nueva',
        )
    if not re.search(r'[A-Za-z]', contrasena) or not re.search(r'\d', contrasena):
        raise ErrorAplicacion(
            'La contrasena tiene que combinar letras y numeros.',
            campo='contrasena_nueva',
        )


@reintentar_en_deadlock()
def restablecer_contrasena(token, contrasena_nueva):
    """Cambia la contrasena con un token valido, via p_restablecer_contrasena."""
    if not token:
        raise ErrorAplicacion(
            'El enlace de recuperacion no es valido o ya vencio', campo='token'
        )
    _validar_contrasena_nueva(contrasena_nueva)

    # Para la auditoria: de quien es el enlace (si es valido).
    dueno = db.session.execute(
        text('SELECT id, email FROM usuarios WHERE token_recuperacion = :h'),
        {'h': _hash_token(token)},
    ).first()

    db.session.execute(
        text(
            'CALL p_restablecer_contrasena(:token, :hash, @p_ok, @p_mensaje)'
        ),
        {'token': _hash_token(token), 'hash': hashear_contrasena(contrasena_nueva)},
    )
    ok, mensaje = db.session.execute(text('SELECT @p_ok, @p_mensaje')).first()
    db.session.commit()

    if not ok:
        raise ErrorAplicacion(mensaje or 'No se pudo restablecer la contrasena.', campo='token')
    if dueno is not None:
        _auditar(dueno[0], dueno[1], 'restablecida')
    return mensaje

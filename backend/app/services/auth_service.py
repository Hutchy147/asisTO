# backend/app/services/auth_service.py
# Logica de autenticacion. Las rutas solo traducen HTTP; las decisiones
# viven aca.

import logging

from app.models import Familiar, Paciente, Rrhh, Terapeuta, Usuario
from app.models.usuario import (
    ROL_FAMILIAR, ROL_PACIENTE, ROL_RRHH, ROL_TERAPEUTA,
)
from app.utils.errors import ErrorAplicacion
from app.utils.security import (
    consumir_tiempo_de_verificacion, generar_token, verificar_contrasena,
)

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


def autenticar(email, contrasena):
    """
    Valida credenciales y devuelve (token, usuario, perfil).

    Lanza ErrorAplicacion con el mismo mensaje ante cualquier fallo.
    """
    if not email or not contrasena:
        raise ErrorAplicacion(MENSAJE_CREDENCIALES, http_status=401)

    usuario = Usuario.query.filter_by(email=email.strip().lower()).first()

    # El mensaje identico no alcanza: el TIEMPO tambien delata. Sin esta
    # llamada, cuando el email no existe se sale sin ejecutar bcrypt y la
    # respuesta llega en ~2 ms contra los ~214 ms de la rama que si lo
    # ejecuta. Esos dos ordenes de magnitud permiten enumerar que emails
    # tienen cuenta midiendo el tiempo de respuesta, sin leer el mensaje.
    #
    # Que se filtre no es una contrasena: es si una direccion esta
    # registrada en un centro de terapia ocupacional, que ya es informacion
    # sensible por si sola. Y se combina mal con que todavia no haya limite
    # de intentos: primero se enumeran cuentas validas, despues se prueban
    # contrasenas contra esas.
    if usuario is None:
        consumir_tiempo_de_verificacion(contrasena)
        logger.info('Login fallido: email inexistente')
        raise ErrorAplicacion(MENSAJE_CREDENCIALES, http_status=401)

    if not verificar_contrasena(contrasena, usuario.contrasena_hash):
        logger.info('Login fallido: contrasena incorrecta para usuario %s', usuario.id)
        raise ErrorAplicacion(MENSAJE_CREDENCIALES, http_status=401)

    # El chequeo de activo va DESPUES de verificar la contrasena, y el orden
    # importa: adelantarlo haria que la cuenta deshabilitada respondiera sin
    # pagar el costo de bcrypt, reabriendo el mismo canal por otra rama.
    if not usuario.activo:
        logger.info('Login rechazado: usuario %s esta inactivo', usuario.id)
        raise ErrorAplicacion(MENSAJE_CREDENCIALES, http_status=401)

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

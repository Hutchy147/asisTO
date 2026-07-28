# backend/app/utils/errors.py
#
# CRITERIO GENERAL DE ERRORES DEL BACKEND
#
# Ningun mensaje crudo de MySQL llega al cliente. El texto nativo incluye
# nombre de base, tabla y constraint: es estructura interna, y por una API
# termina en el navegador. Se traduce a un mensaje propio en castellano y
# el crudo va al log del servidor.
#
# Es el mismo criterio que ya aplican los procedimientos almacenados
# (hallazgo A2 de AUDITORIA.md), ahora extendido a la capa de aplicacion.
#
# Unica excepcion, y es deliberada: los errores 1644 son los SIGNAL
# SQLSTATE '45000' de nuestros propios triggers. Ese texto lo escribimos
# nosotros, ya esta en castellano, no expone estructura y MySQL lo limita
# a 128 caracteres. Ese si se propaga tal cual, porque es exactamente el
# mensaje que el usuario necesita leer ("El paciente ya tiene 4 objetivos
# activos...").

import logging

logger = logging.getLogger(__name__)

# --- Numeros de error de MySQL que nos interesan ---
ERRNO_SIGNAL_TRIGGER = 1644   # SIGNAL SQLSTATE '45000' de nuestros triggers
ERRNO_DEADLOCK = 1213         # Deadlock found when trying to get lock
ERRNO_LOCK_TIMEOUT = 1205     # Lock wait timeout exceeded
ERRNO_DUPLICADO = 1062        # Duplicate entry para una UNIQUE
ERRNO_FK = 1452               # Cannot add or update a child row
ERRNO_FK_BORRADO = 1451       # Cannot delete or update a parent row
ERRNO_CHECK = 3819            # Check constraint is violated

MENSAJE_GENERICO = 'No se pudo completar la operacion. Intente nuevamente.'

# Traducciones por numero de error. Deliberadamente vagas: describen que
# paso en terminos del dominio, sin nombrar tablas ni constraints.
MENSAJES_POR_ERRNO = {
    ERRNO_DEADLOCK: 'La operacion no se pudo completar porque otra la estaba '
                    'modificando al mismo tiempo. Intente nuevamente.',
    ERRNO_LOCK_TIMEOUT: 'La operacion tardo demasiado en obtener acceso a los '
                        'datos. Intente nuevamente.',
    ERRNO_DUPLICADO: 'Ya existe un registro con esos datos.',
    ERRNO_FK: 'Alguno de los datos referenciados no existe.',
    ERRNO_FK_BORRADO: 'No se puede eliminar: hay registros que dependen de este.',
    ERRNO_CHECK: 'Alguno de los valores esta fuera del rango permitido.',
}


class ErrorAplicacion(Exception):
    """
    Error de negocio con un mensaje pensado para el usuario final.

    Lo que llegue aca se devuelve tal cual al cliente, asi que el mensaje
    tiene que estar escrito para una persona, no para un desarrollador.
    """

    def __init__(self, mensaje, http_status=400):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.http_status = http_status


def obtener_errno(error):
    """Extrae el numero de error de MySQL de una excepcion de SQLAlchemy."""
    original = getattr(error, 'orig', error)
    argumentos = getattr(original, 'args', None)
    if argumentos and isinstance(argumentos[0], int):
        return argumentos[0]
    return None


def obtener_texto_signal(error):
    """Texto de un SIGNAL nuestro. Devuelve None si no lo es."""
    original = getattr(error, 'orig', error)
    argumentos = getattr(original, 'args', None)
    if argumentos and len(argumentos) > 1 and isinstance(argumentos[1], str):
        return argumentos[1]
    return None


def traducir_error_db(error, contexto=''):
    """
    Convierte una excepcion de base en un mensaje seguro para el cliente.

    SIEMPRE loguea el error crudo completo. Lo que devuelve es lo unico que
    puede viajar en una respuesta HTTP.
    """
    numero = obtener_errno(error)

    # El crudo va al log del servidor, nunca a la respuesta
    logger.error(
        'Error de base de datos%s (errno=%s): %s',
        f' en {contexto}' if contexto else '',
        numero,
        error,
        exc_info=True,
    )

    if numero == ERRNO_SIGNAL_TRIGGER:
        texto = obtener_texto_signal(error)
        if texto:
            return texto

    return MENSAJES_POR_ERRNO.get(numero, MENSAJE_GENERICO)

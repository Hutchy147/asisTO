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

    `campo` identifica el campo del formulario responsable, cuando se puede
    determinar. Es METADATO al lado del mensaje, no una reescritura: el
    texto sigue viajando igual. Sirve para que el cliente marque el input
    correcto sin tener que adivinar leyendo el mensaje.
    """

    def __init__(self, mensaje, http_status=400, campo=None):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.http_status = http_status
        self.campo = campo


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


# --- Campo responsable de un rechazo -------------------------------------
#
# Qué campo del formulario marcar cuando el servidor rechaza. Viaja como
# metadato junto al mensaje, que NO se toca.
#
# El mapeo se hace por fragmento del mensaje, y eso tiene una condición:
# **si se cambia el texto de un trigger o de un procedimiento, hay que
# cambiar la entrada de esta tabla en el mismo commit.** Que viva acá y no
# en el cliente es justamente lo que lo hace sostenible: el mensaje y su
# mapeo están en el mismo repositorio y se editan juntos. El frontend no
# tiene por qué conocer los textos de la base.
#
# Si un mensaje cambia y esta tabla queda vieja, degrada bien: no se marca
# ningún campo y el aviso de arriba sigue diciendo todo.
CAMPO_POR_FRAGMENTO = (
    ('numero de historia', 'nro_historia'),
    ('ya existe un paciente con ese numero', 'nro_historia'),
    ('objetivo activo con esa descripcion', 'descripcion'),
    ('se superponen con ese horario', 'hora_inicio'),
    ('hora de fin debe ser posterior', 'hora_fin'),
    ('el paciente indicado no existe', 'id_paciente'),
    ('el terapeuta indicado no existe', 'id_terapeuta'),
    ('el usuario indicado no existe', 'id_usuario'),
    ('la sesion indicada no existe', 'id_sesion'),
    ('el objetivo indicado no existe', 'id_objetivo'),
    ('valor de la evolucion', 'valor'),
    ('no pertenece al paciente de esta sesion', 'id_objetivo'),
    ('objetivo archivado', 'id_objetivo'),
    ('ya existe una evolucion para ese objetivo', 'id_objetivo'),
)


def campo_para_mensaje(mensaje):
    """
    Campo del formulario responsable, o None si no se puede determinar.

    None es una respuesta válida y frecuente: el límite de 4 objetivos
    activos, por ejemplo, no es culpa de ningún campo en particular.
    """
    if not mensaje:
        return None

    texto = mensaje.lower()
    for fragmento, campo in CAMPO_POR_FRAGMENTO:
        if fragmento in texto:
            return campo
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

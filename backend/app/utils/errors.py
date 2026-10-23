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
ERRNO_FK = 1452               # Cannot add or update a child row (detallado)
# Misma situacion que 1452 pero en su variante GENERICA. Cual de las dos
# llega DEPENDE DEL USUARIO QUE CONECTA, no de la version del servidor:
# medido el 2026-08-07 con la misma sentencia contra `informes`,
#
#   root         -> 1452, con el nombre de la constraint y de las tablas
#   asisto_app   -> 1216, sin ningun detalle
#
# MySQL le oculta la estructura al usuario sin privilegios sobre la tabla
# padre, que es exactamente lo que este modulo hace a mano. La APP conecta
# como asisto_app, asi que en produccion el errno real es 1216 y con solo
# 1452 mapeado la traduccion no se disparaba nunca.
#
# Van los dos: los tests corren como root y ven 1452, la app ve 1216, y la
# traduccion tiene que ser la misma en los dos casos.
ERRNO_FK_GENERICO = 1216      # Cannot add or update a child row (generico)
ERRNO_FK_BORRADO = 1451       # Cannot delete or update a parent row
ERRNO_DATO_MUY_LARGO = 1406   # Data too long for column
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
    ERRNO_FK_GENERICO: 'Alguno de los datos referenciados no existe.',
    ERRNO_FK_BORRADO: 'No se puede eliminar: hay registros que dependen de este.',
    # Red de seguridad, no la validacion. El largo se rechaza antes, en
    # objetivos_service._descripcion_valida, que si puede decir cuantos
    # caracteres se permiten. Si este mensaje llega a verse, es que algun
    # camino de escritura esquivo esa validacion: vale investigarlo.
    ERRNO_DATO_MUY_LARGO: 'El texto ingresado es mas largo que el maximo '
                          'permitido para ese campo.',
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
#
# EL ORDEN IMPORTA: gana el primer fragmento que aparezca en el mensaje.
# Los mas especificos van arriba.
#
# La tabla se contrasto contra los 51 mensajes que el sistema puede emitir
# —los SIGNAL de los triggers, los p_mensaje de los procedimientos y los
# ErrorAplicacion de los servicios— y no al reves. Revisar solo los
# fragmentos deja pasar el caso que importa: un mensaje real que deberia
# marcar un campo y no lo hace, que es como se encontro que
# "El objetivo esta archivado..." no matcheaba con 'objetivo archivado'.
CAMPO_POR_FRAGMENTO = (
    # --- Objetivos ---
    ('esta archivado: su descripcion quedo fija', 'descripcion'),
    ('objetivo activo con esa descripcion', 'descripcion'),
    ('descripcion del objetivo no puede estar vacia', 'descripcion'),
    ('descripcion del objetivo no puede superar', 'descripcion'),
    # Del errno 1406. Apunta a `descripcion` porque hoy es el unico campo de
    # texto libre largo que un formulario puede desbordar, y llegar acá ya
    # significa que la validacion del servicio se esquivo.
    #
    # LIMITE CONOCIDO: el mapeo es por fragmento y 1406 lo puede disparar
    # cualquier columna. Cuando `pacientes.obra_social` —VARCHAR(120)— se
    # conecte a un formulario, este fragmento va a marcar el campo equivocado.
    # En ese momento hay que darle mensaje propio a cada caso desde el
    # servicio, como hace `descripcion`, en vez de afinar este fragmento.
    ('mas largo que el maximo permitido', 'descripcion'),
    ('ya existe una evolucion para ese objetivo', 'id_objetivo'),
    ('no pertenece al paciente de esta sesion', 'id_objetivo'),
    ('sobre un objetivo archivado', 'id_objetivo'),
    ('el objetivo indicado no existe', 'id_objetivo'),
    # Regla del objetivo posterior a la sesion (2026-08-19). Marca
    # `id_objetivo` y no `id_sesion` a proposito: la sesion es un hecho ya
    # ocurrido y no se mueve, el que esta mal elegido es el objetivo.
    ('el objetivo se creo despues de esa sesion', 'id_objetivo'),
    ('ya tiene evoluciones registradas', 'id_paciente'),

    # --- Pacientes ---
    ('necesita un motivo', 'motivo'),
    ('motivo de la pausa no puede superar', 'motivo'),
    ('tiene que mantener al menos 3 objetivos', 'id_objetivo'),
    ('numero de historia', 'nro_historia'),
    ('ya existe un paciente con ese numero', 'nro_historia'),
    ('el paciente indicado no existe', 'id_paciente'),
    ('no esta en tratamiento activo', 'id_paciente'),
    ('falta indicar el paciente', 'id_paciente'),

    # --- Sesiones ---
    ('se superponen con ese horario', 'hora_inicio'),
    ('hora de fin debe ser posterior', 'hora_fin'),
    ('el estado tiene que ser uno de', 'estado'),
    ('ya tiene evoluciones cargadas', 'estado'),
    ('la sesion indicada no existe', 'id_sesion'),
    # Regla 8 (2026-09-28), solo el mensaje del trigger de INSERT de
    # sesiones. El mensaje de evoluciones ('el terapeuta de la sesion no
    # tenia asignado...') queda A PROPOSITO sin entrada propia: no hay un
    # campo del formulario de evolucion que el usuario pueda corregir para
    # esto, el mismo motivo por el que 'la sesion esta marcada como
    # ausencia' tampoco tiene entrada en esta tabla.
    ('no tiene asignado a este paciente', 'id_paciente'),

    # --- Renglones de la sesion (Entrega 3) ---
    ('renglon no puede estar vacio', 'texto'),
    ('renglon no puede superar', 'texto'),
    ('ya tiene renglones de registro', 'estado'),
    ('ya tiene 30 renglones', 'texto'),
    ('momento del renglon', 'momento'),
    ('no admite registro', 'momento'),
    ('todavia no ocurrio', 'momento'),
    ('el cierre tiene que ser', 'cierre'),

    # --- Asignaciones (HDU 11) ---
    ('ya tiene una asignacion vigente', 'id_terapeuta'),
    ('no puede empezar en una fecha futura', 'fecha_desde'),
    ('fecha de fin de la asignacion', 'fecha_hasta'),

    # --- Recuperacion de contrasena (Entrega 3) ---
    ('enlace de recuperacion no es valido', 'token'),

    # --- Rangos de fecha ---
    ('rango de fechas esta invertido', 'desde'),
    ('el rango pedido es de', 'hasta'),

    # --- Otros ---
    ('el terapeuta indicado no existe', 'id_terapeuta'),
    ('el usuario indicado no existe', 'id_usuario'),
    ('valor de la evolucion', 'valor'),
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

    # Un SIGNAL de un trigger o procedimiento es una regla de negocio que
    # rechazo el pedido (ej. "ya tiene 4 objetivos activos"): no es una falla
    # del servidor. Va como WARNING y sin traza para no tapar los errores reales.
    if numero == ERRNO_SIGNAL_TRIGGER and obtener_texto_signal(error):
        logger.warning(
            'Regla de negocio rechazo la operacion%s: %s',
            f' en {contexto}' if contexto else '', obtener_texto_signal(error),
        )
        return obtener_texto_signal(error)

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

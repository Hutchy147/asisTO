# backend/app/services/objetivos_service.py
# Logica de objetivos terapeuticos.
#
# Las reglas de negocio (maximo 4 activos, unicidad de la descripcion entre
# los activos) las aplica la BASE, no este modulo. Aca no hay ninguna
# reimplementacion de esas reglas: solo se traduce el veredicto de la base a
# un mensaje util. Es la diferencia entre traducir y duplicar — traducir no
# puede divergir, duplicar si.

import logging

from sqlalchemy.exc import IntegrityError

from app import db
from app.models import ObjetivoTerapeutico
from app.models.objetivo import MAXIMO_OBJETIVOS_ACTIVOS
from app.services.pacientes_service import obtener_paciente
from app.utils.db import reintentar_en_deadlock
from app.utils.errors import ERRNO_DUPLICADO, ErrorAplicacion, obtener_errno

logger = logging.getLogger(__name__)

MENSAJE_DESCRIPCION_DUPLICADA = (
    'Ya existe un objetivo activo con esa descripcion para este paciente.'
)


def _traducir_duplicado(error):
    """
    Convierte la violacion de la UNIQUE en un mensaje del dominio.

    La UNIQUE es (id_paciente, descripcion_activa), y descripcion_activa es
    NULL en las filas archivadas. O sea: choca contra un objetivo ACTIVO con
    la misma descripcion, nunca contra uno archivado. Por eso el mensaje
    puede afirmar "activo" sin consultar nada.
    """
    if obtener_errno(error) == ERRNO_DUPLICADO:
        return ErrorAplicacion(MENSAJE_DESCRIPCION_DUPLICADA, http_status=409)
    return None


def listar_por_paciente(id_paciente):
    """Objetivos separados en activos y archivados."""
    paciente = obtener_paciente(id_paciente)

    objetivos = (
        ObjetivoTerapeutico.query
        .filter_by(id_paciente=paciente.id)
        .order_by(ObjetivoTerapeutico.fecha_creacion, ObjetivoTerapeutico.id)
        .all()
    )

    activos = [o.to_dict() for o in objetivos if o.activo]
    archivados = [o.to_dict() for o in objetivos if not o.activo]

    return {
        'paciente': paciente.to_dict_clinico(),
        'activos': activos,
        'archivados': archivados,
        # El cupo se informa para que la interfaz pueda deshabilitar el alta
        # antes de intentarla. NO es la validacion: esa la hace el trigger.
        'cupo': {
            'maximo': MAXIMO_OBJETIVOS_ACTIVOS,
            'usados': len(activos),
            'disponibles': max(0, MAXIMO_OBJETIVOS_ACTIVOS - len(activos)),
        },
    }


def obtener_objetivo(id_objetivo):
    objetivo = ObjetivoTerapeutico.query.get(id_objetivo)
    if objetivo is None:
        raise ErrorAplicacion('El objetivo indicado no existe.', http_status=404)
    return objetivo


@reintentar_en_deadlock()
def crear_objetivo(datos):
    """
    Crea un objetivo activo.

    El limite de 4 lo rechaza el trigger con SIGNAL (errno 1644) y ese
    mensaje se propaga tal cual al cliente; la descripcion duplicada la
    rechaza la UNIQUE (errno 1062) y se traduce aca.
    """
    id_paciente = datos.get('id_paciente')
    descripcion = (datos.get('descripcion') or '').strip()

    if not id_paciente:
        raise ErrorAplicacion('Falta indicar el paciente.')
    if not descripcion:
        raise ErrorAplicacion('La descripcion del objetivo no puede estar vacia.')

    # Cortesia: un 404 claro en vez del error de FK. No es una regla de
    # negocio duplicada, es resolver a que paciente se refiere el pedido.
    paciente = obtener_paciente(id_paciente)

    objetivo = ObjetivoTerapeutico(
        id_paciente=paciente.id,
        descripcion=descripcion,
        activo=True,
    )

    try:
        db.session.add(objetivo)
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        traducido = _traducir_duplicado(error)
        if traducido:
            raise traducido from error
        raise

    logger.info('Objetivo %s creado para paciente %s', objetivo.id, paciente.id)
    return objetivo


@reintentar_en_deadlock()
def editar_descripcion(id_objetivo, datos):
    """Edita solo la descripcion. El estado activo/archivado no se toca aca."""
    descripcion = (datos.get('descripcion') or '').strip()
    if not descripcion:
        raise ErrorAplicacion('La descripcion del objetivo no puede estar vacia.')

    objetivo = obtener_objetivo(id_objetivo)

    if objetivo.descripcion == descripcion:
        # Nada que hacer: se evita una escritura y su lock
        return objetivo

    objetivo.descripcion = descripcion

    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        traducido = _traducir_duplicado(error)
        if traducido:
            raise traducido from error
        raise

    logger.info('Objetivo %s editado', objetivo.id)
    return objetivo


@reintentar_en_deadlock()
def archivar_objetivo(id_objetivo):
    """
    Archiva el objetivo: activo = FALSE.

    NO borra la fila. Las evoluciones ya cargadas apuntan a este objetivo y
    la FK tiene ON DELETE RESTRICT: borrarlo fallaria, y aunque no fallara,
    se perderia historia clinica. Archivar conserva todo y libera el cupo.

    fecha_archivado la escribe el trigger trg_objetivos_limite_activos_update
    al detectar la transicion; no se asigna desde aca para que no queden dos
    lugares que puedan escribir valores distintos.
    """
    objetivo = obtener_objetivo(id_objetivo)

    if not objetivo.activo:
        raise ErrorAplicacion('El objetivo ya estaba archivado.', http_status=409)

    objetivo.activo = False
    db.session.commit()

    logger.info('Objetivo %s archivado', objetivo.id)
    return objetivo

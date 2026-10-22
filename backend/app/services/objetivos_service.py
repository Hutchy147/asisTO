# backend/app/services/objetivos_service.py
# Logica de objetivos terapeuticos.
#
# Las reglas de negocio (maximo 4 activos, unicidad de la descripcion entre
# los activos) las aplica la BASE, no este modulo. Aca no hay ninguna
# reimplementacion de esas reglas: solo se traduce el veredicto de la base a
# un mensaje util. Es la diferencia entre traducir y duplicar — traducir no
# puede divergir, duplicar si.

import logging

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app import db
from app.models import ObjetivoTerapeutico
from app.models.objetivo import (
    MAXIMO_CARACTERES_DESCRIPCION, MAXIMO_OBJETIVOS_ACTIVOS,
)
from app.services.asignaciones_service import exigir_responsable
from app.services.pacientes_service import obtener_paciente
from app.utils.db import reintentar_en_deadlock
from app.utils.errors import ERRNO_DUPLICADO, ErrorAplicacion, obtener_errno

logger = logging.getLogger(__name__)

MENSAJE_DESCRIPCION_DUPLICADA = (
    'Ya existe un objetivo activo con esa descripcion para este paciente.'
)

MENSAJE_DESCRIPCION_VACIA = 'La descripcion del objetivo no puede estar vacia.'

MENSAJE_DESCRIPCION_MUY_LARGA = (
    f'La descripcion del objetivo no puede superar los '
    f'{MAXIMO_CARACTERES_DESCRIPCION} caracteres.'
)


def _descripcion_valida(datos):
    """
    Normaliza y valida la descripcion. Devuelve el texto listo para escribir.

    Por que el largo SI se valida aca, cuando el criterio del modulo es
    traducir y no duplicar: la base rechaza un texto de mas de 700 con errno
    1406, un error crudo cuyo mensaje traducido no puede decir cuantos
    caracteres sobran ni de que campo se trata. Validarlo antes es la misma
    idea que aplican los procedimientos con las FK —chequear primero para dar
    un mensaje util— y no reimplementa ninguna decision: el numero sale de
    MAXIMO_CARACTERES_DESCRIPCION, que acompania al VARCHAR del schema.

    El 1406 igual quedo mapeado en errors.py como red, por si algun camino
    futuro esquiva esta funcion.
    """
    descripcion = (datos.get('descripcion') or '').strip()

    if not descripcion:
        raise ErrorAplicacion(MENSAJE_DESCRIPCION_VACIA, campo='descripcion')

    # Se mide DESPUES del strip: los espacios de los extremos no se guardan,
    # asi que no tiene sentido que consuman cupo y hagan fallar un texto que
    # en realidad entra.
    if len(descripcion) > MAXIMO_CARACTERES_DESCRIPCION:
        raise ErrorAplicacion(MENSAJE_DESCRIPCION_MUY_LARGA, campo='descripcion')

    return descripcion


def _traducir_duplicado(error):
    """
    Convierte la violacion de la UNIQUE en un mensaje del dominio.

    La UNIQUE es (id_paciente, descripcion_activa), y descripcion_activa es
    NULL en las filas archivadas. O sea: choca contra un objetivo ACTIVO con
    la misma descripcion, nunca contra uno archivado. Por eso el mensaje
    puede afirmar "activo" sin consultar nada.
    """
    if obtener_errno(error) == ERRNO_DUPLICADO:
        return ErrorAplicacion(
            MENSAJE_DESCRIPCION_DUPLICADA, http_status=409, campo='descripcion'
        )
    return None


def _seguimiento_de_activos(id_paciente):
    """
    Ultima calificacion y total por objetivo ACTIVO, desde la vista.

    Se usa v_objetivos_activos en vez de recalcularlo: la vista ya define
    que "ultimo" se ordena por fecha y hora de la SESION y no por
    fecha_registro de la evolucion — importa cuando ocurrio la sesion, no
    cuando se cargo. Reescribir ese criterio en Python daria dos versiones
    que pueden divergir.
    """
    filas = db.session.execute(
        text(
            'SELECT id_objetivo, ultimo_valor, fecha_ultima_evolucion, '
            '       total_evoluciones '
            '  FROM v_objetivos_activos WHERE id_paciente = :id'
        ),
        {'id': id_paciente},
    ).all()

    return {
        fila[0]: {
            'ultimo_valor': int(fila[1]) if fila[1] is not None else None,
            'fecha_ultima_evolucion': fila[2].isoformat() if fila[2] else None,
            'total_evoluciones': int(fila[3]),
        }
        for fila in filas
    }


def _seguimiento_de_archivados(id_paciente):
    """
    Lo mismo para los ARCHIVADOS.

    La vista filtra por activo = TRUE, asi que no puede servirlos. Se
    consulta aparte con el mismo criterio de "ultimo", que se mantiene
    alineado a mano con la definicion de la vista en schema.sql.
    """
    filas = db.session.execute(
        text(
            'SELECT o.id, '
            '  (SELECT e.valor FROM evoluciones e JOIN sesiones s ON s.id = e.id_sesion '
            '    WHERE e.id_objetivo = o.id '
            '    ORDER BY s.fecha DESC, s.hora_inicio DESC, e.id DESC LIMIT 1) AS ultimo_valor, '
            '  (SELECT s.fecha FROM evoluciones e JOIN sesiones s ON s.id = e.id_sesion '
            '    WHERE e.id_objetivo = o.id '
            '    ORDER BY s.fecha DESC, s.hora_inicio DESC, e.id DESC LIMIT 1) AS fecha_ultima, '
            '  (SELECT COUNT(*) FROM evoluciones e WHERE e.id_objetivo = o.id) AS total '
            'FROM objetivos_terapeuticos o '
            'WHERE o.id_paciente = :id AND o.activo = FALSE'
        ),
        {'id': id_paciente},
    ).all()

    return {
        fila[0]: {
            'ultimo_valor': int(fila[1]) if fila[1] is not None else None,
            'fecha_ultima_evolucion': fila[2].isoformat() if fila[2] else None,
            'total_evoluciones': int(fila[3]),
        }
        for fila in filas
    }


def listar_por_paciente(id_paciente):
    """
    Objetivos separados en activos y archivados, con su seguimiento.

    Incluye a los pacientes dados de baja: es lectura de historia clinica.
    Crear o editar un objetivo sigue rechazandolos — ver `crear_objetivo`,
    que llama a `obtener_paciente` con el default. Lectura abierta,
    escritura restringida.
    """
    paciente = obtener_paciente(id_paciente, incluir_inactivos=True)

    objetivos = (
        ObjetivoTerapeutico.query
        .filter_by(id_paciente=paciente.id)
        .order_by(ObjetivoTerapeutico.fecha_creacion, ObjetivoTerapeutico.id)
        .all()
    )

    seguimiento = {
        **_seguimiento_de_activos(paciente.id),
        **_seguimiento_de_archivados(paciente.id),
    }

    def con_seguimiento(objetivo):
        datos = objetivo.to_dict()
        datos['seguimiento'] = seguimiento.get(
            objetivo.id,
            {'ultimo_valor': None, 'fecha_ultima_evolucion': None, 'total_evoluciones': 0},
        )
        return datos

    activos = [con_seguimiento(o) for o in objetivos if o.activo]
    archivados = [con_seguimiento(o) for o in objetivos if not o.activo]

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


def _verificar_escritura(objetivo):
    """
    Solo el terapeuta responsable toca los objetivos de un paciente, y solo
    mientras el paciente esta en tratamiento: con la baja (pausa o alta) los
    objetivos quedan de solo lectura.
    """
    exigir_responsable(objetivo.id_paciente, 'modificar sus objetivos',
                       omitir_si_de_baja=True)
    paciente = obtener_paciente(objetivo.id_paciente, incluir_inactivos=True)
    if not paciente.activo:
        raise ErrorAplicacion(
            'El paciente está dado de baja: sus objetivos quedan solo para lectura.',
            http_status=409,
        )


def _avisar(objetivo, accion):
    """Aviso a la familia (Entrega 4), ya confirmado el cambio. Mejor esfuerzo."""
    from app.services.notificaciones_service import avisar_objetivo
    avisar_objetivo(objetivo, accion)


@reintentar_en_deadlock()
def crear_objetivo(datos):
    """
    Crea un objetivo activo.

    El limite de 4 lo rechaza el trigger con SIGNAL (errno 1644) y ese
    mensaje se propaga tal cual al cliente; la descripcion duplicada la
    rechaza la UNIQUE (errno 1062) y se traduce aca.
    """
    id_paciente = datos.get('id_paciente')

    if not id_paciente:
        raise ErrorAplicacion('Falta indicar el paciente.')

    descripcion = _descripcion_valida(datos)

    # Cortesia: un 404 claro en vez del error de FK. No es una regla de
    # negocio duplicada, es resolver a que paciente se refiere el pedido.
    paciente = obtener_paciente(id_paciente)
    exigir_responsable(paciente.id, 'modificar sus objetivos')

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
    _avisar(objetivo, 'agregado')
    return objetivo


@reintentar_en_deadlock()
def editar_descripcion(id_objetivo, datos):
    """
    Edita solo la descripcion. El estado activo/archivado no se toca aca.

    Un objetivo ARCHIVADO no se puede editar: su descripcion es inmutable
    porque hay evoluciones historicas puntuando contra ese texto. Esa regla
    NO esta reimplementada aca: la aplica el trigger
    trg_objetivos_limite_activos_update y su mensaje se propaga tal cual al
    cliente (errno 1644). Agregar el chequeo tambien en Python daria dos
    versiones que pueden divergir, y la de la base es la que vale para
    cualquier camino de escritura, no solo para este endpoint.
    """
    descripcion = _descripcion_valida(datos)

    objetivo = obtener_objetivo(id_objetivo)
    _verificar_escritura(objetivo)

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
    _avisar(objetivo, 'modificado')
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
    _verificar_escritura(objetivo)

    if not objetivo.activo:
        raise ErrorAplicacion('El objetivo ya estaba archivado.', http_status=409)

    # El trigger exige el minimo de 3 activos (bajo lock del paciente); su
    # SIGNAL lo traduce el handler global de SQLAlchemyError.
    objetivo.activo = False
    db.session.commit()

    logger.info('Objetivo %s archivado', objetivo.id)
    _avisar(objetivo, 'archivado')
    return objetivo

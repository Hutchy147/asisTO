# backend/app/services/evoluciones_service.py
#
# Las reglas 2, 3 y 4 las aplican los triggers de la base. Aca NO se
# reimplementan: se llama a p_registrar_evolucion y se propaga su
# p_mensaje, que ya viene con el texto del SIGNAL en castellano.
#
# Las unicas validaciones propias son las que la base no puede expresar o
# las que darian un error confuso: que la sesion exista, que sea del
# terapeuta logueado, y que el paciente tenga algun objetivo activo contra
# el cual calificar.

import logging

from sqlalchemy import text

from app import db
from app.models import Evolucion, ObjetivoTerapeutico, Sesion
from app.models.evolucion import VALOR_MAXIMO, VALOR_MINIMO
from app.services.sesiones_service import obtener_sesion, terapeuta_actual
from app.utils.db import reintentar_en_deadlock
from app.utils.errors import ErrorAplicacion

logger = logging.getLogger(__name__)


def listar_por_sesion(id_sesion):
    """Evoluciones de una sesion. Lectura abierta a cualquier terapeuta."""
    sesion = obtener_sesion(id_sesion)

    evoluciones = (
        db.session.query(Evolucion, ObjetivoTerapeutico)
        .join(ObjetivoTerapeutico, ObjetivoTerapeutico.id == Evolucion.id_objetivo)
        .filter(Evolucion.id_sesion == sesion.id)
        .order_by(Evolucion.id)
        .all()
    )

    resultado = []
    for evolucion, objetivo in evoluciones:
        datos = evolucion.to_dict()
        datos['objetivo'] = {
            'id': objetivo.id,
            'descripcion': objetivo.descripcion,
            'activo': bool(objetivo.activo),
        }
        resultado.append(datos)

    return {
        'id_sesion': sesion.id,
        'evoluciones': resultado,
        'total': len(resultado),
    }


@reintentar_en_deadlock()
def registrar_evolucion(datos):
    """Registra via p_registrar_evolucion."""
    id_sesion = datos.get('id_sesion')
    id_objetivo = datos.get('id_objetivo')
    valor = datos.get('valor')
    observaciones = datos.get('observaciones')

    if not id_sesion or not id_objetivo:
        raise ErrorAplicacion('Faltan datos obligatorios: id_sesion, id_objetivo.')

    # Rango del valor: el CHECK de la base lo rechaza con un error crudo
    # (errno 3819), asi que se traduce antes para dar algo legible. El
    # procedimiento tambien lo valida; la autoridad sigue siendo la base.
    try:
        valor = int(valor)
    except (TypeError, ValueError):
        raise ErrorAplicacion(
            f'El valor de la evolucion tiene que ser un numero entre '
            f'{VALOR_MINIMO} y {VALOR_MAXIMO}.'
        )
    if not VALOR_MINIMO <= valor <= VALOR_MAXIMO:
        raise ErrorAplicacion(
            f'El valor de la evolucion tiene que estar entre '
            f'{VALOR_MINIMO} y {VALOR_MAXIMO}.'
        )

    sesion = obtener_sesion(id_sesion)

    # ESCRITURA RESTRINGIDA al terapeuta de la sesion. La lectura es
    # abierta (ver sesiones_service.obtener_detalle), pero una evolucion es
    # la valoracion clinica de quien atendio: cargarla en nombre de otro
    # falsea la autoria de la historia clinica.
    terapeuta = terapeuta_actual()
    if sesion.id_terapeuta != terapeuta.id:
        raise ErrorAplicacion(
            'Solo el terapeuta que atendio la sesion puede cargarle evolucion.',
            http_status=403,
        )

    # Cortesia: si el paciente no tiene NINGUN objetivo activo, el trigger
    # rechazaria con "el objetivo no pertenece al paciente" o "no existe",
    # que no explica el problema real. No es duplicar una regla: la base no
    # tiene ninguna que diga "el paciente debe tener objetivos activos".
    activos = (
        ObjetivoTerapeutico.query
        .filter_by(id_paciente=sesion.id_paciente, activo=True)
        .count()
    )
    if activos == 0:
        raise ErrorAplicacion(
            'El paciente no tiene objetivos activos: no hay contra que '
            'calificar. Creá un objetivo antes de cargar la evolucion.',
            http_status=409,
        )

    db.session.execute(
        text(
            'CALL p_registrar_evolucion(:id_sesion, :id_objetivo, :valor, '
            ':observaciones, @p_id_evolucion, @p_mensaje)'
        ),
        {
            'id_sesion': sesion.id,
            'id_objetivo': id_objetivo,
            'valor': valor,
            'observaciones': observaciones,
        },
    )

    id_creada, mensaje = db.session.execute(
        text('SELECT @p_id_evolucion, @p_mensaje')
    ).first()

    db.session.commit()

    if id_creada is None:
        # p_mensaje trae el texto del SIGNAL del trigger tal cual: sesion en
        # ausencia, objetivo de otro paciente, objetivo archivado o
        # duplicado. Se propaga sin reescribir.
        raise ErrorAplicacion(mensaje or 'No se pudo registrar la evolucion.')

    evolucion = Evolucion.query.get(int(id_creada))
    logger.info(
        'Evolucion %s registrada en sesion %s por terapeuta %s',
        evolucion.id, sesion.id, terapeuta.id,
    )

    return evolucion, mensaje

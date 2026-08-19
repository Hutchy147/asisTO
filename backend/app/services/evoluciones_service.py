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
from app.services.pacientes_service import obtener_paciente
from app.services.sesiones_service import (
    obtener_sesion, resolver_rango, terapeuta_actual,
)
from app.utils.db import reintentar_en_deadlock
from app.utils.errors import ErrorAplicacion

logger = logging.getLogger(__name__)


def _resolver_periodo(desde, hasta, paciente):
    """
    Rango del historial de evolucion.

    Sin fechas devuelve el TRATAMIENTO ENTERO y ese caso NO paga el tope de
    366 dias. El tope existe para que nadie pida "1900 a 2100"; recortar el
    default en cambio dejaria el grafico a medias sin decirlo, que es peor
    que negarse. El default esta acotado por la realidad del paciente, no
    por lo que pida el llamador.

    "Tratamiento entero" son sus SESIONES, no el almanaque. Hasta el
    2026-08-19 esto devolvia `fecha_alta -> date.today()`, que decia una cosa
    en el docstring y hacia otra: las dos mitades solo coinciden mientras
    ninguna sesion caiga fuera de ese rango. Una terapeuta ocupacional
    externa agendo una sesion para dos dias despues y le cargo la evolucion
    en el acto; para un paciente dado de alta ese mismo dia la ventana media
    UN dia, la sesion quedaba afuera, y con ella TODA la serie —las series
    salen del FROM sesiones del procedimiento—. La ficha le contesto
    "Todavia no hay nada que graficar" con el dato guardado. El borde de
    abajo tenia el mismo defecto al reves: una sesion cargada con fecha
    anterior al alta tampoco entraba.

    Por eso los dos extremos salen de MIN/MAX de las sesiones del paciente,
    ensanchados hasta `fecha_alta` para que un paciente sin ninguna sesion
    siga teniendo un periodo con sentido en vez de dos None. Se eligio esto
    y no "sin tope" justamente para que el default siga acotado por los
    datos del paciente: sin tope, la ventana pasaria a depender del
    almanaque y no de su tratamiento, que es lo contrario del contrato.

    Sobre el tope de 366 dias: el default sigue sin pagarlo, a proposito. La
    diferencia es que ahora no puede crecer sola —lo maximo que abarca es de
    la primera a la ultima sesion que el paciente REALMENTE tiene—, asi que
    un tratamiento largo se grafica entero y no hay forma de pedir un siglo
    por esta puerta. Con fechas explicitas el tope se aplica igual.

    Con fechas explicitas se aplica la misma validacion que
    `GET /api/sesiones`: rango invertido y rango excesivo son errores, no
    listas vacias. Se reusa `resolver_rango` para no tener dos versiones de
    la misma regla.
    """
    if not desde and not hasta:
        # Una sola consulta para los dos extremos. MIN/MAX siempre devuelven
        # una fila: sin sesiones son (None, None), no un resultado vacio.
        primera, ultima = (
            db.session.query(db.func.min(Sesion.fecha), db.func.max(Sesion.fecha))
            .filter(Sesion.id_paciente == paciente.id)
            .one()
        )

        fecha_desde = min(paciente.fecha_alta, primera) if primera else paciente.fecha_alta
        fecha_hasta = max(paciente.fecha_alta, ultima) if ultima else paciente.fecha_alta

        return fecha_desde, fecha_hasta, True

    return (*resolver_rango(desde, hasta), False)


def evolucion_de_paciente(id_paciente, desde=None, hasta=None):
    """
    Serie de evolucion del paciente, lista para graficar.

    Devuelve UNA serie por objetivo que estuvo vivo en el periodo, con un
    punto por cada sesion de ese periodo. `valor: null` en un punto significa
    "esa sesion ocurrio y este objetivo no se califico", que es distinto de
    que no haya habido sesion — la diferencia es clinica y por eso el
    procedimiento devuelve las dos cosas en una sola consulta.

    Incluye a los pacientes dados de baja: es lectura de historia clinica.
    """
    paciente = obtener_paciente(id_paciente, incluir_inactivos=True)
    fecha_desde, fecha_hasta, completo = _resolver_periodo(desde, hasta, paciente)

    filas = db.session.execute(
        text('CALL p_evolucion_paciente(:id, :desde, :hasta, @p_mensaje)'),
        {'id': paciente.id, 'desde': fecha_desde, 'hasta': fecha_hasta},
    ).all()

    mensaje = db.session.execute(text('SELECT @p_mensaje')).scalar()

    # Las filas vienen ordenadas por objetivo y fecha, asi que agrupar es
    # recorrer una vez. El orden lo fija el procedimiento y no se reordena
    # aca: si se reordenara, el criterio quedaria en dos lugares.
    series = []
    por_objetivo = {}
    calificados = 0

    for fila in filas:
        (id_sesion, fecha, hora_inicio, estado_sesion, id_objetivo, descripcion,
         objetivo_activo, fecha_archivado, valor, observaciones, terapeuta) = fila

        serie = por_objetivo.get(id_objetivo)
        if serie is None:
            serie = {
                'id': int(id_objetivo),
                'descripcion': descripcion,
                'activo': bool(objetivo_activo),
                # Con que fecha termina la linea de un objetivo archivado.
                # Sin esto la serie quedaria abierta como si siguiera vigente.
                'fecha_archivado': fecha_archivado.isoformat() if fecha_archivado else None,
                'puntos': [],
            }
            por_objetivo[id_objetivo] = serie
            series.append(serie)

        if valor is not None:
            calificados += 1

        serie['puntos'].append({
            'id_sesion': int(id_sesion),
            'fecha': fecha.isoformat(),
            # hora_inicio llega como timedelta desde el driver
            'hora_inicio': str(hora_inicio),
            'estado_sesion': estado_sesion,
            # null = la sesion ocurrio y este objetivo no se califico
            'valor': int(valor) if valor is not None else None,
            'observaciones': observaciones,
            'terapeuta': terapeuta,
        })

    return {
        'paciente': paciente.to_dict_clinico(),
        'periodo': {
            'desde': fecha_desde.isoformat() if fecha_desde else None,
            'hasta': fecha_hasta.isoformat() if fecha_hasta else None,
            # Para que la interfaz pueda decir "todo el tratamiento" en vez
            # de dibujar dos fechas que el usuario no eligio.
            'completo': completo,
        },
        'objetivos': series,
        'total_puntos': len(filas),
        'total_calificados': calificados,
        'mensaje': mensaje,
    }


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

    # El terapeuta viaja como parametro: el procedimiento revalida la
    # autoria por su cuenta. La comprobacion de arriba se conserva porque
    # da un 403 con mensaje propio antes de tocar la base; esta es la
    # segunda linea, no un reemplazo. Ver el comentario de autoria en
    # p_registrar_evolucion (schema.sql).
    db.session.execute(
        text(
            'CALL p_registrar_evolucion(:id_sesion, :id_objetivo, :valor, '
            ':observaciones, :id_terapeuta, @p_id_evolucion, @p_mensaje)'
        ),
        {
            'id_sesion': sesion.id,
            'id_objetivo': id_objetivo,
            'valor': valor,
            'observaciones': observaciones,
            'id_terapeuta': terapeuta.id,
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

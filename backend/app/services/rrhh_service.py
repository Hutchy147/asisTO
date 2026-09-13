# backend/app/services/rrhh_service.py
# Reporte de asistencias para RRHH. Solo recuento administrativo.
#
# QUE ES RRHH ACA: lleva el recuento de que terapeuta atendio a que paciente
# y registra las ausencias, del paciente y del terapeuta, para la parte
# administrativa del centro. La facturacion NO es parte del sistema.
#
# EL LIMITE CLINICO NO LO SOSTIENE LA BASE. No hay un usuario de MySQL
# separado para RRHH ni GRANTs por columna: el hallazgo A3 sigue abierto. Lo
# unico que hoy impide que salga contenido clinico por este camino son dos
# listas escritas a mano — la del SELECT de `p_reporte_sesiones_periodo` y
# COLUMNAS_REPORTE de este archivo — y las dos tienen que seguir siendo
# angostas y nombradas.

import datetime as dt
import logging

from sqlalchemy import text

from app import db
from app.models.sesion import ESTADO_AUSENCIA, ORIGENES_AUSENCIA
from app.utils.errors import ErrorAplicacion

logger = logging.getLogger(__name__)

# Mismo tope que GET /api/sesiones, por el mismo motivo: un rango sin limite
# permite pedir "desde 1900 hasta 2100" y traerse todo en una respuesta.
MAXIMO_DIAS_RANGO = 366

# LA PROYECCION DE RRHH, CERRADA Y NOMBRADA UNA POR UNA.
#
# No se arma desde `Sesion.to_dict()` ni desde ninguna proyeccion pensada
# para el terapeuta, y no es preferencia de estilo: `to_dict()` incluye
# `notas` POR DEFECTO (`con_notas=True`) y ademas cambia cuando cambia el
# modelo. Colgar el limite de RRHH de acordarse de pasarle `con_notas=False`
# en cada llamada es exactamente la clase de limite que se rompe solo el dia
# que alguien agrega una llamada.
#
# Aca al reves: lo que no esta en esta tupla NO PUEDE SALIR, porque el dict
# de respuesta se arma recorriendo esta tupla y nada mas. Agregar una columna
# clinica requiere escribirla en esta linea, que es donde se ve.
COLUMNAS_REPORTE = (
    'id_sesion',
    'fecha',
    'hora_inicio',
    'hora_fin',
    'estado',
    'ausencia_de',
    # El id ADEMAS del nombre: identifica donde el nombre solo no alcanza
    # (dos homonimos son una sola fila para un reporte administrativo). No
    # amplia el alcance de RRHH: es la misma clave que ya viajaba como filtro
    # en `p_id_terapeuta`, y no hay endpoint clinico alcanzable con ese rol.
    'id_terapeuta',
    'terapeuta',
    'paciente',
    'nro_historia',
    'superposiciones',
)

# La fecha en que `ausencia_de` empezo a existir y a exigirse. Antes de esto
# una ausencia no podia declarar quien falto: la columna no existia. Se usa
# para que el reporte diga de que periodo puede afirmar el reparto y de cual
# no, en vez de dejar que quien lo lea lo suponga.
DESDE_AUSENCIA_DECLARABLE = dt.date(2026, 9, 10)


def _fecha(valor, etiqueta):
    """Parsea una fecha ISO o corta con un mensaje propio."""
    if not valor:
        raise ErrorAplicacion(f'Falta la fecha {etiqueta}.')
    try:
        return dt.date.fromisoformat(valor)
    except (TypeError, ValueError):
        raise ErrorAplicacion(
            f'La fecha {etiqueta} tiene que venir como AAAA-MM-DD.'
        )


def _formatear(valor):
    """Fechas y horas a texto; el resto tal cual.

    `hora_fin` es NULLABLE y `ausencia_de` tambien, asi que el None se
    respeta y no se convierte en cadena vacia: en JSON null y "" no
    significan lo mismo, y aca la diferencia entre "no declarado" y
    "declarado vacio" es justamente lo que el reporte tiene que conservar.
    """
    if valor is None:
        return None
    if isinstance(valor, dt.date):
        return valor.isoformat()
    if isinstance(valor, dt.timedelta):
        # MySQL devuelve TIME como timedelta
        total = int(valor.total_seconds())
        return f'{total // 3600:02d}:{(total % 3600) // 60:02d}'
    if isinstance(valor, dt.time):
        return valor.strftime('%H:%M')
    return valor


def reporte_sesiones(desde, hasta, id_terapeuta=None):
    """
    Reporte de asistencias del periodo, via p_reporte_sesiones_periodo.

    Devuelve el detalle y un resumen. El resumen se calcula SOBRE LAS MISMAS
    FILAS que se devuelven, no con un segundo SELECT: asi no puede decir un
    numero que el detalle no respalde. Si alguna vez esto se pagina, el
    resumen deja de poder calcularse aca y pasa al procedimiento.
    """
    fecha_desde = _fecha(desde, 'desde')
    fecha_hasta = _fecha(hasta, 'hasta')

    if fecha_hasta < fecha_desde:
        raise ErrorAplicacion('La fecha hasta no puede ser anterior a la desde.')

    dias = (fecha_hasta - fecha_desde).days + 1
    if dias > MAXIMO_DIAS_RANGO:
        raise ErrorAplicacion(
            f'El rango no puede superar {MAXIMO_DIAS_RANGO} dias.'
        )

    if id_terapeuta is not None:
        try:
            id_terapeuta = int(id_terapeuta)
        except (TypeError, ValueError):
            raise ErrorAplicacion('El id de terapeuta tiene que ser un numero.')

    resultado = db.session.execute(
        text(
            'CALL p_reporte_sesiones_periodo(:desde, :hasta, :id_terapeuta, '
            '@p_mensaje)'
        ),
        {
            'desde': fecha_desde,
            'hasta': fecha_hasta,
            'id_terapeuta': id_terapeuta,
        },
    )

    # Se leen las filas ANTES de pedir @p_mensaje: el CALL deja el cursor
    # sobre el primer result set y la consulta siguiente lo descarta.
    filas = resultado.mappings().all()
    resultado.close()

    mensaje = db.session.execute(text('SELECT @p_mensaje')).scalar()
    # El CALL no escribe nada, pero abrio transaccion: se cierra para no
    # dejarla colgada ocupando una conexion del pool.
    db.session.commit()

    # El dict se arma recorriendo COLUMNAS_REPORTE, no las claves de la
    # fila. Si el procedimiento empezara a devolver una columna de mas, por
    # este camino NO saldria: habria que agregarla arriba a mano.
    sesiones = [
        {clave: _formatear(fila.get(clave)) for clave in COLUMNAS_REPORTE}
        for fila in filas
    ]

    logger.info(
        'Reporte RRHH %s a %s (terapeuta %s): %s sesiones',
        fecha_desde, fecha_hasta, id_terapeuta or 'todos', len(sesiones),
    )

    return {
        'desde': fecha_desde.isoformat(),
        'hasta': fecha_hasta.isoformat(),
        'id_terapeuta': id_terapeuta,
        'sesiones': sesiones,
        'resumen': _resumir(sesiones, fecha_desde),
        # p_mensaje del procedimiento, propagado tal cual
        'mensaje': mensaje,
    }


def _resumir(sesiones, fecha_desde):
    """
    Recuento del periodo. Tres baldes para las ausencias, no dos.

    `sin_declarar` NO se reparte entre paciente y terapeuta ni se suma a
    ninguno de los dos. Son las ausencias cargadas antes de que
    `ausencia_de` existiera: el dato no esta y no hay forma de reponerlo,
    asi que el reporte lo dice en vez de elegir uno.
    """
    por_estado = {}
    ausencias = {origen: 0 for origen in ORIGENES_AUSENCIA}
    ausencias['sin_declarar'] = 0

    for sesion in sesiones:
        estado = sesion['estado']
        por_estado[estado] = por_estado.get(estado, 0) + 1

        if estado == ESTADO_AUSENCIA:
            origen = sesion['ausencia_de']
            if origen in ausencias:
                ausencias[origen] += 1
            else:
                ausencias['sin_declarar'] += 1

    return {
        'total_sesiones': len(sesiones),
        'por_estado': por_estado,
        'ausencias': ausencias,
        # Ver la nota de DESDE_AUSENCIA_DECLARABLE. Que el periodo empiece
        # antes de esa fecha no invalida el reporte: avisa que el reparto de
        # ausencias puede venir incompleto por origen, y por que.
        'ausencia_declarable_desde': DESDE_AUSENCIA_DECLARABLE.isoformat(),
        'periodo_anterior_a_ausencia_declarable': (
            fecha_desde < DESDE_AUSENCIA_DECLARABLE
        ),
    }

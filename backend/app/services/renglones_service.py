# backend/app/services/renglones_service.py
# Renglones de la sesion (notas de campo, Entrega 3). Las reglas las aplican
# los procedimientos p_*_renglon; aca se traduce.
#
# Lectura abierta a cualquier terapeuta (misma politica que el detalle de la
# sesion); escritura solo del terapeuta de la sesion.

import logging

from sqlalchemy import text

from app import db
from app.models import Sesion, SesionObjetivo, SesionRenglon
from app.services.sesiones_service import obtener_sesion, terapeuta_actual
from app.utils.db import reintentar_en_deadlock
from app.utils.errors import ErrorAplicacion

logger = logging.getLogger(__name__)


def _estado_http(mensaje):
    """El procedimiento rechaza con un p_mensaje: se lo convierte en status."""
    texto = (mensaje or '').lower()
    if 'no existe' in texto:
        return 404
    if texto.startswith('solo el terapeuta'):
        return 403
    return 400


def _falla(mensaje, defecto):
    return ErrorAplicacion(mensaje or defecto, http_status=_estado_http(mensaje))


def listar_de_sesion(id_sesion):
    """
    Plan, registro y arrastre de una sesion.

    `arrastre`: renglones de PLAN todavia pendientes de sesiones ANTERIORES
    del mismo paciente atendidas por el mismo terapeuta (lo que en el
    cuaderno se anota al lado y se pasa al dia siguiente). Un renglon deja de
    arrastrarse cuando se lo cierra como hecho o descartado.
    """
    sesion = obtener_sesion(id_sesion)

    propios = (
        SesionRenglon.query
        .filter_by(id_sesion=sesion.id)
        .order_by(SesionRenglon.orden, SesionRenglon.id)
        .all()
    )

    arrastre = (
        db.session.query(SesionRenglon, Sesion)
        .join(Sesion, Sesion.id == SesionRenglon.id_sesion)
        .filter(
            Sesion.id_paciente == sesion.id_paciente,
            Sesion.id_terapeuta == sesion.id_terapeuta,
            Sesion.fecha < sesion.fecha,
            SesionRenglon.momento == 'plan',
            SesionRenglon.cierre.is_(None),
        )
        .order_by(Sesion.fecha, SesionRenglon.orden, SesionRenglon.id)
        .all()
    )

    return {
        'id_sesion': sesion.id,
        'es_propia': sesion.id_terapeuta == terapeuta_actual().id,
        # Ids de los objetivos del paciente que se planea trabajar. El texto
        # de cada uno ya viaja en el detalle de la sesion (objetivos_activos).
        'objetivos_plan': sorted(
            o.id_objetivo for o in SesionObjetivo.query.filter_by(id_sesion=sesion.id).all()
        ),
        'plan': [r.to_dict() for r in propios if r.momento == 'plan'],
        'registro': [r.to_dict() for r in propios if r.momento == 'registro'],
        'arrastre': [
            {**r.to_dict(), 'fecha_sesion': s.fecha.isoformat()} for r, s in arrastre
        ],
    }


@reintentar_en_deadlock()
def agregar_renglon(id_sesion, datos):
    terapeuta = terapeuta_actual()
    obtener_sesion(id_sesion)  # 404 limpio antes de llamar al procedimiento

    db.session.execute(
        text('CALL p_agregar_renglon(:s, :t, :m, :x, :d, @p_id, @p_mensaje)'),
        {
            's': id_sesion,
            't': terapeuta.id,
            'm': (datos.get('momento') or '').strip(),
            'x': datos.get('texto'),
            'd': bool(datos.get('destacado')),
        },
    )
    id_renglon, mensaje = db.session.execute(text('SELECT @p_id, @p_mensaje')).first()
    db.session.commit()

    if id_renglon is None:
        raise _falla(mensaje, 'No se pudo guardar el renglon.')
    return SesionRenglon.query.get(int(id_renglon)).to_dict(), mensaje


@reintentar_en_deadlock()
def editar_renglon(id_renglon, datos):
    terapeuta = terapeuta_actual()

    db.session.execute(
        text('CALL p_editar_renglon(:r, :t, :x, :d, @p_ok, @p_mensaje)'),
        {
            'r': id_renglon,
            't': terapeuta.id,
            'x': datos.get('texto'),
            'd': bool(datos.get('destacado')),
        },
    )
    ok, mensaje = db.session.execute(text('SELECT @p_ok, @p_mensaje')).first()
    db.session.commit()

    if not ok:
        raise _falla(mensaje, 'No se pudo editar el renglon.')
    db.session.expire_all()
    return SesionRenglon.query.get(id_renglon).to_dict(), mensaje


@reintentar_en_deadlock()
def cerrar_renglon(id_renglon, datos):
    terapeuta = terapeuta_actual()
    cierre = datos.get('cierre')
    cierre = '' if cierre is None else str(cierre).strip()

    db.session.execute(
        text('CALL p_cerrar_renglon(:r, :t, :c, @p_ok, @p_mensaje)'),
        {'r': id_renglon, 't': terapeuta.id, 'c': cierre},
    )
    ok, mensaje = db.session.execute(text('SELECT @p_ok, @p_mensaje')).first()
    db.session.commit()

    if not ok:
        raise _falla(mensaje, 'No se pudo cerrar el renglon.')
    db.session.expire_all()
    return SesionRenglon.query.get(id_renglon).to_dict(), mensaje


@reintentar_en_deadlock()
def borrar_renglon(id_renglon):
    terapeuta = terapeuta_actual()

    db.session.execute(
        text('CALL p_borrar_renglon(:r, :t, @p_ok, @p_mensaje)'),
        {'r': id_renglon, 't': terapeuta.id},
    )
    ok, mensaje = db.session.execute(text('SELECT @p_ok, @p_mensaje')).first()
    db.session.commit()

    if not ok:
        raise _falla(mensaje, 'No se pudo borrar el renglon.')
    return mensaje


@reintentar_en_deadlock()
def marcar_objetivo(id_sesion, datos):
    """Agrega o quita un objetivo del plan de la sesion (p_marcar_objetivo_sesion)."""
    terapeuta = terapeuta_actual()
    obtener_sesion(id_sesion)  # 404 limpio antes de llamar al procedimiento

    id_objetivo = datos.get('id_objetivo')
    if not isinstance(id_objetivo, int) or isinstance(id_objetivo, bool):
        raise ErrorAplicacion('Indique qué objetivo.', campo='id_objetivo')
    marcado = datos.get('marcado', True)
    if not isinstance(marcado, bool):
        raise ErrorAplicacion('El campo marcado tiene que ser verdadero o falso.', campo='marcado')

    db.session.execute(
        text('CALL p_marcar_objetivo_sesion(:s, :t, :o, :m, @p_ok, @p_mensaje)'),
        {'s': id_sesion, 't': terapeuta.id, 'o': id_objetivo, 'm': marcado},
    )
    ok, mensaje = db.session.execute(text('SELECT @p_ok, @p_mensaje')).first()
    db.session.commit()

    if not ok:
        raise _falla(mensaje, 'No se pudo actualizar el plan.')
    return mensaje

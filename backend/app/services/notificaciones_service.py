# backend/app/services/notificaciones_service.py
# Avisos del tratamiento para la familia (Entrega 4).
#
# EMISION: la hace p_notificar_paciente, en una transaccion aparte y DESPUES
# de confirmar el cambio avisado. Es "mejor esfuerzo": si el aviso falla se
# registra en el log y el cambio original queda como estaba. Un aviso
# perdido es un problema menor; una sesion que no se puede registrar porque
# fallo un aviso no lo es.
#
# CONSULTA: solo rol familiar, y solo sus propios avisos.

import datetime as dt
import logging

from flask import g
from sqlalchemy import text

from app import db
from app.models import Familiar, Notificacion, Paciente, PreferenciaNotificacion
from app.models.notificacion import TIPOS
from app.utils.errors import ErrorAplicacion

logger = logging.getLogger(__name__)

ETIQUETAS_TIPO = {
    'nueva_sesion': 'Nueva sesión registrada',
    'informe_generado': 'Informe generado',
    'cambio_objetivo': 'Cambios en los objetivos',
}
DESCRIPCIONES_TIPO = {
    'nueva_sesion': 'Un aviso cada vez que el equipo terapéutico registra una sesión realizada.',
    'informe_generado': 'Un aviso cuando hay un informe nuevo del paciente.',
    'cambio_objetivo': 'Un aviso cuando se agrega, modifica o archiva un objetivo.',
}
MAXIMO_DESCRIPCION = 300


# ---------------------------------------------------------------------------
# Emision
# ---------------------------------------------------------------------------
def _fecha(valor):
    if isinstance(valor, str):
        valor = dt.date.fromisoformat(valor)
    return valor.strftime('%d/%m/%Y')


def _recortar(texto):
    texto = (texto or '').strip()
    if len(texto) <= MAXIMO_DESCRIPCION:
        return texto
    return texto[:MAXIMO_DESCRIPCION - 1].rstrip() + '…'


def emitir(id_paciente, tipo, texto):
    """
    Envia el aviso a los familiares vinculados. Nunca lanza: devuelve la
    cantidad de avisos creados (0 si no se pudo o no correspondia).
    """
    try:
        db.session.execute(
            text('CALL p_notificar_paciente(:pac, :tipo, :texto, @p_env, @p_msg)'),
            {'pac': id_paciente, 'tipo': tipo, 'texto': texto[:500]},
        )
        enviadas, mensaje = db.session.execute(text('SELECT @p_env, @p_msg')).first()
        db.session.commit()
        if mensaje != 'Aviso enviado':
            logger.warning('Aviso %s no enviado (paciente %s): %s', tipo, id_paciente, mensaje)
        return int(enviadas or 0)
    except Exception:  # noqa: BLE001 - el aviso no puede romper el flujo clinico
        db.session.rollback()
        logger.exception('Fallo al emitir el aviso %s del paciente %s', tipo, id_paciente)
        return 0


def _nombre(id_paciente):
    paciente = db.session.get(Paciente, id_paciente)
    return paciente.nombre if paciente else 'el paciente'


def avisar_sesion(sesion):
    """Aviso de sesion cargada. Solo sesiones ya ocurridas (fecha <= hoy)."""
    fecha = sesion.fecha
    if fecha > dt.date.today():
        return 0
    nombre = _nombre(sesion.id_paciente)
    if sesion.estado == 'ausencia':
        texto = f'Se registró una ausencia en la sesión del {_fecha(fecha)} de {nombre}.'
    else:
        texto = f'Se registró la sesión del {_fecha(fecha)} de {nombre}.'
    return emitir(sesion.id_paciente, 'nueva_sesion', texto)


def avisar_objetivo(objetivo, accion):
    """accion: 'agregado' | 'modificado' | 'archivado'."""
    nombre = _nombre(objetivo.id_paciente)
    frases = {
        'agregado': f'Se agregó un objetivo al plan de {nombre}',
        'modificado': f'Se modificó un objetivo del plan de {nombre}',
        'archivado': f'Se archivó un objetivo del plan de {nombre}',
    }
    texto = f'{frases[accion]}: {_recortar(objetivo.descripcion)}'
    return emitir(objetivo.id_paciente, 'cambio_objetivo', texto)


def avisar_informe(id_paciente):
    """Gancho para la Entrega 6 (informes): lo llama quien genera el informe."""
    texto = f'Ya está disponible un informe nuevo de {_nombre(id_paciente)}.'
    return emitir(id_paciente, 'informe_generado', texto)


# ---------------------------------------------------------------------------
# Consulta del familiar
# ---------------------------------------------------------------------------
def _familiar_actual():
    familiar = Familiar.query.filter_by(id_usuario=g.usuario_actual.id).first()
    if familiar is None:
        raise ErrorAplicacion(
            'Su cuenta no tiene un perfil de familiar asociado. Comuníquese con el centro.',
            http_status=409,
        )
    return familiar


def _serializar(n, nombres):
    return {
        'id': n.id,
        'id_paciente': n.id_paciente,
        'paciente': nombres.get(n.id_paciente),
        'tipo': n.tipo,
        'tipo_etiqueta': ETIQUETAS_TIPO.get(n.tipo, n.tipo),
        'mensaje': n.mensaje,
        'leida': bool(n.leida),
        'fecha': n.fecha.isoformat(),
    }


def contar_no_leidas():
    familiar = _familiar_actual()
    cantidad = Notificacion.query.filter_by(id_familiar=familiar.id, leida=False).count()
    return {'no_leidas': cantidad}


def listar(tipo=None, leida=None, id_paciente=None, limite=50, desplazamiento=0):
    familiar = _familiar_actual()
    if tipo and tipo not in TIPOS:
        raise ErrorAplicacion('El tipo de aviso indicado no es válido.', campo='tipo')
    try:
        limite = max(1, min(int(limite), 100))
        desplazamiento = max(0, int(desplazamiento))
    except (TypeError, ValueError):
        raise ErrorAplicacion('La paginación indicada no es válida.')

    consulta = Notificacion.query.filter_by(id_familiar=familiar.id)
    if tipo:
        consulta = consulta.filter_by(tipo=tipo)
    if leida in ('0', '1', 0, 1, True, False, 'true', 'false'):
        consulta = consulta.filter_by(leida=leida in ('1', 1, True, 'true'))
    if id_paciente:
        consulta = consulta.filter_by(id_paciente=int(id_paciente))

    total = consulta.count()
    filas = (
        consulta.order_by(Notificacion.fecha.desc(), Notificacion.id.desc())
        .limit(limite).offset(desplazamiento).all()
    )
    ids = {n.id_paciente for n in filas}
    nombres = {
        p.id: p.nombre_completo
        for p in Paciente.query.filter(Paciente.id.in_(ids)).all()
    } if ids else {}
    return {
        'notificaciones': [_serializar(n, nombres) for n in filas],
        'total': total,
        'no_leidas': contar_no_leidas()['no_leidas'],
    }


def marcar(id_notificacion, leida=True):
    familiar = _familiar_actual()
    n = Notificacion.query.filter_by(id=id_notificacion, id_familiar=familiar.id).first()
    if n is None:
        raise ErrorAplicacion('El aviso indicado no existe.', http_status=404)
    n.leida = bool(leida)
    db.session.commit()
    return _serializar(n, {n.id_paciente: _nombre_completo(n.id_paciente)})


def _nombre_completo(id_paciente):
    paciente = db.session.get(Paciente, id_paciente)
    return paciente.nombre_completo if paciente else None


def marcar_todas():
    familiar = _familiar_actual()
    cantidad = (
        Notificacion.query.filter_by(id_familiar=familiar.id, leida=False)
        .update({'leida': True})
    )
    db.session.commit()
    return cantidad


def listar_preferencias():
    familiar = _familiar_actual()
    guardadas = {
        p.tipo: bool(p.habilitada)
        for p in PreferenciaNotificacion.query.filter_by(id_familiar=familiar.id).all()
    }
    return {
        'preferencias': [
            {
                'tipo': tipo,
                'etiqueta': ETIQUETAS_TIPO[tipo],
                'descripcion': DESCRIPCIONES_TIPO[tipo],
                # sin fila = habilitado
                'habilitada': guardadas.get(tipo, True),
            }
            for tipo in TIPOS
        ]
    }


def guardar_preferencia(tipo, habilitada):
    familiar = _familiar_actual()
    if tipo not in TIPOS:
        raise ErrorAplicacion('El tipo de aviso indicado no existe.', http_status=404)
    if not isinstance(habilitada, bool):
        raise ErrorAplicacion('Indique si el aviso queda habilitado o no.', campo='habilitada')
    fila = PreferenciaNotificacion.query.filter_by(id_familiar=familiar.id, tipo=tipo).first()
    if fila is None:
        fila = PreferenciaNotificacion(id_familiar=familiar.id, tipo=tipo, habilitada=habilitada)
        db.session.add(fila)
    else:
        fila.habilitada = habilitada
    db.session.commit()
    return listar_preferencias()

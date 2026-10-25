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
from app.models.sesion import formatear_hora
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


def _texto_sesion(sesion):
    # La hora va en el texto porque el texto es lo que identifica la sesion
    # al deduplicar (avisar_sesion_cerrada): con solo la fecha, dos sesiones
    # del mismo paciente el mismo dia generaban un unico aviso.
    fecha = _fecha(sesion.fecha)
    hora = (formatear_hora(sesion.hora_inicio) or '')[:5] or None
    cuando = f'{fecha} a las {hora}' if hora else fecha
    nombre = _nombre(sesion.id_paciente)
    if sesion.estado == 'ausencia':
        return f'Se registró una ausencia en la sesión del {cuando} de {nombre}.'
    if sesion.estado == 'cortada':
        return f'Se registró la sesión del {cuando} de {nombre}; se cortó antes de lo previsto.'
    return f'Se registró la sesión del {cuando} de {nombre}.'


def avisar_sesion(sesion):
    """
    Aviso de sesion cargada. Solo sesiones ya ocurridas (fecha <= hoy) y con
    el registro cerrado: una sesion 'incompleta' todavia no se informa, el
    aviso sale cuando pasa a realizada o a ausencia.
    """
    if sesion.estado not in ('completa', 'cortada', 'ausencia'):
        return 0
    return avisar_sesion_cerrada(sesion)


def avisar_sesion_cerrada(sesion):
    """
    Aviso al cerrar el registro del dia (la sesion pasa a realizada o a
    ausencia). Las sesiones salen de la agenda recurrente ya creadas y sin
    aviso, asi que este es el momento en que la familia se entera.

    Una sola vez por sesion: reabrir y volver a cerrar el registro no repite
    el aviso (el texto lleva la fecha, que identifica a la sesion del
    paciente).
    """
    if sesion.fecha > dt.date.today():
        return 0
    texto = _texto_sesion(sesion)[:500]
    ya_avisado = Notificacion.query.filter_by(
        id_paciente=sesion.id_paciente, tipo='nueva_sesion', mensaje=texto,
    ).first()
    db.session.rollback()  # cierra la transaccion de lectura
    if ya_avisado is not None:
        return 0
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


def _ids_vinculados(id_familiar):
    # Import local: portal_familiar_service importa este modulo.
    from app.services.portal_familiar_service import ids_de_pacientes_vinculados
    return ids_de_pacientes_vinculados(id_familiar)


def _avisos_visibles(familiar):
    """
    Avisos del familiar sobre pacientes que HOY tiene vinculados. Al quitar el
    acceso a un paciente, sus avisos viejos dejan de mostrarse: traen nombre,
    fechas y horarios del paciente.
    """
    vinculados = _ids_vinculados(familiar.id)
    return Notificacion.query.filter(
        Notificacion.id_familiar == familiar.id,
        Notificacion.id_paciente.in_(vinculados or {0}),
    )


def contar_no_leidas():
    familiar = _familiar_actual()
    cantidad = _avisos_visibles(familiar).filter(Notificacion.leida.is_(False)).count()
    return {'no_leidas': cantidad}


_LEIDA_SI = ('1', 'true')
_LEIDA_NO = ('0', 'false')


def listar(tipo=None, leida=None, id_paciente=None, limite=50, desplazamiento=0):
    familiar = _familiar_actual()
    if tipo and tipo not in TIPOS:
        raise ErrorAplicacion('El tipo de aviso indicado no es válido.', campo='tipo')
    try:
        limite = int(limite)
        desplazamiento = int(desplazamiento)
    except (TypeError, ValueError):
        raise ErrorAplicacion('La paginación indicada no es válida.')
    if not 1 <= limite <= 100:
        raise ErrorAplicacion('El límite tiene que estar entre 1 y 100.', campo='limite')
    if desplazamiento < 0:
        raise ErrorAplicacion('El desplazamiento no puede ser negativo.', campo='desplazamiento')
    if leida is not None and str(leida).strip().lower() not in _LEIDA_SI + _LEIDA_NO + ('',):
        raise ErrorAplicacion('El filtro "leida" tiene que ser 1 (leídos) o 0 (sin leer).', campo='leida')
    if id_paciente:
        try:
            id_paciente = int(id_paciente)
        except (TypeError, ValueError):
            raise ErrorAplicacion('El paciente indicado no es válido.', campo='id_paciente')
        if id_paciente not in _ids_vinculados(familiar.id):
            raise ErrorAplicacion(
                'El paciente indicado no está vinculado a su cuenta.', http_status=403,
            )

    consulta = _avisos_visibles(familiar)
    if tipo:
        consulta = consulta.filter_by(tipo=tipo)
    if leida is not None and str(leida).strip().lower() in _LEIDA_SI + _LEIDA_NO:
        consulta = consulta.filter_by(leida=str(leida).strip().lower() in _LEIDA_SI)
    if id_paciente:
        consulta = consulta.filter_by(id_paciente=id_paciente)

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
    n = _avisos_visibles(familiar).filter(Notificacion.id == id_notificacion).first()
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

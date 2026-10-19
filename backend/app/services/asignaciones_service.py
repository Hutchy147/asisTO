# backend/app/services/asignaciones_service.py
# Asignacion paciente-terapeuta (HDU 11). Las reglas las aplica la base;
# aca se traduce. Quien puede abrir o cerrar: solo el rol administrador (un
# terapeuta no decide quien atiende a quien). Queda registrado con las fechas
# de cada asignacion.

import datetime as dt
import logging

from sqlalchemy import text

from app import db
from app.models import Asignacion, Paciente, Terapeuta, Usuario
from app.services.pacientes_service import obtener_paciente
from app.utils.db import reintentar_en_deadlock
from app.utils.errors import ErrorAplicacion

logger = logging.getLogger(__name__)


def _parsear_fecha_opcional(valor, campo, etiqueta):
    if valor is None or valor == '':
        return None
    try:
        return dt.date.fromisoformat(str(valor).strip())
    except ValueError:
        raise ErrorAplicacion(
            f'La fecha "{etiqueta}" tiene que estar en formato AAAA-MM-DD.',
            campo=campo,
        )


def _entero(valor, campo, etiqueta):
    try:
        numero = int(valor)
    except (TypeError, ValueError):
        raise ErrorAplicacion(f'Falta indicar {etiqueta}.', campo=campo)
    if numero <= 0:
        raise ErrorAplicacion(f'Falta indicar {etiqueta}.', campo=campo)
    return numero


def listar_terapeutas():
    """Terapeutas con usuario activo, para el selector de la asignacion."""
    filas = (
        db.session.query(Terapeuta, Usuario)
        .join(Usuario, Usuario.id == Terapeuta.id_usuario)
        .filter(Usuario.activo.is_(True))
        .order_by(Usuario.apellido, Usuario.nombre)
        .all()
    )
    return [
        {
            'id': terapeuta.id,
            'nombre_completo': f'{usuario.nombre} {usuario.apellido}',
            'especialidad': terapeuta.especialidad,
        }
        for terapeuta, usuario in filas
    ]


def _nombres(ids):
    if not ids:
        return {}
    filas = (
        db.session.query(Terapeuta.id, Usuario.nombre, Usuario.apellido)
        .join(Usuario, Usuario.id == Terapeuta.id_usuario)
        .filter(Terapeuta.id.in_(list(ids)))
        .all()
    )
    return {f[0]: f'{f[1]} {f[2]}' for f in filas}


def _serializar(asignaciones):
    nombres = _nombres({a.id_terapeuta for a in asignaciones})
    resultado = []
    for asignacion in asignaciones:
        datos = asignacion.to_dict()
        datos['terapeuta'] = nombres.get(asignacion.id_terapeuta)
        resultado.append(datos)
    return resultado


def listar_de_paciente(id_paciente):
    """
    Historial de asignaciones del paciente (vigentes primero, despues las
    cerradas de la mas reciente a la mas vieja). Incluye pacientes de baja:
    la lectura queda abierta.
    """
    paciente = obtener_paciente(id_paciente, incluir_inactivos=True)
    asignaciones = (
        Asignacion.query
        .filter_by(id_paciente=paciente.id)
        .order_by(
            Asignacion.fecha_hasta.isnot(None),
            Asignacion.fecha_desde.desc(),
            Asignacion.id.desc(),
        )
        .all()
    )
    datos = _serializar(asignaciones)
    return {
        'id_paciente': paciente.id,
        'asignaciones': datos,
        'vigentes': sum(1 for a in datos if a['vigente']),
    }


@reintentar_en_deadlock()
def abrir_asignacion(id_paciente, datos):
    """Abre una asignacion via p_abrir_asignacion. Devuelve (dict, mensaje)."""
    id_terapeuta = _entero(datos.get('id_terapeuta'), 'id_terapeuta', 'el terapeuta')
    fecha_desde = _parsear_fecha_opcional(
        datos.get('fecha_desde'), 'fecha_desde', 'desde'
    )

    db.session.execute(
        text(
            'CALL p_abrir_asignacion(:id_paciente, :id_terapeuta, :fecha_desde, '
            '@p_id, @p_mensaje)'
        ),
        {
            'id_paciente': id_paciente,
            'id_terapeuta': id_terapeuta,
            'fecha_desde': fecha_desde,
        },
    )
    id_asignacion, mensaje = db.session.execute(
        text('SELECT @p_id, @p_mensaje')
    ).first()
    db.session.commit()

    if id_asignacion is None:
        raise ErrorAplicacion(mensaje or 'No se pudo abrir la asignacion.')

    asignacion = Asignacion.query.get(id_asignacion)
    logger.info(
        'Asignacion %s abierta: paciente %s, terapeuta %s',
        id_asignacion, id_paciente, id_terapeuta,
    )
    return _serializar([asignacion])[0], mensaje


@reintentar_en_deadlock()
def cerrar_asignacion(id_asignacion, datos):
    """Cierra una asignacion via p_cerrar_asignacion. Devuelve (dict, mensaje)."""
    fecha_hasta = _parsear_fecha_opcional(
        datos.get('fecha_hasta'), 'fecha_hasta', 'hasta'
    )

    db.session.execute(
        text('CALL p_cerrar_asignacion(:id, :hasta, @p_cerrada, @p_mensaje)'),
        {'id': id_asignacion, 'hasta': fecha_hasta},
    )
    cerrada, mensaje = db.session.execute(
        text('SELECT @p_cerrada, @p_mensaje')
    ).first()
    db.session.commit()

    if not cerrada:
        # 404 si no existe, 409 si ya estaba cerrada (el estado no admite el
        # cambio), 400 para el resto (por ejemplo, una fecha de cierre
        # anterior al inicio: la rechaza el trigger).
        texto = (mensaje or '').lower()
        if 'no existe' in texto:
            estado_http = 404
        elif 'ya estaba cerrada' in texto:
            estado_http = 409
        else:
            estado_http = 400
        raise ErrorAplicacion(
            mensaje or 'No se pudo cerrar la asignacion.', http_status=estado_http
        )

    db.session.expire_all()
    asignacion = Asignacion.query.get(id_asignacion)
    logger.info('Asignacion %s cerrada', id_asignacion)
    return _serializar([asignacion])[0], mensaje


def ids_de_pacientes_asignados(id_terapeuta):
    """{id_paciente} con asignacion vigente del terapeuta."""
    filas = (
        db.session.query(Asignacion.id_paciente)
        .filter(
            Asignacion.id_terapeuta == id_terapeuta,
            Asignacion.fecha_hasta.is_(None),
        )
        .all()
    )
    return {f[0] for f in filas}


def responsables_vigentes():
    """{id_paciente: [nombre terapeuta, ...]} de las asignaciones vigentes."""
    asignaciones = Asignacion.query.filter(Asignacion.fecha_hasta.is_(None)).all()
    nombres = _nombres({a.id_terapeuta for a in asignaciones})
    resultado = {}
    for a in asignaciones:
        resultado.setdefault(a.id_paciente, []).append(nombres.get(a.id_terapeuta))
    return resultado


def listar_pacientes_admin():
    """
    Pacientes para la pantalla del administrador: identidad, estado y
    asignaciones vigentes. Usa to_dict (sin diagnostico): el administrador no
    ve contenido clinico.
    """
    pacientes = Paciente.query.order_by(Paciente.apellido, Paciente.nombre).all()
    vigentes = Asignacion.query.filter(Asignacion.fecha_hasta.is_(None)).all()
    nombres = _nombres({a.id_terapeuta for a in vigentes})
    por_paciente = {}
    for a in vigentes:
        por_paciente.setdefault(a.id_paciente, []).append({
            'id': a.id,
            'id_terapeuta': a.id_terapeuta,
            'terapeuta': nombres.get(a.id_terapeuta),
            'fecha_desde': a.fecha_desde.isoformat() if a.fecha_desde else None,
        })
    resultado = []
    for paciente in pacientes:
        datos = paciente.to_dict()
        datos['asignaciones_vigentes'] = por_paciente.get(paciente.id, [])
        resultado.append(datos)
    return resultado

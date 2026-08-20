# backend/app/services/sesiones_service.py
# Logica de sesiones. Las reglas las aplica la base; aca se traduce.

import datetime as dt
import logging

from flask import g
from sqlalchemy import bindparam, text

from app import db
from app.models import Evolucion, ObjetivoTerapeutico, Paciente, Sesion, Terapeuta, Usuario
from app.models.sesion import ESTADOS, ESTADOS_CON_EVOLUCION
from app.utils.db import reintentar_en_deadlock
from app.utils.errors import ErrorAplicacion

logger = logging.getLogger(__name__)

# Tope del rango de GET /api/sesiones. Un rango sin limite permite pedir
# "desde 1900 hasta 2100" y traerse la agenda entera en una sola respuesta.
MAXIMO_DIAS_RANGO = 366

# Ventana por defecto cuando no se indican fechas: la semana en curso
# hacia adelante. Es lo que necesita un calendario al abrirse.
DIAS_POR_DEFECTO = 7


def terapeuta_actual():
    """Perfil de terapeuta del usuario logueado."""
    terapeuta = Terapeuta.query.filter_by(id_usuario=g.usuario_actual.id).first()
    if terapeuta is None:
        # El rol es terapeuta pero no tiene fila en terapeutas: dato
        # incompleto, no un problema de permisos del usuario
        raise ErrorAplicacion(
            'Tu usuario no tiene un perfil de terapeuta asociado. '
            'Avisale al equipo.',
            http_status=409,
        )
    return terapeuta


def _parsear_fecha(valor, etiqueta):
    if not valor:
        return None
    try:
        return dt.date.fromisoformat(valor.strip())
    except (ValueError, AttributeError):
        raise ErrorAplicacion(
            f'La fecha "{etiqueta}" tiene que estar en formato AAAA-MM-DD.'
        )


def resolver_rango(desde, hasta):
    """
    Valida el rango pedido. Devuelve (desde, hasta) como date.

    Se rechaza el rango invertido y el excesivamente amplio. Los dos son
    errores del llamador, no estados vacios: devolver una lista vacia ante
    un rango invertido esconde el error en vez de mostrarlo.
    """
    fecha_desde = _parsear_fecha(desde, 'desde')
    fecha_hasta = _parsear_fecha(hasta, 'hasta')

    if fecha_desde is None and fecha_hasta is None:
        hoy = dt.date.today()
        return hoy, hoy + dt.timedelta(days=DIAS_POR_DEFECTO)

    if fecha_desde is None:
        fecha_desde = fecha_hasta - dt.timedelta(days=DIAS_POR_DEFECTO)
    if fecha_hasta is None:
        fecha_hasta = fecha_desde + dt.timedelta(days=DIAS_POR_DEFECTO)

    if fecha_desde > fecha_hasta:
        raise ErrorAplicacion(
            'El rango de fechas esta invertido: "desde" es posterior a "hasta".'
        )

    dias = (fecha_hasta - fecha_desde).days + 1
    if dias > MAXIMO_DIAS_RANGO:
        raise ErrorAplicacion(
            f'El rango pedido es de {dias} dias y el maximo es '
            f'{MAXIMO_DIAS_RANGO}. Acotá las fechas.'
        )

    return fecha_desde, fecha_hasta


def _conteo_de_objetivos(ids_sesion):
    """
    Por sesion: cuantos objetivos se calificaron sobre cuantos habia.

    EL DENOMINADOR ES "objetivos activos AL MOMENTO DE LA SESION", no los
    activos hoy. Para un historial es lo unico que tiene sentido: una sesion
    de marzo donde se calificaron 3 de 3 no pasa a ser "3 de 1" porque desde
    entonces se archivaron dos objetivos. Con el denominador de hoy, el
    pasado cambiaria solo.

    Se reconstruye con fecha_creacion y fecha_archivado, que ya estan en la
    tabla: un objetivo estaba activo en T si se creo antes de T y todavia no
    estaba archivado en T.

    LIMITACION CONOCIDA: si un objetivo se archivo, se reactivo y se volvio
    a archivar, solo sobrevive la ultima fecha_archivado, asi que el conteo
    de las sesiones del primer tramo puede quedar corto. Es un caso raro y
    la alternativa —una tabla de historial de estados— no se justifica para
    esta entrega.

    Una sola consulta para todas las sesiones, no una por sesion.
    """
    if not ids_sesion:
        return {}

    filas = db.session.execute(
        text(
            'SELECT s.id, '
            '  (SELECT COUNT(*) FROM evoluciones e WHERE e.id_sesion = s.id) AS calificados, '
            '  (SELECT COUNT(*) FROM objetivos_terapeuticos o '
            '     WHERE o.id_paciente = s.id_paciente '
            '       AND o.fecha_creacion <= TIMESTAMP(s.fecha, s.hora_inicio) '
            '       AND (o.activo = TRUE '
            '            OR o.fecha_archivado > TIMESTAMP(s.fecha, s.hora_inicio))) AS total '
            'FROM sesiones s WHERE s.id IN :ids'
        ).bindparams(bindparam('ids', expanding=True)),
        {'ids': list(ids_sesion)},
    ).all()

    return {fila[0]: {'calificados': int(fila[1]), 'total': int(fila[2])} for fila in filas}


def _nombres_de_terapeutas(ids_terapeuta):
    """{id_terapeuta: nombre completo} en una sola consulta."""
    if not ids_terapeuta:
        return {}
    filas = (
        db.session.query(Terapeuta.id, Usuario.nombre, Usuario.apellido)
        .join(Usuario, Usuario.id == Terapeuta.id_usuario)
        .filter(Terapeuta.id.in_(list(ids_terapeuta)))
        .all()
    )
    return {fila[0]: f'{fila[1]} {fila[2]}' for fila in filas}


def _serializar_lista(sesiones):
    """Sesiones + paciente + terapeuta + avance de calificacion.

    Todo lo agregado se resuelve con tres consultas fijas, no con una por
    sesion.
    """
    ids = [s.id for s in sesiones]
    conteos = _conteo_de_objetivos(ids)
    nombres = _nombres_de_terapeutas({s.id_terapeuta for s in sesiones})

    resultado = []
    for sesion in sesiones:
        conteo = conteos.get(sesion.id, {'calificados': 0, 'total': 0})
        datos = sesion.to_dict()
        datos['tiene_evolucion'] = conteo['calificados'] > 0
        datos['admite_evolucion'] = sesion.estado in ESTADOS_CON_EVOLUCION
        # "3 de 4" — el dato mas repetido de la interfaz. En una ausencia no
        # corresponde calificar nada, asi que se informa igual pero la
        # pantalla lo muestra como "—".
        datos['objetivos'] = conteo
        datos['paciente'] = {
            'id': sesion.paciente.id,
            'nombre': sesion.paciente.nombre,
            'apellido': sesion.paciente.apellido,
            'nombre_completo': sesion.paciente.nombre_completo,
            'nro_historia': sesion.paciente.nro_historia,
        }
        datos['terapeuta'] = {
            'id': sesion.id_terapeuta,
            'nombre_completo': nombres.get(sesion.id_terapeuta),
        }
        resultado.append(datos)
    return resultado


def listar_por_rango(desde, hasta):
    """Sesiones del terapeuta logueado en el rango."""
    terapeuta = terapeuta_actual()
    fecha_desde, fecha_hasta = resolver_rango(desde, hasta)

    sesiones = (
        Sesion.query
        .filter(
            Sesion.id_terapeuta == terapeuta.id,
            Sesion.fecha >= fecha_desde,
            Sesion.fecha <= fecha_hasta,
        )
        .order_by(Sesion.fecha, Sesion.hora_inicio)
        .all()
    )

    return {
        'desde': fecha_desde.isoformat(),
        'hasta': fecha_hasta.isoformat(),
        'sesiones': _serializar_lista(sesiones),
        'total': len(sesiones),
    }


def listar_de_hoy():
    terapeuta = terapeuta_actual()
    hoy = dt.date.today()

    sesiones = (
        Sesion.query
        .filter(Sesion.id_terapeuta == terapeuta.id, Sesion.fecha == hoy)
        .order_by(Sesion.hora_inicio)
        .all()
    )

    return {
        'fecha': hoy.isoformat(),
        'sesiones': _serializar_lista(sesiones),
        'total': len(sesiones),
    }


def listar_pendientes_de_evolucion():
    """
    Sesiones ya ocurridas, en completa o incompleta, sin ninguna evolucion.

    "Ya ocurridas" incluye las de hoy cuyo horario de inicio ya paso: una
    sesion de las 9 de la manana esta pendiente a las 11, no recien manana.
    Las de estado 'ausencia' quedan afuera: no es que les falte evolucion,
    es que no pueden tenerla (regla 2).
    """
    terapeuta = terapeuta_actual()
    ahora = dt.datetime.now()
    hoy = ahora.date()
    hora_actual = ahora.time()

    sesiones = (
        Sesion.query
        .filter(
            Sesion.id_terapeuta == terapeuta.id,
            Sesion.estado.in_(ESTADOS_CON_EVOLUCION),
            db.or_(
                Sesion.fecha < hoy,
                db.and_(Sesion.fecha == hoy, Sesion.hora_inicio <= hora_actual),
            ),
            ~Sesion.id.in_(db.session.query(Evolucion.id_sesion).distinct()),
        )
        .order_by(Sesion.fecha.desc(), Sesion.hora_inicio.desc())
        .all()
    )

    return {
        'sesiones': _serializar_lista(sesiones),
        'total': len(sesiones),
    }


def listar_por_paciente(id_paciente):
    """
    Historial completo de sesiones de un paciente, de la mas reciente a la
    mas vieja.

    Devuelve las de TODOS los terapeutas, no solo las del logueado. Es
    coherente con la decision de autoria que ya rige el modulo: la lectura
    es abierta a cualquier terapeuta y lo restringido es cargar evolucion.
    Filtrar por terapeuta aca mostraria media historia clinica, que es peor
    que mostrarla entera.
    """
    # Valida que exista, con el 404 correspondiente. Los dados de baja SI se
    # incluyen: el historial de sesiones es justamente lo que hay que poder
    # consultar despues de la baja. Registrar una sesion nueva sigue
    # rechazandolos por otro camino.
    from app.services.pacientes_service import obtener_paciente

    paciente = obtener_paciente(id_paciente, incluir_inactivos=True)

    sesiones = (
        Sesion.query
        .filter(Sesion.id_paciente == paciente.id)
        .order_by(Sesion.fecha.desc(), Sesion.hora_inicio.desc())
        .all()
    )

    return {
        'paciente': paciente.to_dict_clinico(),
        'sesiones': _serializar_lista(sesiones),
        'total': len(sesiones),
    }


def obtener_sesion(id_sesion):
    sesion = Sesion.query.get(id_sesion)
    if sesion is None:
        raise ErrorAplicacion('La sesion indicada no existe.', http_status=404)
    return sesion


def obtener_detalle(id_sesion):
    """
    Detalle de la sesion con su evolucion y los objetivos activos del
    paciente (que es contra lo que se puede calificar).

    LECTURA ABIERTA A CUALQUIER TERAPEUTA. En esta entrega todos los
    terapeutas ven todos los pacientes, y la continuidad del tratamiento
    exige poder leer que hizo el colega que atendio antes. La ESCRITURA de
    evolucion si esta restringida — ver evoluciones_service.

    Hasta el 2026-08-07 esta nota daba como segundo motivo que el schema
    contemplaba "duplas terapeuticas (dos terapeutas sobre el mismo
    paciente)". Era falso: eso es trabajo interdisciplinario y quedo fuera
    del alcance. Una dupla es UNA terapeuta con DOS ninios, y no toca la
    lectura del detalle de sesion. El primer motivo se sostiene solo.
    """
    sesion = obtener_sesion(id_sesion)

    evoluciones = (
        Evolucion.query
        .filter_by(id_sesion=sesion.id)
        .order_by(Evolucion.id)
        .all()
    )

    objetivos = (
        ObjetivoTerapeutico.query
        .filter_by(id_paciente=sesion.id_paciente, activo=True)
        .order_by(ObjetivoTerapeutico.fecha_creacion, ObjetivoTerapeutico.id)
        .all()
    )

    usuario_terapeuta = (
        db.session.query(Usuario)
        .join(Terapeuta, Terapeuta.id_usuario == Usuario.id)
        .filter(Terapeuta.id == sesion.id_terapeuta)
        .first()
    )

    conteo = _conteo_de_objetivos([sesion.id]).get(
        sesion.id, {'calificados': 0, 'total': 0}
    )

    datos = sesion.to_dict()
    datos['tiene_evolucion'] = len(evoluciones) > 0
    datos['admite_evolucion'] = sesion.estado in ESTADOS_CON_EVOLUCION
    datos['es_propia'] = sesion.id_terapeuta == terapeuta_actual().id
    datos['objetivos'] = conteo

    # La descripcion del objetivo viaja PEGADA a cada evolucion, y no se
    # deduce cruzando contra `objetivos_activos`. El motivo es que ese cruce
    # falla justo donde importa: un objetivo calificado en marzo puede estar
    # archivado hoy, y entonces NO esta en esa lista. La vista de lectura
    # mostraria una calificacion sin poder decir de que objetivo es.
    #
    # Es el mismo criterio que ya aplica p_evolucion_paciente para armar las
    # series: de una sesion pasada se muestra lo que estaba vivo EN ESA
    # SESION, no lo que sigue activo hoy.
    objetivos_calificados = {}
    if evoluciones:
        objetivos_calificados = {
            o.id: o
            for o in ObjetivoTerapeutico.query.filter(
                ObjetivoTerapeutico.id.in_([e.id_objetivo for e in evoluciones])
            ).all()
        }

    evoluciones_datos = []
    for evolucion in evoluciones:
        item = evolucion.to_dict()
        objetivo = objetivos_calificados.get(evolucion.id_objetivo)
        # None solo si la fila del objetivo ya no existe. Hoy no puede pasar
        # —la FK lo impide y el borrado esta bloqueado— pero la vista tiene
        # que poder dibujar algo en vez de romper.
        item['objetivo'] = {
            'id': objetivo.id,
            'descripcion': objetivo.descripcion,
            'activo': bool(objetivo.activo),
        } if objetivo else None
        evoluciones_datos.append(item)

    return {
        'sesion': datos,
        'paciente': sesion.paciente.to_dict_clinico(),
        'terapeuta': {
            'id': sesion.id_terapeuta,
            'nombre_completo': usuario_terapeuta.nombre_completo if usuario_terapeuta else None,
        },
        'evoluciones': evoluciones_datos,
        # Contra que se puede calificar. Si viene vacio, el paciente no
        # tiene objetivos activos y no hay nada que evaluar todavia.
        'objetivos_activos': [o.to_dict() for o in objetivos],
    }


@reintentar_en_deadlock()
def registrar_sesion(datos):
    """
    Registra via p_registrar_sesion. No se duplica la validacion de
    superposicion: la hace el procedimiento y ademas el trigger.

    La sesion se registra SIEMPRE a nombre del terapeuta logueado. Un
    id_terapeuta que venga en el cuerpo se ignora: si no, cualquier
    terapeuta podria llenarle la agenda a otro.
    """
    terapeuta = terapeuta_actual()

    id_paciente = datos.get('id_paciente')
    fecha = (datos.get('fecha') or '').strip()
    hora_inicio = (datos.get('hora_inicio') or '').strip()
    hora_fin = (datos.get('hora_fin') or '').strip() or None
    estado = (datos.get('estado') or 'incompleta').strip()
    notas = datos.get('notas')

    faltantes = [
        etiqueta for etiqueta, valor in (
            ('id_paciente', id_paciente),
            ('fecha', fecha),
            ('hora_inicio', hora_inicio),
        ) if not valor
    ]
    if faltantes:
        raise ErrorAplicacion('Faltan datos obligatorios: ' + ', '.join(faltantes))

    if estado not in ESTADOS:
        raise ErrorAplicacion(
            'El estado tiene que ser uno de: ' + ', '.join(ESTADOS) + '.'
        )

    db.session.execute(
        text(
            'CALL p_registrar_sesion(:id_terapeuta, :id_paciente, :fecha, '
            ':hora_inicio, :hora_fin, :estado, :notas, @p_id_sesion, @p_mensaje)'
        ),
        {
            'id_terapeuta': terapeuta.id,
            'id_paciente': id_paciente,
            'fecha': fecha,
            'hora_inicio': hora_inicio,
            'hora_fin': hora_fin,
            'estado': estado,
            'notas': notas,
        },
    )

    id_creada, mensaje = db.session.execute(
        text('SELECT @p_id_sesion, @p_mensaje')
    ).first()

    db.session.commit()

    if id_creada is None:
        # p_mensaje ya explica por que: superposicion, hora invalida,
        # paciente inexistente. Se propaga tal cual.
        raise ErrorAplicacion(mensaje or 'No se pudo registrar la sesion.')

    sesion = Sesion.query.get(int(id_creada))
    logger.info('Sesion %s registrada por terapeuta %s', sesion.id, terapeuta.id)

    return sesion, mensaje

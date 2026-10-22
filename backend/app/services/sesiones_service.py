# backend/app/services/sesiones_service.py
# Logica de sesiones. Las reglas las aplica la base; aca se traduce.

import datetime as dt
import logging

from flask import g
from sqlalchemy import bindparam, text

from app import db
from app.models import Evolucion, ObjetivoTerapeutico, Paciente, Sesion, Terapeuta, Usuario
from app.models.sesion import ESTADO_AUSENCIA, ESTADOS, ESTADOS_CON_EVOLUCION, ORIGENES_AUSENCIA
from app.utils.db import reintentar_en_deadlock
from app.utils.errors import ErrorAplicacion
from app.utils.textos import acentuar

logger = logging.getLogger(__name__)

# Tope del rango de GET /api/sesiones. Un rango sin limite permite pedir
# "desde 1900 hasta 2100" y traerse la agenda entera en una sola respuesta.
MAXIMO_DIAS_RANGO = 366

# Ventana por defecto cuando no se indican fechas: la semana en curso
# hacia adelante. Es lo que necesita un calendario al abrirse.
DIAS_POR_DEFECTO = 7

# NORMA DE AGENDA (Entrega 3): sesiones de 45 minutos, de lunes a viernes.
#
# Son politica operativa del centro, no integridad de los datos, y por eso
# viven aca y no en la base: la base sigue admitiendo cualquier dia y
# cualquier duracion (hay sesiones viejas sin hora de fin que se leen como
# una hora, y la carga retroactiva no puede volverse imposible). Lo que se
# controla es AGENDAR: una sesion nueva, o mover una existente a otro dia.
# Una sesion ya guardada en fin de semana se sigue viendo y editando.
DURACION_POR_DEFECTO_MINUTOS = 45
DIAS_HABILES = 5  # lunes (0) a viernes (4)


def _validar_dia_habil(fecha_iso):
    try:
        dia = dt.date.fromisoformat(fecha_iso)
    except (TypeError, ValueError):
        raise ErrorAplicacion(
            'La fecha tiene que tener el formato AAAA-MM-DD.', campo='fecha'
        )
    if dia.weekday() >= DIAS_HABILES:
        raise ErrorAplicacion(
            'Las sesiones se agendan de lunes a viernes.', campo='fecha'
        )


def _hora_fin_por_defecto(hora_inicio):
    """hora_inicio + 45 minutos ('HH:MM' o 'HH:MM:SS'). None si no hay lugar en el dia."""
    try:
        partes = [int(x) for x in hora_inicio.split(':')]
        inicio = dt.timedelta(hours=partes[0], minutes=partes[1],
                              seconds=partes[2] if len(partes) > 2 else 0)
    except (ValueError, IndexError, AttributeError):
        raise ErrorAplicacion('La hora de inicio no es valida.', campo='hora_inicio')
    fin = inicio + dt.timedelta(minutes=DURACION_POR_DEFECTO_MINUTOS)
    if fin >= dt.timedelta(days=1):
        return None  # la base asumira su default; la sesion termina pasada la medianoche
    segundos = int(fin.total_seconds())
    return f'{segundos // 3600:02d}:{segundos % 3600 // 60:02d}:{segundos % 60:02d}'


def terapeuta_actual():
    """Perfil de terapeuta del usuario logueado."""
    terapeuta = Terapeuta.query.filter_by(id_usuario=g.usuario_actual.id).first()
    if terapeuta is None:
        # El rol es terapeuta pero no tiene fila en terapeutas: dato
        # incompleto, no un problema de permisos del usuario
        raise ErrorAplicacion(
            'Su usuario no tiene un perfil de terapeuta asociado. '
            'Avise al equipo.',
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
            f'{MAXIMO_DIAS_RANGO}. Acote las fechas.'
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


def _companeros_de_dupla(sesiones):
    """
    {id_sesion: datos del otro paciente de la dupla} para las sesiones que
    integran una. Una consulta para todas.

    Es el unico dato de la otra sesion que se expone en la lista: quien es
    el companero y cual es su sesion, para poder mostrarlo y abrirlo. Nada
    clinico del companero viaja aca.
    """
    ids_dupla = {s.id_dupla for s in sesiones if s.id_dupla}
    if not ids_dupla:
        return {}
    hermanas = Sesion.query.filter(Sesion.id_dupla.in_(list(ids_dupla))).all()
    por_dupla = {}
    for h in hermanas:
        por_dupla.setdefault(h.id_dupla, []).append(h)
    resultado = {}
    for sesion in sesiones:
        if not sesion.id_dupla:
            continue
        for otra in por_dupla.get(sesion.id_dupla, []):
            if otra.id != sesion.id:
                resultado[sesion.id] = {
                    'id_sesion': otra.id,
                    'id_paciente': otra.id_paciente,
                    'nombre_completo': otra.paciente.nombre_completo,
                }
                break
    return resultado


def _serializar_lista(sesiones):
    """Sesiones + paciente + terapeuta + avance de calificacion.

    Todo lo agregado se resuelve con cuatro consultas fijas, no con una por
    sesion.
    """
    ids = [s.id for s in sesiones]
    conteos = _conteo_de_objetivos(ids)
    nombres = _nombres_de_terapeutas({s.id_terapeuta for s in sesiones})
    companeros = _companeros_de_dupla(sesiones)

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
        # Dupla: None si la sesion es individual (o si la hermana no existe)
        datos['companero'] = companeros.get(sesion.id)
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


def _resumen_de_renglones(sesiones):
    """
    Por sesion: cuantos renglones de plan y de registro tiene, y cuantos
    renglones de plan PENDIENTES arrastra de sesiones anteriores del mismo
    paciente (mismo terapeuta). Dos consultas fijas, no una por sesion.
    """
    if not sesiones:
        return {}
    ids = [s.id for s in sesiones]
    resumen = {s.id: {'plan': 0, 'registro': 0, 'arrastre': 0} for s in sesiones}

    filas = db.session.execute(
        text(
            'SELECT id_sesion, momento, COUNT(*) FROM sesion_renglones '
            'WHERE id_sesion IN :ids GROUP BY id_sesion, momento'
        ).bindparams(bindparam('ids', expanding=True)),
        {'ids': ids},
    ).fetchall()
    for id_sesion, momento, cantidad in filas:
        resumen[id_sesion][momento] = int(cantidad)

    for sesion in sesiones:
        resumen[sesion.id]['arrastre'] = int(db.session.execute(
            text(
                'SELECT COUNT(*) FROM sesion_renglones r '
                'JOIN sesiones s2 ON s2.id = r.id_sesion '
                "WHERE r.momento = 'plan' AND r.cierre IS NULL "
                'AND s2.id_paciente = :p AND s2.id_terapeuta = :t AND s2.fecha < :f'
            ),
            {'p': sesion.id_paciente, 't': sesion.id_terapeuta, 'f': sesion.fecha},
        ).scalar() or 0)
    return resumen


def listar_de_hoy():
    terapeuta = terapeuta_actual()
    hoy = dt.date.today()

    sesiones = (
        Sesion.query
        .filter(Sesion.id_terapeuta == terapeuta.id, Sesion.fecha == hoy)
        .order_by(Sesion.hora_inicio)
        .all()
    )

    datos = _serializar_lista(sesiones)
    resumen = _resumen_de_renglones(sesiones)
    for item in datos:
        item['renglones'] = resumen.get(item['id'])

    return {
        'fecha': hoy.isoformat(),
        'sesiones': datos,
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


def _validar_estado(estado):
    """Una sola funcion para las dos rutas de escritura (crear y editar),
    para que la lista de estados validos no diverja entre las dos."""
    if estado not in ESTADOS:
        raise ErrorAplicacion(
            'El estado tiene que ser uno de: ' + ', '.join(ESTADOS) + '.'
        )


def _validar_ausencia_de(estado, ausencia_de):
    """Misma consistencia que trg_sesiones_solape_insert/_update, pero con
    mensaje de Python antes de gastar un viaje a la base. Compartida entre
    crear y editar, igual que _validar_estado: es la misma regla en las
    dos puertas y no puede divergir entre ellas.

    El trigger queda como la fuente de verdad (un CALL directo sin pasar
    por Flask tiene que dar el mismo veredicto); esto es una copia
    deliberada para dar el mensaje en castellano antes, no un reemplazo.
    """
    if estado == ESTADO_AUSENCIA:
        if ausencia_de not in ORIGENES_AUSENCIA:
            raise ErrorAplicacion(
                'Falta declarar quien falto: tiene que ser "paciente" o '
                '"terapeuta".'
            )
    elif ausencia_de:
        raise ErrorAplicacion(
            'Quien falto solo se declara en una sesion marcada como ausencia.'
        )


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
    datos['companero'] = _companeros_de_dupla([sesion]).get(sesion.id)

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
def registrar_sesion(datos, notificar=True):
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
    # SIN DEFAULT A PROPOSITO. Hasta el 2026-09-10 esto era
    # `datos.get('estado') or 'incompleta'`: un estado ausente se guardaba
    # como si alguien hubiera declarado "incompleta", sin que nadie lo haya
    # dicho. Es el mismo defecto que la interfaz (hallazgo A de
    # AUDITORIA.md) una capa mas abajo, y ese campo es justo el que RRHH
    # exporta y cuenta. Ausencia de estado pasa a ser lo que ya es ausencia
    # de fecha u hora_inicio: un dato obligatorio faltante.
    estado = (datos.get('estado') or '').strip()
    ausencia_de = (datos.get('ausencia_de') or '').strip() or None
    notas = datos.get('notas')

    faltantes = [
        etiqueta for etiqueta, valor in (
            ('id_paciente', id_paciente),
            ('fecha', fecha),
            ('hora_inicio', hora_inicio),
            ('estado', estado),
        ) if not valor
    ]
    if faltantes:
        raise ErrorAplicacion('Faltan datos obligatorios: ' + ', '.join(faltantes))

    _validar_estado(estado)
    _validar_ausencia_de(estado, ausencia_de)
    _validar_dia_habil(fecha)
    if hora_fin is None:
        hora_fin = _hora_fin_por_defecto(hora_inicio)

    db.session.execute(
        text(
            'CALL p_registrar_sesion(:id_terapeuta, :id_paciente, :fecha, '
            ':hora_inicio, :hora_fin, :estado, :ausencia_de, :notas, '
            '@p_id_sesion, @p_mensaje)'
        ),
        {
            'id_terapeuta': terapeuta.id,
            'id_paciente': id_paciente,
            'fecha': fecha,
            'hora_inicio': hora_inicio,
            'hora_fin': hora_fin,
            'estado': estado,
            'ausencia_de': ausencia_de,
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

    # Aviso a la familia (Entrega 4), ya confirmada la sesion. Mejor esfuerzo:
    # si falla, la sesion queda registrada igual. La agenda recurrente genera
    # turnos a futuro y pasa notificar=False: lo agendado no es una sesion
    # cargada.
    if notificar:
        from app.services.notificaciones_service import avisar_sesion
        avisar_sesion(sesion)

    return sesion, mensaje


@reintentar_en_deadlock()
def editar_sesion(id_sesion, datos):
    """
    Edita via p_editar_sesion. Editable: estado, ausencia_de, notas, fecha,
    hora_inicio, hora_fin. NO edita id_paciente ni id_terapeuta: el
    terapeuta lo fija el login, igual que en registrar_sesion, y el
    paciente es un hecho de la sesion, no un dato que se corrija aca.

    ESCRITURA RESTRINGIDA al terapeuta que atendio, mismo criterio que
    evoluciones_service.registrar_evolucion: la lectura de una sesion es
    abierta a cualquier terapeuta, pero solo quien atendio puede tocarla.
    El id_terapeuta viaja igual al procedimiento, que revalida la autoria
    por su cuenta (ver el comentario en p_editar_sesion, schema.sql): el
    403 de aca es la primera linea, no la unica.

    No se duplica la validacion de superposicion, de sesion posterior a la
    baja del paciente ni de ausencia con evoluciones cargadas: las aplica
    trg_sesiones_solape_update y su p_mensaje se propaga tal cual.
    """
    sesion = obtener_sesion(id_sesion)
    terapeuta = terapeuta_actual()

    if sesion.id_terapeuta != terapeuta.id:
        raise ErrorAplicacion(
            'Solo el terapeuta que atendio la sesion puede editarla.',
            http_status=403,
        )

    # Horario de partida, para avisar si la reprogramacion arrastra a la
    # hermana de dupla (la base mueve las dos juntas).
    horario_antes = (sesion.fecha, sesion.hora_inicio, sesion.hora_fin)
    id_dupla = sesion.id_dupla
    estado_antes = sesion.estado

    fecha = (datos.get('fecha') or '').strip()
    hora_inicio = (datos.get('hora_inicio') or '').strip()
    hora_fin = (datos.get('hora_fin') or '').strip() or None
    estado = (datos.get('estado') or '').strip()
    ausencia_de = (datos.get('ausencia_de') or '').strip() or None
    notas = datos.get('notas')

    faltantes = [
        etiqueta for etiqueta, valor in (
            ('estado', estado),
            ('fecha', fecha),
            ('hora_inicio', hora_inicio),
        ) if not valor
    ]
    if faltantes:
        raise ErrorAplicacion('Faltan datos obligatorios: ' + ', '.join(faltantes))

    _validar_estado(estado)
    _validar_ausencia_de(estado, ausencia_de)
    # Solo si la fecha CAMBIA: una sesion vieja de fin de semana sigue siendo
    # editable (estado, notas, hora) sin tener que moverla.
    if fecha != sesion.fecha.isoformat():
        _validar_dia_habil(fecha)

    db.session.execute(
        text(
            'CALL p_editar_sesion(:id_sesion, :id_terapeuta, :estado, '
            ':ausencia_de, :notas, :fecha, :hora_inicio, :hora_fin, '
            '@p_editado, @p_mensaje)'
        ),
        {
            'id_sesion': sesion.id,
            'id_terapeuta': terapeuta.id,
            'estado': estado,
            'ausencia_de': ausencia_de,
            'notas': notas,
            'fecha': fecha,
            'hora_inicio': hora_inicio,
            'hora_fin': hora_fin,
        },
    )

    editado, mensaje = db.session.execute(
        text('SELECT @p_editado, @p_mensaje')
    ).first()

    db.session.commit()

    if editado is None:
        # p_mensaje ya explica por que: superposicion, sesion posterior a la
        # baja del paciente, ausencia con evoluciones cargadas, sesion
        # inexistente. Se propaga tal cual.
        raise ErrorAplicacion(mensaje or 'No se pudo editar la sesion.')

    db.session.expire_all()
    sesion = Sesion.query.get(sesion.id)
    logger.info('Sesion %s editada por terapeuta %s', sesion.id, terapeuta.id)

    # Aviso a la familia (Entrega 4): al cerrar el registro del dia. Mejor
    # esfuerzo, una sola vez por sesion. Ver avisar_sesion_cerrada.
    if sesion.estado != estado_antes and sesion.estado in ('completa', 'ausencia'):
        from app.services.notificaciones_service import avisar_sesion_cerrada
        avisar_sesion_cerrada(sesion)

    mensaje = acentuar(mensaje)
    if id_dupla and horario_antes != (sesion.fecha, sesion.hora_inicio, sesion.hora_fin):
        companero = _companeros_de_dupla([sesion]).get(sesion.id)
        if companero:
            mensaje += (
                f' También se reprogramó la sesión de {companero["nombre_completo"]}, '
                'porque integran una dupla.'
            )

    return sesion, mensaje


# ---------------------------------------------------------------------------
# DUPLAS (Entrega 5)
#
# Una dupla es una terapeuta con dos pacientes en el mismo horario. Las
# reglas viven en la base (p_registrar_dupla, p_agregar_a_dupla y los
# triggers de solape de sesiones); aca se traduce el resultado. No hay ruta
# propia: la dupla se agenda desde el turno semanal en dupla
# (agenda_recurrente_service) y la lectura sale en el detalle de cada sesion.
# ---------------------------------------------------------------------------
def _estado_http_dupla(mensaje):
    texto = (mensaje or '').lower()
    if 'no existe' in texto:
        return 404
    if 'solo el terapeuta' in texto:
        return 403
    if 'ya integra' in texto or 'superponen' in texto:
        return 409
    return 400


@reintentar_en_deadlock()
def registrar_dupla(id_paciente_1, id_paciente_2, fecha, hora_inicio, hora_fin=None):
    """
    Agenda las dos sesiones de una dupla (p_registrar_dupla), a nombre de la
    terapeuta logueada y con estado 'incompleta' (agendadas, sin registro).
    Devuelve {id_dupla, id_sesion_1, id_sesion_2, mensaje}. Sin commit
    previo: la unidad es la dupla entera o nada.
    """
    terapeuta = terapeuta_actual()
    _validar_dia_habil(fecha)
    if hora_fin is None:
        hora_fin = _hora_fin_por_defecto(hora_inicio)

    db.session.execute(
        text(
            'CALL p_registrar_dupla(:t, :p1, :p2, :fecha, :inicio, :fin, '
            '@p_dupla, @p_s1, @p_s2, @p_mensaje)'
        ),
        {'t': terapeuta.id, 'p1': id_paciente_1, 'p2': id_paciente_2,
         'fecha': fecha, 'inicio': hora_inicio, 'fin': hora_fin},
    )
    dupla, s1, s2, mensaje = db.session.execute(
        text('SELECT @p_dupla, @p_s1, @p_s2, @p_mensaje')
    ).first()
    db.session.commit()

    if dupla is None:
        mensaje = acentuar(mensaje) or 'No se pudo registrar la dupla.'
        raise ErrorAplicacion(mensaje, http_status=_estado_http_dupla(mensaje))

    logger.info('Dupla %s registrada por terapeuta %s', dupla, terapeuta.id)
    return {'id_dupla': int(dupla), 'id_sesion_1': int(s1),
            'id_sesion_2': int(s2), 'mensaje': acentuar(mensaje)}


@reintentar_en_deadlock()
def agregar_a_dupla(id_sesion, id_paciente):
    """
    Suma un segundo paciente a una sesion individual ya agendada
    (p_agregar_a_dupla): crea la sesion del companero en el mismo horario y
    arma la dupla. Solo la terapeuta que atendio la sesion.
    """
    terapeuta = terapeuta_actual()
    db.session.execute(
        text(
            'CALL p_agregar_a_dupla(:t, :sesion, :paciente, '
            '@p_dupla, @p_nueva, @p_mensaje)'
        ),
        {'t': terapeuta.id, 'sesion': id_sesion, 'paciente': id_paciente},
    )
    dupla, nueva, mensaje = db.session.execute(
        text('SELECT @p_dupla, @p_nueva, @p_mensaje')
    ).first()
    db.session.commit()

    if dupla is None:
        mensaje = acentuar(mensaje) or 'No se pudo armar la dupla.'
        raise ErrorAplicacion(mensaje, http_status=_estado_http_dupla(mensaje))

    logger.info('Dupla %s armada sobre la sesion %s', dupla, id_sesion)
    return {'id_dupla': int(dupla), 'id_sesion_nueva': int(nueva),
            'mensaje': acentuar(mensaje)}


# ---------------------------------------------------------------------------
# Sesiones registradas (Entrega 5): consulta de lo ya ocurrido
# ---------------------------------------------------------------------------
DIAS_REGISTRADAS_POR_DEFECTO = 90
POR_PAGINA_DEFECTO = 20
POR_PAGINA_MAXIMO = 50


def _entero_positivo(valor, nombre, defecto, maximo=None):
    if valor in (None, ''):
        return defecto
    try:
        numero = int(valor)
    except (TypeError, ValueError):
        raise ErrorAplicacion(f'El valor de "{nombre}" no es válido.', campo=nombre)
    if numero < 1 or (maximo is not None and numero > maximo):
        raise ErrorAplicacion(f'El valor de "{nombre}" no es válido.', campo=nombre)
    return numero


def listar_registradas(filtros):
    """
    Sesiones YA OCURRIDAS y registradas, con filtros y paginacion.

    "Registrada" = ocurrio (su hora de inicio ya paso) y se la cerro como
    completa o ausencia, o tiene al menos una evolucion cargada. Una sesion
    agendada hacia adelante, o que ocurrio y sigue sin registro, no entra:
    esa es la lista de trabajo pendiente del Panel.

    Lectura abierta entre terapeutas (misma politica que la ficha clinica):
    `terapeuta=mias` (por defecto) o `terapeuta=todas`. Editar sigue siendo
    solo de quien atendio; el detalle lo dice con `es_propia`.
    """
    terapeuta = terapeuta_actual()
    hoy = dt.date.today()

    if not filtros.get('desde') and not filtros.get('hasta'):
        fecha_hasta = hoy
        fecha_desde = hoy - dt.timedelta(days=DIAS_REGISTRADAS_POR_DEFECTO - 1)
    else:
        fecha_desde, fecha_hasta = resolver_rango(filtros.get('desde'), filtros.get('hasta'))
    fecha_hasta = min(fecha_hasta, hoy)

    alcance = (filtros.get('terapeuta') or 'mias').strip().lower()
    if alcance not in ('mias', 'todas'):
        raise ErrorAplicacion('El filtro de terapeuta no es válido. Use «mias» o «todas».', campo='terapeuta')
    estado = (filtros.get('estado') or '').strip().lower() or None
    if estado is not None and estado not in ESTADOS:
        raise ErrorAplicacion('El estado indicado no es válido.', campo='estado')
    id_paciente = _entero_positivo(filtros.get('id_paciente'), 'id_paciente', None)
    pagina = _entero_positivo(filtros.get('pagina'), 'pagina', 1)
    por_pagina = _entero_positivo(filtros.get('por_pagina'), 'por_pagina', POR_PAGINA_DEFECTO, POR_PAGINA_MAXIMO)

    con_evolucion = db.session.query(Evolucion.id).filter(Evolucion.id_sesion == Sesion.id).exists()
    consulta = Sesion.query.filter(
        Sesion.fecha >= fecha_desde,
        Sesion.fecha <= fecha_hasta,
        db.func.timestamp(Sesion.fecha, Sesion.hora_inicio) <= dt.datetime.now(),
        db.or_(Sesion.estado.in_(('completa', ESTADO_AUSENCIA)), con_evolucion),
    )
    if alcance == 'mias':
        consulta = consulta.filter(Sesion.id_terapeuta == terapeuta.id)
    if id_paciente:
        consulta = consulta.filter(Sesion.id_paciente == id_paciente)
    if estado:
        consulta = consulta.filter(Sesion.estado == estado)

    total = consulta.count()
    sesiones = (
        consulta.order_by(Sesion.fecha.desc(), Sesion.hora_inicio.desc(), Sesion.id.desc())
        .offset((pagina - 1) * por_pagina).limit(por_pagina).all()
    )
    lista = _serializar_lista(sesiones)
    for datos in lista:
        datos['es_propia'] = datos['terapeuta']['id'] == terapeuta.id
    return {
        'desde': fecha_desde.isoformat(),
        'hasta': fecha_hasta.isoformat(),
        'terapeuta': alcance,
        'pagina': pagina,
        'por_pagina': por_pagina,
        'total': total,
        'paginas': max(1, -(-total // por_pagina)),
        'sesiones': lista,
    }

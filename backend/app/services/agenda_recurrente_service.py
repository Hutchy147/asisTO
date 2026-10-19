# backend/app/services/agenda_recurrente_service.py
# Agenda semanal recurrente (Entrega 3).
#
# La plantilla (tabla agenda_recurrente) dice "los lunes a las 9 viene este
# paciente". Generar la agenda recorre las plantillas de la terapeuta y agenda
# una sesion por cada fecha futura de lunes a viernes a traves de
# sesiones_service.registrar_sesion, o sea por p_registrar_sesion: la
# superposicion, el paciente de baja y la asignacion siguen decidiendolas el
# procedimiento y los triggers. Lo que no se puede agendar se informa como
# omitido, con el motivo; nunca se aborta toda la generacion por una fecha.

import datetime as dt
import logging

from sqlalchemy import text

from app import db
from app.models import AgendaRecurrente, Paciente, Sesion
from app.models.sesion import formatear_hora
from app.services.asignaciones_service import ids_de_pacientes_asignados
from app.services.sesiones_service import (
    DIAS_HABILES, _hora_fin_por_defecto, agregar_a_dupla, registrar_dupla,
    registrar_sesion, terapeuta_actual,
)
from app.utils.db import reintentar_en_deadlock
from app.utils.errors import ErrorAplicacion
from app.utils.textos import acentuar

logger = logging.getLogger(__name__)

# Cuantas semanas hacia adelante se puede generar de una vez. Cuatro es un
# mes de agenda; el tope evita llenar la tabla de sesiones por un error de
# tipeo ("520" semanas).
SEMANAS_POR_DEFECTO = 4
SEMANAS_MAXIMAS = 8
MAXIMO_PLANTILLAS_POR_TERAPEUTA = 60


def _a_segundos(hora_iso):
    try:
        partes = [int(x) for x in hora_iso.split(':')]
        return partes[0] * 3600 + partes[1] * 60 + (partes[2] if len(partes) > 2 else 0)
    except (ValueError, IndexError, AttributeError):
        raise ErrorAplicacion('La hora de inicio no es valida.', campo='hora_inicio')


def _a_hora(segundos):
    return f'{segundos // 3600:02d}:{segundos % 3600 // 60:02d}:{segundos % 60:02d}'


def _segundos_de_time(valor):
    return _a_segundos(formatear_hora(valor))


def _grupos_de_dupla(filas):
    """
    {id_dupla: [turnos activos]} solo para las duplas COMPLETAS (dos turnos
    activos). Un turno cuya hermana se quito queda con su id_dupla pero se
    lee como individual.
    """
    grupos = {}
    for f in filas:
        if f.id_dupla:
            grupos.setdefault(f.id_dupla, []).append(f)
    return {k: v for k, v in grupos.items() if len(v) == 2}


def listar_plantillas():
    terapeuta = terapeuta_actual()
    filas = (
        AgendaRecurrente.query
        .filter_by(id_terapeuta=terapeuta.id, activo=True)
        .order_by(AgendaRecurrente.dia_semana, AgendaRecurrente.hora_inicio,
                  AgendaRecurrente.id)
        .all()
    )
    grupos = _grupos_de_dupla(filas)
    resultado = []
    for f in filas:
        datos = f.to_dict()
        pareja = [x for x in grupos.get(f.id_dupla, []) if x.id != f.id]
        # id_dupla solo viaja si la dupla esta completa: el cliente agrupa por ahi
        datos['id_dupla'] = f.id_dupla if pareja else None
        datos['companero'] = {
            'id_turno': pareja[0].id,
            'id_paciente': pareja[0].id_paciente,
            'paciente': pareja[0].to_dict()['paciente'],
        } if pareja else None
        resultado.append(datos)
    return {'plantillas': resultado, 'total': len(resultado)}


def crear_plantilla(datos):
    terapeuta = terapeuta_actual()

    id_paciente = datos.get('id_paciente')
    id_paciente_2 = datos.get('id_paciente_2')
    dia = datos.get('dia_semana')
    hora_inicio = (datos.get('hora_inicio') or '').strip()
    hora_fin = (datos.get('hora_fin') or '').strip() or None

    faltantes = [e for e, v in (('id_paciente', id_paciente), ('dia_semana', dia),
                                ('hora_inicio', hora_inicio)) if v is None or v == '']
    if faltantes:
        raise ErrorAplicacion('Faltan datos obligatorios: ' + ', '.join(faltantes))

    if not isinstance(dia, int) or isinstance(dia, bool) or not 1 <= dia <= DIAS_HABILES:
        raise ErrorAplicacion(
            'El dia tiene que ser de lunes (1) a viernes (5).', campo='dia_semana'
        )

    inicio = _a_segundos(hora_inicio)
    if hora_fin is None:
        hora_fin = _hora_fin_por_defecto(hora_inicio)
        if hora_fin is None:
            raise ErrorAplicacion(
                'La sesion tiene que terminar el mismo dia.', campo='hora_inicio'
            )
    fin = _a_segundos(hora_fin)
    if fin <= inicio:
        raise ErrorAplicacion(
            'La hora de fin debe ser posterior a la de inicio.', campo='hora_fin'
        )

    if id_paciente_2 not in (None, ''):
        return _crear_turno_dupla(terapeuta, id_paciente, id_paciente_2, dia, inicio, fin)

    paciente = Paciente.query.get(id_paciente)
    if paciente is None:
        raise ErrorAplicacion('El paciente indicado no existe.', campo='id_paciente',
                              http_status=404)
    if not paciente.activo:
        raise ErrorAplicacion('El paciente esta dado de baja.', campo='id_paciente')
    # Regla 8 aplicada a la plantilla: no se planifica a quien no se atiende.
    if paciente.id not in ids_de_pacientes_asignados(terapeuta.id):
        raise ErrorAplicacion(
            'El paciente no está asignado a su usuario: solicite la asignación al '
            'administrador antes de agendarlo.', campo='id_paciente',
        )

    activas = AgendaRecurrente.query.filter_by(id_terapeuta=terapeuta.id, activo=True)
    if activas.count() >= MAXIMO_PLANTILLAS_POR_TERAPEUTA:
        raise ErrorAplicacion(
            f'La agenda semanal admite hasta {MAXIMO_PLANTILLAS_POR_TERAPEUTA} turnos.'
        )

    # Dos turnos de la misma terapeuta no pueden pisarse el mismo dia.
    # Es la misma regla de superposicion de las sesiones, aplicada a la
    # plantilla para avisar al cargarla y no recien al generar.
    for otra in activas.filter_by(dia_semana=dia).all():
        if inicio < _segundos_de_time(otra.hora_fin) and fin > _segundos_de_time(otra.hora_inicio):
            raise ErrorAplicacion(
                'Ese horario se superpone con otro turno de su agenda semanal.',
                campo='hora_inicio',
            )

    fila = AgendaRecurrente(
        id_terapeuta=terapeuta.id, id_paciente=paciente.id, dia_semana=dia,
        hora_inicio=_a_hora(inicio), hora_fin=_a_hora(fin), activo=True,
    )
    db.session.add(fila)
    db.session.commit()
    logger.info('Turno recurrente %s creado por terapeuta %s', fila.id, terapeuta.id)
    return {'turno': fila.to_dict()}


def _estado_http_turno(mensaje):
    texto = (mensaje or '').lower()
    if 'no existe' in texto:
        return 404
    if 'propia agenda' in texto:
        return 403
    if 'ya integra' in texto or 'superpone' in texto:
        return 409
    return 400


def _limite_de_turnos(terapeuta, nuevos):
    activos = AgendaRecurrente.query.filter_by(id_terapeuta=terapeuta.id, activo=True).count()
    if activos + nuevos > MAXIMO_PLANTILLAS_POR_TERAPEUTA:
        raise ErrorAplicacion(
            f'La agenda semanal admite hasta {MAXIMO_PLANTILLAS_POR_TERAPEUTA} turnos.'
        )


@reintentar_en_deadlock()
def _crear_turno_dupla(terapeuta, id_paciente_1, id_paciente_2, dia, inicio, fin):
    """Turno semanal en dupla (p_crear_turno_dupla): dos filas, una sola unidad."""
    _limite_de_turnos(terapeuta, 2)
    db.session.execute(
        text(
            'CALL p_crear_turno_dupla(:t, :p1, :p2, :dia, :inicio, :fin, '
            '@p_dupla, @p_mensaje)'
        ),
        {'t': terapeuta.id, 'p1': id_paciente_1, 'p2': id_paciente_2, 'dia': dia,
         'inicio': _a_hora(inicio), 'fin': _a_hora(fin)},
    )
    dupla, mensaje = db.session.execute(text('SELECT @p_dupla, @p_mensaje')).first()
    db.session.commit()
    if dupla is None:
        mensaje = acentuar(mensaje) or 'No se pudo crear el turno en dupla.'
        raise ErrorAplicacion(mensaje, http_status=_estado_http_turno(mensaje))

    filas = (
        AgendaRecurrente.query.filter_by(id_dupla=dupla, activo=True)
        .order_by(AgendaRecurrente.id).all()
    )
    logger.info('Turno en dupla %s creado por terapeuta %s', dupla, terapeuta.id)
    return {'turno': filas[0].to_dict(), 'companero': filas[1].to_dict(),
            'id_dupla': int(dupla), 'mensaje': acentuar(mensaje)}


@reintentar_en_deadlock()
def sumar_companero(id_turno, id_paciente):
    """Convierte un turno individual en turno en dupla (p_sumar_companero_a_turno)."""
    terapeuta = terapeuta_actual()
    if id_paciente in (None, ''):
        raise ErrorAplicacion('Falta indicar el paciente que se suma.', campo='id_paciente')
    _limite_de_turnos(terapeuta, 1)
    db.session.execute(
        text(
            'CALL p_sumar_companero_a_turno(:t, :turno, :paciente, '
            '@p_dupla, @p_mensaje)'
        ),
        {'t': terapeuta.id, 'turno': id_turno, 'paciente': id_paciente},
    )
    dupla, mensaje = db.session.execute(text('SELECT @p_dupla, @p_mensaje')).first()
    db.session.commit()
    if dupla is None:
        mensaje = acentuar(mensaje) or 'No se pudo armar la dupla.'
        raise ErrorAplicacion(mensaje, http_status=_estado_http_turno(mensaje),
                              campo='id_paciente')
    logger.info('Dupla %s armada sobre el turno %s', dupla, id_turno)
    return {'id_dupla': int(dupla), 'mensaje': acentuar(mensaje)}


def quitar_plantilla(id_plantilla, dupla_completa=False):
    """
    Quita un turno de la agenda. En un turno en dupla se puede quitar solo a
    un paciente (el otro sigue como turno individual) o la dupla entera.
    """
    terapeuta = terapeuta_actual()
    fila = AgendaRecurrente.query.get(id_plantilla)
    if fila is None or not fila.activo:
        raise ErrorAplicacion('El turno indicado no existe.', http_status=404)
    if fila.id_terapeuta != terapeuta.id:
        raise ErrorAplicacion('Solo puede modificar su propia agenda.', http_status=403)
    fila.activo = False
    if dupla_completa and fila.id_dupla:
        for otra in AgendaRecurrente.query.filter_by(
                id_dupla=fila.id_dupla, id_terapeuta=terapeuta.id, activo=True).all():
            otra.activo = False
    db.session.commit()
    return {'mensaje': 'Turno quitado de la agenda semanal. Las sesiones ya generadas no se tocan.'}


def _generar_dupla_del_dia(terapeuta, dia, a, b):
    """
    Sesiones de UN turno en dupla para UNA fecha. Devuelve (creadas,
    existentes, omitidas). Idempotente, y tolera que ya exista la sesion de
    uno de los dos (agendada antes de que el turno fuera en dupla): en ese
    caso se le suma el companero con p_agregar_a_dupla.
    """
    hora_inicio = formatear_hora(a.hora_inicio)
    base = {'fecha': dia.isoformat(), 'hora_inicio': hora_inicio}
    nombre = {a.id_paciente: a.to_dict()['paciente'], b.id_paciente: b.to_dict()['paciente']}

    def omitir(paciente_id, motivo):
        return {**base, 'paciente': nombre[paciente_id], 'motivo': motivo}

    sa = Sesion.query.filter_by(id_paciente=a.id_paciente, fecha=dia, hora_inicio=a.hora_inicio).first()
    sb = Sesion.query.filter_by(id_paciente=b.id_paciente, fecha=dia, hora_inicio=b.hora_inicio).first()

    ajena = 'El paciente ya tiene una sesion a esa hora con otra terapeuta.'
    if sa is not None and sb is not None:
        if sa.id_terapeuta != terapeuta.id:
            return 0, 0, [omitir(a.id_paciente, ajena)]
        if sb.id_terapeuta != terapeuta.id:
            return 0, 0, [omitir(b.id_paciente, ajena)]
        if sa.id_dupla and sa.id_dupla == sb.id_dupla:
            return 0, 2, []
        return 0, 0, [omitir(
            b.id_paciente, 'Las sesiones existentes de ese horario no forman una dupla.')]

    try:
        if sa is None and sb is None:
            registrar_dupla(a.id_paciente, b.id_paciente, dia.isoformat(), hora_inicio,
                            formatear_hora(a.hora_fin))
            return 2, 0, []

        existente, nuevo = (sa, b) if sa is not None else (sb, a)
        if existente.id_terapeuta != terapeuta.id:
            return 0, 0, [omitir(existente.id_paciente, ajena)]
        if existente.id_dupla:
            return 0, 0, [omitir(
                nuevo.id_paciente,
                'La sesion de su companero ya integra otra dupla ese dia.')]
        agregar_a_dupla(existente.id, nuevo.id_paciente)
        return 1, 1, []
    except ErrorAplicacion as error:
        db.session.rollback()
        return 0, 0, [{
            **base, 'paciente': f'{nombre[a.id_paciente]} y {nombre[b.id_paciente]}',
            'motivo': error.mensaje,
        }]


def generar_agenda(datos, hoy=None):
    """
    Genera las sesiones de las proximas `semanas` semanas (desde hoy
    inclusive) segun las plantillas vigentes.

    Es idempotente: una sesion que ya existe para ese paciente, fecha y hora
    se cuenta como `existentes` y no se vuelve a crear, asi que se puede
    apretar dos veces sin duplicar nada. Las sesiones se agendan en estado
    'incompleta', igual que al agendar a mano desde el calendario.
    """
    terapeuta = terapeuta_actual()
    semanas = datos.get('semanas', SEMANAS_POR_DEFECTO)
    if (not isinstance(semanas, int) or isinstance(semanas, bool)
            or not 1 <= semanas <= SEMANAS_MAXIMAS):
        raise ErrorAplicacion(
            f'Las semanas tienen que ser entre 1 y {SEMANAS_MAXIMAS}.', campo='semanas'
        )

    hoy = hoy or dt.date.today()
    hasta = hoy + dt.timedelta(days=semanas * 7 - 1)

    plantillas = (
        AgendaRecurrente.query
        .filter_by(id_terapeuta=terapeuta.id, activo=True)
        .order_by(AgendaRecurrente.dia_semana, AgendaRecurrente.hora_inicio)
        .all()
    )
    if not plantillas:
        raise ErrorAplicacion(
            'Todavía no cargó turnos en su agenda semanal.', http_status=409
        )

    grupos = _grupos_de_dupla(plantillas)
    # La dupla se procesa UNA vez por dia, desde su primer turno
    primeros = {min(t.id for t in g) for g in grupos.values()}

    creadas, existentes, omitidas = 0, 0, []
    dia = hoy
    while dia <= hasta:
        for pl in plantillas:
            if pl.dia_semana != dia.weekday() + 1:
                continue
            if pl.id_dupla in grupos:
                if pl.id not in primeros:
                    continue
                par = sorted(grupos[pl.id_dupla], key=lambda t: t.id)
                c, e, o = _generar_dupla_del_dia(terapeuta, dia, par[0], par[1])
                creadas += c
                existentes += e
                omitidas.extend(o)
                continue
            hora_inicio = formatear_hora(pl.hora_inicio)
            ya = Sesion.query.filter_by(
                id_paciente=pl.id_paciente, fecha=dia, hora_inicio=pl.hora_inicio
            ).first()
            if ya is not None:
                if ya.id_terapeuta == terapeuta.id:
                    existentes += 1
                else:
                    omitidas.append({
                        'fecha': dia.isoformat(), 'hora_inicio': hora_inicio,
                        'paciente': pl.to_dict()['paciente'],
                        'motivo': 'El paciente ya tiene una sesion a esa hora con otra terapeuta.',
                    })
                continue
            try:
                registrar_sesion({
                    'id_paciente': pl.id_paciente, 'fecha': dia.isoformat(),
                    'hora_inicio': hora_inicio, 'hora_fin': formatear_hora(pl.hora_fin),
                    'estado': 'incompleta',
                }, notificar=False)  # turnos generados: no son sesiones cargadas
                creadas += 1
            except ErrorAplicacion as error:
                db.session.rollback()
                omitidas.append({
                    'fecha': dia.isoformat(), 'hora_inicio': hora_inicio,
                    'paciente': pl.to_dict()['paciente'], 'motivo': error.mensaje,
                })
        dia += dt.timedelta(days=1)

    logger.info('Agenda generada para terapeuta %s: %s creadas, %s existentes, %s omitidas',
                terapeuta.id, creadas, existentes, len(omitidas))
    return {
        'desde': hoy.isoformat(), 'hasta': hasta.isoformat(), 'semanas': semanas,
        'creadas': creadas, 'existentes': existentes, 'omitidas': omitidas,
    }

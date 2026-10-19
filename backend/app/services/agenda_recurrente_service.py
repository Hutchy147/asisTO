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

from app import db
from app.models import AgendaRecurrente, Paciente, Sesion
from app.models.sesion import formatear_hora
from app.services.asignaciones_service import ids_de_pacientes_asignados
from app.services.sesiones_service import (
    DIAS_HABILES, _hora_fin_por_defecto, registrar_sesion, terapeuta_actual,
)
from app.utils.errors import ErrorAplicacion

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


def listar_plantillas():
    terapeuta = terapeuta_actual()
    filas = (
        AgendaRecurrente.query
        .filter_by(id_terapeuta=terapeuta.id, activo=True)
        .order_by(AgendaRecurrente.dia_semana, AgendaRecurrente.hora_inicio)
        .all()
    )
    return {'plantillas': [f.to_dict() for f in filas], 'total': len(filas)}


def crear_plantilla(datos):
    terapeuta = terapeuta_actual()

    id_paciente = datos.get('id_paciente')
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
    return fila.to_dict()


def quitar_plantilla(id_plantilla):
    terapeuta = terapeuta_actual()
    fila = AgendaRecurrente.query.get(id_plantilla)
    if fila is None or not fila.activo:
        raise ErrorAplicacion('El turno indicado no existe.', http_status=404)
    if fila.id_terapeuta != terapeuta.id:
        raise ErrorAplicacion('Solo puede modificar su propia agenda.', http_status=403)
    fila.activo = False
    db.session.commit()
    return {'mensaje': 'Turno quitado de la agenda semanal. Las sesiones ya generadas no se tocan.'}


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

    creadas, existentes, omitidas = 0, 0, []
    dia = hoy
    while dia <= hasta:
        for pl in plantillas:
            if pl.dia_semana != dia.weekday() + 1:
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
                })
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

# backend/app/services/portal_familiar_service.py
# Portal del familiar (Entrega 4): consulta de la evolucion del paciente
# vinculado. Es una VISTA REDUCIDA de la evolucion clinica, no la misma
# respuesta con campos escondidos en el front:
#
#   - Solo pacientes vinculados a la cuenta (familiares_pacientes). Un
#     paciente ajeno recibe 403, igual que uno inexistente: no se revela si existe.
#   - Sin diagnostico, sin observaciones por evolucion, sin nombres de
#     terapeutas, sin motivo de baja, sin numero de historia ni obra social.
#   - Solo sesiones ya ocurridas (fecha <= hoy): lo agendado a futuro no es
#     evolucion y no se muestra.
#
# El calculo de la serie se reutiliza de evoluciones_service (una sola
# version de la regla); aca solo se recorta lo que el familiar no debe ver.

import datetime as dt

from flask import g

from app import db
from app.models import Familiar, FamiliarPaciente, Informe, Paciente
from app.services import informes_pdf
from app.services.evoluciones_service import evolucion_de_paciente
from app.services.informes_generador import ETIQUETA_TIPO, etiqueta_periodo
from app.services.sesiones_service import MAXIMO_DIAS_RANGO, resolver_rango_pasado
from app.utils.errors import ErrorAplicacion


def _familiar_actual():
    familiar = Familiar.query.filter_by(id_usuario=g.usuario_actual.id).first()
    if familiar is None:
        raise ErrorAplicacion(
            'Su cuenta no tiene un perfil de familiar asociado. '
            'Comuníquese con el centro.',
            http_status=409,
        )
    return familiar


def _estado(paciente):
    if paciente.activo:
        return 'en_tratamiento'
    return paciente.tipo_cierre or 'alta'


def _resumen_paciente(paciente):
    return {
        'id': paciente.id,
        'nombre_completo': paciente.nombre_completo,
        'fecha_nacimiento': paciente.fecha_nacimiento.isoformat() if paciente.fecha_nacimiento else None,
        'fecha_alta': paciente.fecha_alta.isoformat() if paciente.fecha_alta else None,
        'estado': _estado(paciente),
        'fecha_baja': paciente.fecha_baja.isoformat() if paciente.fecha_baja else None,
    }


def listar_pacientes_vinculados():
    familiar = _familiar_actual()
    pacientes = (
        db.session.query(Paciente)
        .join(FamiliarPaciente, FamiliarPaciente.id_paciente == Paciente.id)
        .filter(FamiliarPaciente.id_familiar == familiar.id)
        .order_by(Paciente.apellido, Paciente.nombre)
        .all()
    )
    return {'pacientes': [_resumen_paciente(p) for p in pacientes], 'total': len(pacientes)}


def ids_de_pacientes_vinculados(id_familiar):
    filas = (
        db.session.query(FamiliarPaciente.id_paciente)
        .filter(FamiliarPaciente.id_familiar == id_familiar)
        .all()
    )
    return {f[0] for f in filas}


def _verificar_vinculo(id_paciente):
    familiar = _familiar_actual()
    if id_paciente not in ids_de_pacientes_vinculados(familiar.id):
        raise ErrorAplicacion(
            'El paciente indicado no está vinculado a su cuenta.',
            http_status=403,
        )
    return familiar


def evolucion_vinculada(id_paciente, desde=None, hasta=None):
    """Evolucion reducida de un paciente vinculado a la cuenta."""
    _verificar_vinculo(id_paciente)
    return evolucion_reducida(id_paciente, desde, hasta)


def _hora_posterior(hora_inicio, ahora):
    """True si la hora (HH:MM[:SS]) todavia no llego hoy."""
    try:
        return dt.time.fromisoformat(str(hora_inicio)) > ahora.time()
    except ValueError:
        return False


def evolucion_reducida(id_paciente, desde=None, hasta=None):
    """
    Evolucion reducida: objetivos con el valor de cada sesion ocurrida, mas
    un resumen por objetivo y el detalle por sesion.

    NO verifica quien pregunta: la usan el portal del familiar (que valida el
    vinculo antes) y el portal del paciente (que valida que sea SU ficha).
    Una sola version de la regla de que se recorta.
    """
    ahora = dt.datetime.now()
    hoy = ahora.date()
    if desde and hasta:
        # Con las dos puntas se valida igual que el resto; lo que no se acepta
        # es un periodo que todavia no empezo (se veria "del 01/12 al 22/10").
        resolver_rango_pasado(desde, hasta, MAXIMO_DIAS_RANGO)
    completa = evolucion_de_paciente(id_paciente, desde, hasta)
    paciente = Paciente.query.get(id_paciente)

    objetivos = []
    sesiones = {}
    calificados = 0
    for objetivo in completa['objetivos']:
        puntos = []
        for punto in objetivo['puntos']:
            # Solo lo ya ocurrido: la sesion de hoy entra cuando llega su hora.
            fecha_punto = dt.date.fromisoformat(punto['fecha'])
            if fecha_punto > hoy or (fecha_punto == hoy and _hora_posterior(punto['hora_inicio'], ahora)):
                continue
            puntos.append({
                'id_sesion': punto['id_sesion'],
                'fecha': punto['fecha'],
                'estado_sesion': punto['estado_sesion'],
                'valor': punto['valor'],
            })
            sesion = sesiones.setdefault(punto['id_sesion'], {
                'id_sesion': punto['id_sesion'],
                'fecha': punto['fecha'],
                'hora_inicio': punto['hora_inicio'],
                'estado_sesion': punto['estado_sesion'],
                'valores': [],
            })
            if punto['valor'] is not None:
                sesion['valores'].append({
                    'id_objetivo': objetivo['id'],
                    'objetivo': objetivo['descripcion'],
                    'valor': punto['valor'],
                })
        valores = [p['valor'] for p in puntos if p['valor'] is not None]
        calificados += len(valores)
        objetivos.append({
            'id': objetivo['id'],
            'descripcion': objetivo['descripcion'],
            'activo': objetivo['activo'],
            'fecha_archivado': objetivo['fecha_archivado'],
            'puntos': puntos,
            'resumen': {
                'calificados': len(valores),
                'ultimo': valores[-1] if valores else None,
            },
        })

    periodo = dict(completa['periodo'])
    if periodo.get('hasta') and dt.date.fromisoformat(periodo['hasta']) > hoy:
        periodo['hasta'] = hoy.isoformat()

    ordenadas = sorted(sesiones.values(), key=lambda s: (s['fecha'], s['hora_inicio']), reverse=True)
    return {
        'paciente': _resumen_paciente(paciente),
        'periodo': periodo,
        'objetivos': objetivos,
        'sesiones': ordenadas,
        'total_sesiones': len(ordenadas),
        'total_calificados': calificados,
    }


# ---------------------------------------------------------------------------
# Informes publicados (Entrega 6, HDU 8)
# ---------------------------------------------------------------------------
# El familiar ve SOLO los informes en estado final (publicados) de sus
# pacientes vinculados. Nunca borradores ni versiones reemplazadas. Igual que
# en el resto del portal, no se le muestran nombres de terapeutas.
def _resumen_informe(informe):
    return {
        'id': informe.id,
        'id_paciente': informe.id_paciente,
        'tipo': informe.tipo,
        'tipo_etiqueta': ETIQUETA_TIPO.get(informe.tipo, informe.tipo),
        'periodo': informe.periodo,
        'periodo_etiqueta': etiqueta_periodo(informe.tipo, informe.periodo),
        'fecha_desde': informe.fecha_desde.isoformat(),
        'fecha_hasta': informe.fecha_hasta.isoformat(),
        'version': informe.version,
        'estado': informe.estado,
        'fecha_publicacion': informe.fecha_publicacion.isoformat() if informe.fecha_publicacion else None,
    }


def listar_informes_vinculados(id_paciente):
    _verificar_vinculo(id_paciente)
    paciente = Paciente.query.get(id_paciente)
    informes = (
        Informe.query.filter_by(id_paciente=id_paciente, estado='final')
        .order_by(Informe.fecha_publicacion.desc(), Informe.id.desc()).all()
    )
    return {
        'paciente': _resumen_paciente(paciente),
        'informes': [_resumen_informe(i) for i in informes],
        'total': len(informes),
    }


def _informe_publicado(id_paciente, id_informe):
    _verificar_vinculo(id_paciente)
    informe = Informe.query.get(id_informe)
    # Inexistente, de otro paciente, borrador o reemplazado: todo es "no existe".
    if informe is None or informe.id_paciente != id_paciente or informe.estado != 'final':
        raise ErrorAplicacion('El informe indicado no existe.', http_status=404)
    return informe


def obtener_informe_vinculado(id_paciente, id_informe):
    informe = _informe_publicado(id_paciente, id_informe)
    datos = _resumen_informe(informe)
    datos['contenido'] = informe.contenido if informe.contenido is not None else informe.contenido_original
    datos['paciente'] = _resumen_paciente(Paciente.query.get(id_paciente))
    return datos


def pdf_informe_vinculado(id_paciente, id_informe):
    """(bytes, nombre_de_archivo) del PDF de un informe publicado."""
    datos = obtener_informe_vinculado(id_paciente, id_informe)
    nombre = datos['paciente']['nombre_completo']
    datos['periodo_etiqueta'] = datos['periodo_etiqueta']
    return (
        informes_pdf.generar_pdf(datos, nombre, 'Equipo terapéutico del centro'),
        informes_pdf.nombre_de_archivo(datos, nombre),
    )

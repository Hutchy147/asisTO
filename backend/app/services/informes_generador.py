# backend/app/services/informes_generador.py
# Generador de informes (Entrega 6, HDU 5).
#
# DOS CAMINOS, UN MISMO RESULTADO (un borrador de texto con secciones):
#
#   1. PLANTILLA. Vuelca los datos del periodo en un texto con la estructura
#      del rubro. No usa IA y no manda nada fuera del servidor. Es el camino
#      por omision y el que hay que probar siempre.
#   2. IA. Si el centro configuro un proveedor y una clave en el .env, la IA
#      redacta las secciones narrativas a partir de los mismos datos. Si el
#      proveedor falla, el informe se genera igual con la plantilla y se avisa.
#
# QUE NUNCA HACE: publicar. El resultado es siempre un borrador que una
# persona revisa. Tampoco inventa datos: la IA recibe solo lo que registro el
# equipo, y lo que falte queda como una marca [COMPLETAR ...] que impide
# publicar mientras no se resuelva (lo hace cumplir p_publicar_informe).
#
# PRIVACIDAD. Al proveedor de IA nunca viaja el nombre del paciente ni su
# apellido: se reemplazan por "el paciente" en todos los textos. Es un
# resguardo de mejor esfuerzo, no una garantia: un nombre propio escrito en
# una nota con otra grafia no se detecta. Por eso la IA queda apagada si el
# centro no la configura expresamente.
#
# ESCALA. Las calificaciones se comunican siempre con las cinco palabras
# (No logrado / Inicial / En proceso / Avanzado / Logrado), nunca con numeros
# ni promedios: es la decision de producto de toda la aplicacion.

import calendar
import datetime as dt
import json
import logging
import re
import unicodedata
import urllib.error
import urllib.request

from flask import current_app
from sqlalchemy import text

from app import db
from app.models import Evolucion, ObjetivoTerapeutico, Sesion, SesionRenglon
from app.utils.errors import ErrorAplicacion
from app.utils.textos import acentuar

logger = logging.getLogger(__name__)

ETIQUETA_ESCALA = {1: 'No logrado', 2: 'Inicial', 3: 'En proceso', 4: 'Avanzado', 5: 'Logrado'}
ETIQUETA_TIPO = {'mensual': 'Informe mensual', 'semestral': 'Informe semestral', 'pti': 'Plan terapéutico integral (PTI)'}
MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
         'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']

MAXIMO_OBSERVACION = 320
MAXIMO_OBSERVACIONES_PLANTILLA = 12
MARCA_COMPLETAR = '[COMPLETAR'

_RE_MENSUAL = re.compile(r'^(\d{4})-(0[1-9]|1[0-2])$')
_RE_SEMESTRAL = re.compile(r'^(\d{4})-S([12])$')


# ---------------------------------------------------------------------------
# Periodos
# ---------------------------------------------------------------------------
def fecha_corta(valor):
    return valor.strftime('%d/%m/%Y')


def etiqueta_periodo(tipo, periodo):
    """Texto legible del periodo: 'septiembre de 2026', 'primer semestre de 2026'."""
    if tipo == 'mensual':
        m = _RE_MENSUAL.match(periodo or '')
        if m:
            return f'{MESES[int(m.group(2)) - 1]} de {m.group(1)}'
    elif tipo == 'semestral':
        m = _RE_SEMESTRAL.match(periodo or '')
        if m:
            return f"{'primer' if m.group(2) == '1' else 'segundo'} semestre de {m.group(1)}"
    elif tipo == 'pti':
        return 'ingreso'
    return periodo


def clave_mensual(fecha):
    return f'{fecha.year:04d}-{fecha.month:02d}'


def clave_semestral(fecha):
    return f'{fecha.year:04d}-S{1 if fecha.month <= 6 else 2}'


def calcular_periodo(tipo, periodo, hoy=None):
    """
    (clave, desde, hasta) de un informe mensual o semestral. El `hasta` se
    recorta a hoy: un informe del mes en curso cubre hasta hoy. Un periodo que
    todavia no empezo se rechaza.
    """
    hoy = hoy or dt.date.today()
    if tipo == 'mensual':
        m = _RE_MENSUAL.match(periodo or '')
        if not m:
            raise ErrorAplicacion('El período mensual debe tener el formato AAAA-MM.', campo='periodo')
        anio, mes = int(m.group(1)), int(m.group(2))
        desde = dt.date(anio, mes, 1)
        hasta = dt.date(anio, mes, calendar.monthrange(anio, mes)[1])
    elif tipo == 'semestral':
        m = _RE_SEMESTRAL.match(periodo or '')
        if not m:
            raise ErrorAplicacion('El período semestral debe tener el formato AAAA-S1 o AAAA-S2.', campo='periodo')
        anio, semestre = int(m.group(1)), int(m.group(2))
        desde = dt.date(anio, 1 if semestre == 1 else 7, 1)
        hasta = dt.date(anio, 6, 30) if semestre == 1 else dt.date(anio, 12, 31)
    else:
        raise ErrorAplicacion('El tipo de informe indicado no es válido.', campo='tipo')
    if desde > hoy:
        raise ErrorAplicacion('Ese período todavía no empezó: no se puede generar el informe.', campo='periodo')
    return periodo, desde, min(hasta, hoy)


# ---------------------------------------------------------------------------
# Recoleccion de datos del periodo (los "diarios")
# ---------------------------------------------------------------------------
def edad_texto(fecha_nacimiento, hoy=None):
    hoy = hoy or dt.date.today()
    anios = hoy.year - fecha_nacimiento.year - ((hoy.month, hoy.day) < (fecha_nacimiento.month, fecha_nacimiento.day))
    if anios < 1:
        meses = (hoy.year - fecha_nacimiento.year) * 12 + hoy.month - fecha_nacimiento.month - (hoy.day < fecha_nacimiento.day)
        return f'{max(meses, 0)} meses'
    return f'{anios} años' if anios != 1 else '1 año'


def _recortar(texto, maximo=MAXIMO_OBSERVACION):
    texto = ' '.join((texto or '').split())
    return texto if len(texto) <= maximo else texto[: maximo - 1].rstrip() + '…'


def diarios_del_periodo(id_paciente, desde, hasta):
    """
    Lo que se registro dia por dia en el periodo, sesion por sesion: estado,
    renglones del plan y del registro, nota libre y lo evaluado en cada objetivo.
    Es el insumo de los informes grandes y lo que la terapeuta consulta mientras
    revisa el borrador. Solo sesiones ya ocurridas (fecha <= hoy).
    """
    tope = min(hasta, dt.date.today())
    sesiones = (
        Sesion.query
        .filter(Sesion.id_paciente == id_paciente, Sesion.fecha >= desde, Sesion.fecha <= tope)
        .order_by(Sesion.fecha, Sesion.hora_inicio)
        .all()
    )
    ids = [s.id for s in sesiones]
    renglones, evoluciones = {}, {}
    if ids:
        for r in (
            SesionRenglon.query.filter(SesionRenglon.id_sesion.in_(ids))
            .order_by(SesionRenglon.id_sesion, SesionRenglon.momento, SesionRenglon.orden).all()
        ):
            renglones.setdefault(r.id_sesion, []).append(r)
        filas = (
            db.session.query(Evolucion, ObjetivoTerapeutico.descripcion)
            .join(ObjetivoTerapeutico, ObjetivoTerapeutico.id == Evolucion.id_objetivo)
            .filter(Evolucion.id_sesion.in_(ids))
            .order_by(Evolucion.id_sesion, Evolucion.id)
            .all()
        )
        for evolucion, descripcion in filas:
            evoluciones.setdefault(evolucion.id_sesion, []).append((evolucion, descripcion))

    diarios = []
    for s in sesiones:
        diarios.append({
            'id_sesion': s.id,
            'fecha': s.fecha.isoformat(),
            'hora_inicio': s.hora_inicio.strftime('%H:%M') if hasattr(s.hora_inicio, 'strftime') else str(s.hora_inicio)[:5],
            'estado': s.estado,
            'nota': (s.notas or '').strip() or None,
            'plan': [
                {'texto': r.texto, 'destacado': bool(r.destacado), 'cierre': r.cierre}
                for r in renglones.get(s.id, []) if r.momento == 'plan'
            ],
            'registro': [
                {'texto': r.texto, 'destacado': bool(r.destacado)}
                for r in renglones.get(s.id, []) if r.momento == 'registro'
            ],
            'objetivos': [
                {
                    'id_objetivo': e.id_objetivo,
                    'objetivo': descripcion,
                    'valor': ETIQUETA_ESCALA.get(int(e.valor), str(e.valor)),
                    'observaciones': (e.observaciones or '').strip() or None,
                }
                for e, descripcion in evoluciones.get(s.id, [])
            ],
        })
    return diarios


def _tendencias(id_paciente, desde, hasta):
    filas = db.session.execute(
        text('CALL p_tendencia_paciente(:id, :desde, :hasta, @p_mensaje)'),
        {'id': id_paciente, 'desde': desde, 'hasta': hasta},
    ).all()
    mensaje = db.session.execute(text('SELECT @p_mensaje')).scalar()
    if mensaje:
        raise ErrorAplicacion(acentuar(mensaje))

    def palabra(valor):
        return ETIQUETA_ESCALA.get(int(valor)) if valor is not None else None

    return [
        {
            'id': int(f[0]), 'descripcion': f[1], 'activo': bool(f[2]),
            'calificaciones': int(f[3]), 'nivel': palabra(f[4]),
            'calificaciones_anterior': int(f[5]), 'nivel_anterior': palabra(f[6]),
            'tendencia': f[7], 'cambio': f[8],
        }
        for f in filas
    ]


def recolectar(paciente, tipo, desde, hasta, pti=None):
    """Todos los datos que el generador necesita, sin texto armado."""
    diarios = diarios_del_periodo(paciente.id, desde, hasta)
    completas = sum(1 for d in diarios if d['estado'] == 'completa' or (d['estado'] == 'incompleta' and d['objetivos']))
    ausencias = sum(1 for d in diarios if d['estado'] == 'ausencia')
    return {
        'tipo': tipo,
        'paciente': {
            'nombre_completo': paciente.nombre_completo,
            'nombre': paciente.nombre,
            'apellido': paciente.apellido,
            'fecha_nacimiento': paciente.fecha_nacimiento,
            'edad': edad_texto(paciente.fecha_nacimiento),
        },
        'periodo': {'desde': desde, 'hasta': hasta},
        'asistencia': {'sesiones': completas, 'ausencias': ausencias},
        'objetivos': _tendencias(paciente.id, desde, hasta) if tipo != 'pti' else [],
        'diarios': diarios,
        'pti': pti,
    }


# ---------------------------------------------------------------------------
# Plantilla (sin IA)
# ---------------------------------------------------------------------------
def _encabezado(datos, etiqueta):
    p = datos['paciente']
    return (
        '## Datos del paciente\n'
        f"{p['nombre_completo']}, {p['edad']} (nacimiento: {fecha_corta(p['fecha_nacimiento'])}).\n\n"
        '## Período\n'
        f"{etiqueta[0].upper() + etiqueta[1:]} "
        f"(del {fecha_corta(datos['periodo']['desde'])} al {fecha_corta(datos['periodo']['hasta'])}).\n"
    )


def _frase_asistencia(datos):
    n, a = datos['asistencia']['sesiones'], datos['asistencia']['ausencias']
    if n == 0 and a == 0:
        return 'No se registraron sesiones en el período.'
    partes = []
    if n:
        partes.append(f"{n} sesión realizada" if n == 1 else f"{n} sesiones realizadas")
    if a:
        partes.append(f"{a} ausencia" if a == 1 else f"{a} ausencias")
    # Verbo concordado con lo que se cuenta: "Se registró 1 ausencia" pero
    # "Se registraron 22 sesiones realizadas y 1 ausencia".
    verbo = 'Se registró' if (n + a) == 1 else 'Se registraron'
    return f"{verbo} " + ' y '.join(partes) + ' en el período.'


_TEXTO_TENDENCIA = {'mejora': 'tendencia de mejora', 'se_mantiene': 'se mantiene estable', 'retrocede': 'requiere atención por un retroceso'}
_TEXTO_CAMBIO = {'mejoro': 'mejoró respecto del período anterior', 'igual': 'sin cambios respecto del período anterior', 'retrocedio': 'retrocedió respecto del período anterior'}


def _linea_objetivo(o, con_comparacion):
    if o['calificaciones'] == 0 or o['nivel'] is None:
        return f"- {o['descripcion']}: no se calificó en el período."
    veces = 'una sesión' if o['calificaciones'] == 1 else f"{o['calificaciones']} sesiones"
    linea = f"- {o['descripcion']}: {o['nivel']} (calificado en {veces})"
    extras = []
    if _TEXTO_TENDENCIA.get(o['tendencia']):
        extras.append(_TEXTO_TENDENCIA[o['tendencia']])
    if con_comparacion and _TEXTO_CAMBIO.get(o['cambio']):
        extras.append(_TEXTO_CAMBIO[o['cambio']])
    if extras:
        linea += '; ' + '; '.join(extras)
    return linea + '.'


def _observaciones(datos):
    """Observaciones de evolucion y renglones destacados, en orden de fecha."""
    salida = []
    for d in datos['diarios']:
        fecha = dt.date.fromisoformat(d['fecha']).strftime('%d/%m')
        for o in d['objetivos']:
            if o['observaciones']:
                salida.append(f"- {fecha}: {_recortar(o['observaciones'])}")
        for r in d['registro']:
            if r['destacado']:
                salida.append(f"- {fecha}: {_recortar(r['texto'])}")
    return salida


def redactar_plantilla(datos):
    """Informe mensual o semestral armado solo con los datos del periodo."""
    tipo = datos['tipo']
    etiqueta = etiqueta_periodo(tipo, datos.get('clave', ''))
    partes = [_encabezado(datos, etiqueta)]
    partes.append('## Asistencia\n' + _frase_asistencia(datos) + '\n')

    objetivos = [o for o in datos['objetivos'] if o['activo'] or o['calificaciones'] > 0]
    if objetivos:
        lineas = [_linea_objetivo(o, con_comparacion=(tipo == 'semestral')) for o in objetivos]
        partes.append('## Objetivos trabajados\n' + '\n'.join(lineas) + '\n')
    else:
        partes.append('## Objetivos trabajados\nNo hay objetivos con actividad en el período.\n')

    observaciones = _observaciones(datos)
    if observaciones:
        mostradas = observaciones[:MAXIMO_OBSERVACIONES_PLANTILLA]
        extra = len(observaciones) - len(mostradas)
        cuerpo = '\n'.join(mostradas)
        if extra > 0:
            cuerpo += f'\n- (Hay {extra} observaciones más en los diarios del período.)'
        partes.append('## Observaciones de las sesiones\n' + cuerpo + '\n')
    else:
        partes.append('## Observaciones de las sesiones\nNo hay observaciones registradas en el período.\n')

    cierre = 'Evolución general del semestre y proyección para el próximo' if tipo == 'semestral' else 'Cierre del período y próximos pasos'
    partes.append(f'## Cierre y próximos pasos\n{MARCA_COMPLETAR}: {cierre.lower()}]\n')
    return '\n'.join(partes).strip() + '\n'


def redactar_pti(datos):
    """PTI de ingreso: vuelca lo respondido en las etapas del ingreso."""
    ingreso = datos['pti']
    p = datos['paciente']
    partes = [
        '## Datos del paciente\n'
        f"{p['nombre_completo']}, {p['edad']} (nacimiento: {fecha_corta(p['fecha_nacimiento'])}).\n",
        '## Ingreso\n'
        f"Ingreso iniciado el {fecha_corta(datos['periodo']['desde'])}.\n",
    ]
    hay_contenido = False
    for etapa in ingreso['etapas']:
        if etapa['etapa'] not in ('evaluacion', 'entrevista', 'pti'):
            continue
        lineas = [f"- {c['etiqueta']}: {_recortar(c['valor'], 700)}" for c in etapa['campos'] if c.get('valor')]
        if lineas:
            hay_contenido = True
            partes.append(f"## {etapa['nombre']}\n" + '\n'.join(lineas) + '\n')
    if not hay_contenido:
        partes.append('## Plan terapéutico\n' + MARCA_COMPLETAR + ': todavía no hay respuestas cargadas en las etapas del ingreso]\n')
    objetivos = ingreso.get('objetivos') or []
    if objetivos:
        partes.append('## Objetivos iniciales\n' + '\n'.join(f'- {o}' for o in objetivos) + '\n')
    partes.append(f'## Coordinación y revisión\n{MARCA_COMPLETAR}: frecuencia, coordinación con otros profesionales y fecha de revisión]\n')
    return '\n'.join(partes).strip() + '\n'


# ---------------------------------------------------------------------------
# IA (opcional)
# ---------------------------------------------------------------------------
INSTRUCCIONES_IA = (
    'Usted redacta BORRADORES de informes de terapia ocupacional que una profesional va a revisar '
    'y firmar. Escriba en español, en tercera persona y con registro formal y clínico.\n'
    'Reglas estrictas:\n'
    '- Use únicamente los datos entregados. No invente hechos, fechas, diagnósticos ni recomendaciones.\n'
    '- Refiérase a la persona como "el paciente". Nunca escriba nombres propios.\n'
    '- Comunique la evolución solo con las palabras de la escala (No logrado, Inicial, En proceso, '
    'Avanzado, Logrado). No use números, porcentajes ni promedios de calificaciones.\n'
    '- No incluya datos de identificación ni encabezado: ya los agrega el sistema.\n'
    '- Estructure con encabezados de la forma "## Título" y listas con "- ".\n'
    '- Donde falte información para una sección, escriba "[COMPLETAR: qué falta]" en lugar de inventarla.\n'
    '- Termine con una sección "## Cierre y próximos pasos" que solo contenga una marca [COMPLETAR: ...] '
    'si los datos no alcanzan para proponer los pasos.'
)


class ProveedorIA:
    """Interfaz del proveedor. Un proveedor nuevo implementa `redactar`."""
    nombre = ''

    def redactar(self, instrucciones, datos_json):
        raise NotImplementedError


class ProveedorAnthropic(ProveedorIA):
    """Mensajes de Anthropic por HTTPS, sin dependencia extra."""

    def __init__(self, clave, modelo, timeout):
        self.clave = clave
        self.modelo = modelo
        self.timeout = timeout
        self.nombre = f'anthropic:{modelo}'

    def redactar(self, instrucciones, datos_json):
        cuerpo = json.dumps({
            'model': self.modelo,
            'max_tokens': 3000,
            'system': instrucciones,
            'messages': [{'role': 'user', 'content': 'Datos del período (JSON):\n' + datos_json}],
        }).encode('utf-8')
        pedido = urllib.request.Request(
            'https://api.anthropic.com/v1/messages', data=cuerpo, method='POST',
            headers={
                'content-type': 'application/json',
                'x-api-key': self.clave,
                'anthropic-version': '2023-06-01',
            },
        )
        with urllib.request.urlopen(pedido, timeout=self.timeout) as respuesta:
            datos = json.loads(respuesta.read().decode('utf-8'))
        bloques = [b.get('text', '') for b in datos.get('content', []) if b.get('type') == 'text']
        return '\n'.join(bloques).strip()


def obtener_proveedor():
    """Proveedor configurado en el .env, o None si la IA esta apagada."""
    config = current_app.config
    proveedor = config.get('INFORMES_IA_PROVEEDOR') or ''
    clave = config.get('INFORMES_IA_API_KEY') or ''
    if proveedor == 'anthropic' and clave:
        return ProveedorAnthropic(clave, config.get('INFORMES_IA_MODELO') or 'claude-sonnet-5-5',
                                  config.get('INFORMES_IA_TIMEOUT') or 60)
    return None


def ia_disponible():
    return obtener_proveedor() is not None


_VARIANTES = {
    'a': 'aáàäâ', 'e': 'eéèëê', 'i': 'iíìïî', 'o': 'oóòöô', 'u': 'uúùüû', 'n': 'nñ',
}


def _patron_nombre(nombre):
    """
    Patron del nombre como PALABRA ENTERA y sin distinguir tildes.

    Sin los limites de palabra, "Ana" se comia el "ana" de "semana" y "Paz" el
    de "capaz": la IA recibia texto roto. Sin las variantes, "Lucia" (como esta
    cargado) no tapaba "Lucía" (como lo escribe la terapeuta) y el nombre
    viajaba igual.
    """
    sin_tildes = unicodedata.normalize('NFKD', nombre).encode('ascii', 'ignore').decode().lower()
    partes = [f'[{_VARIANTES[c]}]' if c in _VARIANTES else re.escape(c) for c in sin_tildes]
    return re.compile(r'(?<!\w)' + ''.join(partes) + r'(?!\w)', re.IGNORECASE)


def _sin_nombre(valor, nombres):
    """Reemplaza el nombre y el apellido del paciente por 'el paciente'."""
    if isinstance(valor, str):
        for nombre in nombres:
            if nombre and len(nombre) >= 3:
                valor = _patron_nombre(nombre).sub('el paciente', valor)
        return valor
    if isinstance(valor, list):
        return [_sin_nombre(v, nombres) for v in valor]
    if isinstance(valor, dict):
        return {k: _sin_nombre(v, nombres) for k, v in valor.items()}
    return valor


def datos_para_ia(datos):
    """Los datos del periodo sin identificacion del paciente, serializables."""
    p = datos['paciente']
    nombres = [p['nombre'], p['apellido']]
    nombres += [parte for parte in f"{p['nombre']} {p['apellido']}".split() if len(parte) >= 3]
    bruto = {
        'tipo_de_informe': datos['tipo'],
        'edad_del_paciente': p['edad'],
        'periodo': {'desde': datos['periodo']['desde'].isoformat(), 'hasta': datos['periodo']['hasta'].isoformat()},
        'asistencia': datos['asistencia'],
        'objetivos': datos['objetivos'],
        'diarios': datos['diarios'],
        'ingreso': datos.get('pti'),
    }
    return _sin_nombre(bruto, nombres)


def _redactar_con_ia(proveedor, datos, cabecera):
    cuerpo = proveedor.redactar(INSTRUCCIONES_IA, json.dumps(datos_para_ia(datos), ensure_ascii=False))
    if not cuerpo or '## ' not in cuerpo:
        raise ValueError('La respuesta de la IA no tiene la estructura esperada')
    if len(cuerpo) > 50000:
        raise ValueError('La respuesta de la IA es demasiado larga')
    return cabecera.rstrip() + '\n\n' + cuerpo.strip() + '\n'


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------
def generar_contenido(datos, usar_ia=True):
    """
    Devuelve (contenido, generado_con, proveedor, advertencia).

    `generado_con` es 'ia' solo si la IA redacto de verdad. Si se pidio IA y
    fallo, o no hay proveedor, vuelve la plantilla y `advertencia` lo dice.
    """
    datos['clave'] = datos.get('clave', '')
    es_pti = datos['tipo'] == 'pti'
    plantilla = redactar_pti(datos) if es_pti else redactar_plantilla(datos)

    if not usar_ia:
        return plantilla, 'plantilla', None, None
    proveedor = obtener_proveedor()
    if proveedor is None:
        return plantilla, 'plantilla', None, 'La IA no está configurada en este centro: el borrador se armó con la plantilla.'
    try:
        etiqueta = etiqueta_periodo(datos['tipo'], datos['clave'])
        cabecera = _encabezado(datos, etiqueta) if not es_pti else plantilla.split('## Ingreso')[0]
        return _redactar_con_ia(proveedor, datos, cabecera), 'ia', proveedor.nombre, None
    except (urllib.error.URLError, TimeoutError, ValueError, OSError, KeyError, json.JSONDecodeError) as fallo:
        logger.warning('La IA no pudo redactar el informe (%s): se usa la plantilla', type(fallo).__name__)
        return plantilla, 'plantilla', None, 'La IA no respondió: el borrador se armó con la plantilla.'

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
    completas = sum(1 for d in diarios if d['estado'] in ('completa', 'cortada') or (d['estado'] == 'incompleta' and d['objetivos']))
    ausencias = sum(1 for d in diarios if d['estado'] == 'ausencia')
    # Ya ocurridas pero sin nada cargado: no se sabe si asistio. El borrador
    # lo marca para que la terapeuta lo resuelva antes de publicar.
    sin_registrar = sum(
        1 for d in diarios
        if d['estado'] == 'incompleta' and not d['objetivos'] and not d['registro']
        and d['fecha'] < dt.date.today().isoformat()
    )
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
        'asistencia': {'sesiones': completas, 'ausencias': ausencias, 'sin_registrar': sin_registrar},
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
    pendientes = datos['asistencia'].get('sin_registrar', 0)
    if n == 0 and a == 0:
        frase = 'No se registraron sesiones en el período.'
    else:
        # «Asistió a» y no «sesiones realizadas»: el control mensual cuenta
        # lo mismo y la familia no distingue cerradas de en registro.
        partes = []
        if n:
            partes.append('asistió a 1 sesión' if n == 1 else f'asistió a {n} sesiones')
        if a:
            partes.append('faltó a 1' if a == 1 else f'faltó a {a}')
        frase = 'En el período ' + ' y '.join(partes) + '.'
    if pendientes:
        cuantas = 'hay 1 sesión' if pendientes == 1 else f'hay {pendientes} sesiones'
        frase += f'\n\n{MARCA_COMPLETAR}: {cuantas} del período sin registrar; regístrelas o ajuste la asistencia]'
    return frase


_TEXTO_TENDENCIA = {'mejora': 'tendencia de mejora', 'se_mantiene': 'se mantiene estable', 'retrocede': 'requiere atención por un retroceso'}
_TEXTO_CAMBIO = {'mejoro': 'mejoró respecto del período anterior', 'igual': 'sin cambios respecto del período anterior', 'retrocedio': 'retrocedió respecto del período anterior'}


def _linea_objetivo(o, con_comparacion):
    if o['calificaciones'] == 0 or o['nivel'] is None:
        return f"- {o['descripcion'].rstrip('. ')}: no se calificó en el período."
    veces = 'una sesión' if o['calificaciones'] == 1 else f"{o['calificaciones']} sesiones"
    linea = f"- {o['descripcion'].rstrip('. ')}: {o['nivel']} (calificado en {veces})"
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


def _seccion_asistencia(datos):
    return '## Asistencia\n' + _frase_asistencia(datos) + '\n'


def _seccion_objetivos(datos):
    """Objetivos con su nivel en palabras. Siempre lo arma el codigo, nunca la IA."""
    objetivos = [o for o in datos['objetivos'] if o['activo'] or o['calificaciones'] > 0]
    if not objetivos:
        return '## Objetivos trabajados\nNo hay objetivos con actividad en el período.\n'
    lineas = [_linea_objetivo(o, con_comparacion=(datos['tipo'] == 'semestral')) for o in objetivos]
    # Franco: no se sabia si el nivel era la ultima calificacion o un resumen.
    aclaracion = ('El nivel de cada objetivo resume todas sus calificaciones del período; '
                  'no es la última calificación.')
    return '## Objetivos trabajados\n' + aclaracion + '\n\n' + '\n'.join(lineas) + '\n'


def _seccion_cierre(datos):
    """Los próximos pasos los decide la profesional: el sistema deja la marca."""
    cierre = ('Evolución general del semestre y proyección para el próximo' if datos['tipo'] == 'semestral'
              else 'Cierre del período y próximos pasos')
    return f'## Cierre y próximos pasos\n{MARCA_COMPLETAR}: {cierre.lower()}]\n'


def redactar_plantilla(datos):
    """Informe mensual o semestral armado solo con los datos del periodo."""
    tipo = datos['tipo']
    etiqueta = etiqueta_periodo(tipo, datos.get('clave', ''))
    partes = [_encabezado(datos, etiqueta), _seccion_asistencia(datos), _seccion_objetivos(datos)]

    observaciones = _observaciones(datos)
    if observaciones:
        mostradas = observaciones[:MAXIMO_OBSERVACIONES_PLANTILLA]
        extra = len(observaciones) - len(mostradas)
        cuerpo = '\n'.join(mostradas)
        if extra > 0:
            # Marca y no texto suelto: antes llegaba a la familia «(Hay 1
            # observaciones más en los diarios...)» (usabilidad, terapeuta).
            cuantas = 'queda 1 observación' if extra == 1 else f'quedan {extra} observaciones'
            cuerpo += f'\n\n{MARCA_COMPLETAR}: {cuantas} más en los diarios del período; incorpore lo que corresponda]'
        partes.append('## Observaciones de las sesiones\n' + cuerpo + '\n')
    else:
        partes.append('## Observaciones de las sesiones\nNo hay observaciones registradas en el período.\n')

    partes.append(_seccion_cierre(datos))
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
    '- Escriba SIEMPRE y exclusivamente en español rioplatense formal. Nunca use otro idioma ni otro alfabeto.\n'
    '- Use únicamente los datos entregados. No invente hechos, fechas, diagnósticos ni recomendaciones.\n'
    '- Refiérase a la persona como "el paciente". Nunca escriba nombres propios.\n'
    '- Comunique la evolución solo con las palabras de la escala (No logrado, Inicial, En proceso, '
    'Avanzado, Logrado). No use números, porcentajes ni promedios de calificaciones.\n'
    '- No incluya datos de identificación ni encabezado: ya los agrega el sistema.\n'
    '- Donde falte información, escriba "[COMPLETAR: qué falta]" en lugar de inventarla.\n'
    '- Formato: texto plano. Los títulos son líneas que empiezan con "## ". No use asteriscos, '
    'negritas, cursivas, tablas ni otros símbolos de formato.\n'
)

_INSTRUCCIONES_PERIODICO = (
    'El sistema YA incluye la asistencia, la lista de objetivos con su nivel y el cierre: no los repita '
    'ni enumere las sesiones una por una. Usted recibe solo las observaciones del equipo y la tendencia '
    'de cada objetivo.\n'
    'Redacte SOLO esta sección:\n'
    '## Evolución del período\n'
    'Exactamente {parrafos} párrafos de prosa corrida, de hasta 4 oraciones cada uno, sin listas:\n'
    '{guia}'
    'Reglas del texto:\n'
    '- Cada párrafo aporta ideas nuevas: no repita lo ya dicho ni cierre con una conclusión general.\n'
    '- Cuente solo lo que dicen los datos. No explique causas, no relacione objetivos entre sí y no '
    'proponga estrategias ni actividades nuevas: eso lo decide la profesional.\n'
    '- No mencione fechas, días, cantidades de sesiones ni niveles: ya figuran en otras secciones.\n'
    '- Si los datos no alcanzan para un párrafo, escriba en su lugar [COMPLETAR: qué falta].\n'
)

_GUIA_MENSUAL = (
    '1) qué se trabajó y la disposición del paciente; '
    '2) qué apoyos necesitó y qué dificultades aparecieron; '
    '3) qué cambió, según la tendencia de cada objetivo.\n'
)
_GUIA_SEMESTRAL = (
    '1) qué se trabajó en el semestre y la disposición del paciente; '
    '2) qué apoyos necesitó y qué dificultades aparecieron; '
    '3) qué cambió respecto del período anterior, según la tendencia de cada objetivo; '
    '4) los aspectos que conviene sostener o vigilar, solo si las observaciones lo indican.\n'
)

_INSTRUCCIONES_PTI = (
    'Sea conciso: máximo 600 palabras. Estructure con secciones "## Título" y listas con "- ". '
    'Termine con "## Cierre y próximos pasos", que solo contenga una marca [COMPLETAR: ...] '
    'si los datos no alcanzan para proponerlos.'
)


def instrucciones_ia(tipo):
    """Reglas comunes más las del tipo de informe."""
    if tipo == 'pti':
        return INSTRUCCIONES_IA + _INSTRUCCIONES_PTI
    semestral = tipo == 'semestral'
    return INSTRUCCIONES_IA + _INSTRUCCIONES_PERIODICO.format(
        parrafos=4 if semestral else 3,
        guia=_GUIA_SEMESTRAL if semestral else _GUIA_MENSUAL,
    )


class ProveedorIA:
    """Interfaz del proveedor. Un proveedor nuevo implementa `redactar`."""
    nombre = ''
    local = False

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


class ProveedorOllama(ProveedorIA):
    """
    Modelo local servido por Ollama. No hay clave ni salida a internet: los
    datos del periodo no abandonan la maquina. Es mas lento que un proveedor
    en la nube (depende del equipo), por eso conviene un INFORMES_IA_TIMEOUT
    alto en el .env.
    """
    local = True

    def __init__(self, url, modelo, timeout, ctx=8192, keep_alive='30m'):
        self.url = url
        self.modelo = modelo
        self.timeout = timeout
        self.ctx = ctx
        self.keep_alive = keep_alive
        self.nombre = f'ollama:{modelo}'
        self.ultima_medicion = None

    def redactar(self, instrucciones, datos_json):
        cuerpo = json.dumps({
            'model': self.modelo,
            'stream': False,
            'keep_alive': self.keep_alive,
            'messages': [
                {'role': 'system', 'content': instrucciones},
                {'role': 'user', 'content': 'Datos del período (JSON):\n' + datos_json},
            ],
            'options': {'temperature': 0.2, 'num_predict': 2000, 'num_ctx': self.ctx},
        }).encode('utf-8')
        pedido = urllib.request.Request(
            f'{self.url}/api/chat', data=cuerpo, method='POST',
            headers={'content-type': 'application/json'},
        )
        with urllib.request.urlopen(pedido, timeout=self.timeout) as respuesta:
            datos = json.loads(respuesta.read().decode('utf-8'))
        self._registrar_medicion(datos)
        return (datos.get('message') or {}).get('content', '').strip()

    def _registrar_medicion(self, datos):
        """Deja en el log cuanto tardo cada etapa, para saber que optimizar."""
        seg = lambda ns: round((ns or 0) / 1e9, 1)
        entrada, salida = datos.get('prompt_eval_count') or 0, datos.get('eval_count') or 0
        t_salida = seg(datos.get('eval_duration'))
        medicion = {
            'total_s': seg(datos.get('total_duration')),
            'carga_modelo_s': seg(datos.get('load_duration')),
            'entrada_tokens': entrada, 'entrada_s': seg(datos.get('prompt_eval_duration')),
            'salida_tokens': salida, 'salida_s': t_salida,
            'tokens_por_s': round(salida / t_salida, 1) if t_salida else None,
        }
        self.ultima_medicion = medicion
        logger.info('IA local (%s): %s', self.modelo, medicion)
        if entrada + salida >= self.ctx - 64:
            logger.warning('IA local: el texto llego al limite de contexto (%s tokens); Ollama puede '
                           'haber recortado el principio. Subir INFORMES_IA_CTX o achicar el periodo.', self.ctx)


def obtener_proveedor():
    """Proveedor configurado en el .env, o None si la IA esta apagada."""
    config = current_app.config
    proveedor = config.get('INFORMES_IA_PROVEEDOR') or ''
    clave = config.get('INFORMES_IA_API_KEY') or ''
    modelo = config.get('INFORMES_IA_MODELO') or ''
    timeout = config.get('INFORMES_IA_TIMEOUT') or 60
    if proveedor == 'anthropic' and clave:
        return ProveedorAnthropic(clave, modelo or 'claude-sonnet-5-5', timeout)
    if proveedor == 'ollama' and modelo:
        return ProveedorOllama(config.get('INFORMES_IA_URL') or 'http://127.0.0.1:11434', modelo, timeout,
                               config.get('INFORMES_IA_CTX') or 8192, config.get('INFORMES_IA_KEEP_ALIVE') or '30m')
    return None


def ia_disponible():
    return obtener_proveedor() is not None


def ia_local():
    """True si el proveedor corre en esta maquina y no manda nada afuera."""
    proveedor = obtener_proveedor()
    return bool(proveedor and getattr(proveedor, 'local', False))


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


# Claves que no aportan a la redaccion: identificadores internos y la hora exacta.
_CLAVES_SIN_VALOR_PARA_IA = {'id', 'id_sesion', 'id_objetivo', 'hora_inicio'}


def _compactar(valor, clave=None):
    """
    Saca de lo que viaja a la IA lo que no cambia el texto del informe: ids,
    claves vacias y valores de relleno ("sin_datos", 0 calificaciones previas,
    objetivo activo). En un modelo local la entrada se procesa en CPU y cada
    token cuesta, asi que achicarla es lo que mas acelera.
    """
    if isinstance(valor, dict):
        salida = {}
        for k, x in valor.items():
            if k in _CLAVES_SIN_VALOR_PARA_IA:
                continue
            x = _compactar(x, k)
            if x in (None, '', [], {}):
                continue
            if k in ('tendencia', 'cambio') and x == 'sin_datos':
                continue
            if k == 'calificaciones_anterior' and x == 0:
                continue
            if k == 'activo' and x is True:
                continue
            salida[k] = x
        return salida
    if isinstance(valor, list):
        return [x for x in (_compactar(i) for i in valor) if x not in (None, '', [], {})]
    return valor


MAXIMO_OBSERVACIONES_IA = 30


def _observaciones_para_ia(datos):
    """
    Lo cualitativo que registro el equipo, sin fechas ni niveles: notas de la
    sesion, renglones destacados y observaciones por objetivo. Las fechas, los
    niveles y los conteos los muestra el sistema en otras secciones; si el
    modelo los recibe, los mezcla y los cuenta mal.
    """
    textos = []
    for d in datos['diarios']:
        if d['estado'] == 'ausencia':
            continue
        if d['nota']:
            textos.append(_recortar(d['nota'], 220))
        textos += [_recortar(r['texto'], 220) for r in d['registro'] if r['destacado']]
        textos += [_recortar(f"{_recortar(o['objetivo'], 70)}: {o['observaciones']}", 260) for o in d['objetivos'] if o['observaciones']]
    vistos, unicos = set(), []
    for t in textos:
        if t and t not in vistos:
            vistos.add(t)
            unicos.append(t)
    return unicos[:MAXIMO_OBSERVACIONES_IA]


def datos_para_ia(datos):
    """Los datos del periodo sin identificacion del paciente, serializables."""
    p = datos['paciente']
    nombres = [p['nombre'], p['apellido']]
    nombres += [parte for parte in f"{p['nombre']} {p['apellido']}".split() if len(parte) >= 3]
    if datos['tipo'] != 'pti':
        semestral = datos['tipo'] == 'semestral'
        bruto = {
            'tipo_de_informe': datos['tipo'],
            'edad_del_paciente': p['edad'],
            'objetivos': [
                {
                    'objetivo': _recortar(o['descripcion'], 160),
                    'tendencia': _TEXTO_TENDENCIA.get(o['tendencia']),
                    **({'respecto_del_periodo_anterior': _TEXTO_CAMBIO.get(o['cambio'])} if semestral else {}),
                }
                for o in datos['objetivos'] if o['calificaciones'] > 0
            ],
            'observaciones_del_equipo': _observaciones_para_ia(datos),
        }
        return _compactar(_sin_nombre(bruto, nombres))
    bruto = {
        'tipo_de_informe': datos['tipo'],
        'edad_del_paciente': p['edad'],
        'periodo': {'desde': datos['periodo']['desde'].isoformat(), 'hasta': datos['periodo']['hasta'].isoformat()},
        'asistencia': datos['asistencia'],
        'objetivos': datos['objetivos'],
        'diarios': datos['diarios'],
        'ingreso': datos.get('pti'),
    }
    return _compactar(_sin_nombre(bruto, nombres))


# Ideogramas CJK, kana y hangul: en un informe en español nunca corresponden.
_OTRO_ALFABETO = re.compile('[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uac00-\ud7af\uff00-\uffef]')


def _limpiar_formato(cuerpo):
    """
    Los modelos chicos escriben Markdown aunque se les pida texto plano y la
    pantalla solo entiende "## ", "- " y parrafos. Se normaliza aca: titulos a
    "## ", vinetas a "- " y sin negritas, cursivas ni codigo.
    """
    salida = []
    for linea in cuerpo.replace('\r\n', '\n').split('\n'):
        linea = linea.rstrip()
        titulo = re.match(r'^\s*#{1,6}\s+(.*)$', linea)
        if titulo:
            linea = '## ' + titulo.group(1)
        else:
            linea = re.sub(r'^\s*(?:[*•]|-)\s+', '- ', linea)
        linea = re.sub(r'\*\*|__|`', '', linea)
        linea = re.sub(r'(?<![\w*])\*([^*\n]+)\*(?![\w*])', r'\1', linea)
        if linea.startswith('## '):
            linea = linea.rstrip(' :*')
        salida.append(linea)
    return re.sub(r'\n{3,}', '\n\n', '\n'.join(salida)).strip()


# Secciones que ya arma el codigo: si el modelo las repite, se descartan.
_SECCIONES_DEL_SISTEMA = ('datos del paciente', 'periodo', 'asistencia', 'objetivos', 'diario', 'sesiones', 'cierre')


def _sin_secciones_del_sistema(cuerpo):
    conservadas = []
    for parte in re.split(r'(?m)^(?=## )', cuerpo):
        if not parte.startswith('## '):
            continue  # texto suelto antes del primer titulo («Aqui esta el informe:»)
        titulo = parte.split('\n', 1)[0][3:]
        titulo = unicodedata.normalize('NFD', titulo.lower())
        titulo = ''.join(c for c in titulo if unicodedata.category(c) != 'Mn').strip()
        if not titulo.startswith(_SECCIONES_DEL_SISTEMA):
            conservadas.append(parte.strip())
    return '\n\n'.join(conservadas)


def _redactar_con_ia(proveedor, datos, cabecera):
    cuerpo = proveedor.redactar(
        instrucciones_ia(datos['tipo']),
        json.dumps(datos_para_ia(datos), ensure_ascii=False, separators=(',', ':')),
    )
    if not cuerpo or '## ' not in cuerpo:
        raise ValueError('La respuesta de la IA no tiene la estructura esperada')
    if len(cuerpo) > 50000:
        raise ValueError('La respuesta de la IA es demasiado larga')
    if _OTRO_ALFABETO.search(cuerpo):
        # Algunos modelos locales se pasan al chino/japonés/coreano a mitad de texto.
        raise ValueError('La respuesta de la IA mezcla otro idioma')
    cuerpo = _limpiar_formato(cuerpo)
    if datos['tipo'] == 'pti':
        return cabecera.rstrip() + '\n\n' + cuerpo + '\n'
    # Mensual y semestral: los hechos (asistencia, objetivos y niveles) los arma
    # el codigo y la IA solo redacta la evolucion y el cierre. Asi no hay
    # listas de sesiones repetidas ni niveles inventados.
    cuerpo = _sin_secciones_del_sistema(cuerpo)
    if not cuerpo:
        raise ValueError('La respuesta de la IA no tiene la estructura esperada')
    return '\n'.join([cabecera.rstrip() + '\n', _seccion_asistencia(datos), _seccion_objetivos(datos), cuerpo + '\n', _seccion_cierre(datos)])


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

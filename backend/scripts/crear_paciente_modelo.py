"""
backend/scripts/crear_paciente_modelo.py

Crea el paciente "modelo" de la demostracion: Mateo Gómez, asignado a Laura
Fernández, con el legajo COMPLETO para mostrar como queda un caso bien llevado.

  - Alta, asignacion vigente desde el 02/03/2026 y una cuenta de familiar.
  - Ingreso con las 4 etapas cerradas, 4 objetivos activos e historia clinica.
  - Dos sesiones por semana (lunes y jueves, 12:00) hasta el 22/10/2026, con
    ausencias, sesiones incompletas y evolucion por objetivo.
  - Informes mensuales publicados de marzo a septiembre, el semestral del
    primer semestre y el PTI, todos revisados y publicados.
  - Octubre queda SIN informe a proposito: sirve para generar uno en vivo
    (con la plantilla o con la IA local).

No existe un informe "trimestral" en AsisTO (los tipos son mensual,
semestral y PTI): el cierre de periodo largo es el semestral.

Todo se carga por la API real (con el cliente de pruebas de Flask), asi que
corren los mismos triggers y procedimientos que en uso normal. Lo unico que
se toca por SQL son las FECHAS, para que el historial quede repartido en el
tiempo en vez de fechado hoy.

Uso (desde backend/, con el venv activo, backend apagado o prendido):

    python scripts/crear_paciente_modelo.py
    python scripts/crear_paciente_modelo.py --email laura.fernandez@asisto.local --contrasena asisto2026

La contrasena se usa para Laura y para el administrador (en el seed demo es la misma).

Es idempotente en el sentido seguro: si "Mateo Gómez" ya existe no hace nada.
Para volver a crearlo hay que dar de baja o borrar al paciente a mano.
"""

import argparse
import datetime as dt
import os
import random
import re
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import text  # noqa: E402

from app import create_app, db  # noqa: E402
from app.services.pacientes_service import siguiente_nro_historia  # noqa: E402
from app.utils.security import hashear_contrasena  # noqa: E402

INICIO = dt.date(2026, 3, 2)               # alta y primera asignacion
OBJETIVOS_DESDE = dt.date(2026, 3, 13)     # el ingreso termina y se fijan los objetivos
PRIMERA_SESION = dt.date(2026, 3, 16)
ULTIMA_SESION = dt.date(2026, 10, 22)
HORA = ('12:00:00', '13:00:00')
FERIADOS = {dt.date(2026, 3, 23), dt.date(2026, 4, 2), dt.date(2026, 5, 25), dt.date(2026, 6, 15),
            dt.date(2026, 7, 9), dt.date(2026, 8, 17), dt.date(2026, 10, 12)}
CONTRASENA_FAMILIAR = 'asisto2026'
EMAIL_FAMILIAR = 'silvana.paredes@asisto.local'

PACIENTE = {
    'nombre': 'Mateo',
    'apellido': 'Gómez',
    'fecha_nacimiento': '2016-05-14',
    'diagnostico': 'Dificultades de autorregulación emocional y de motricidad fina. '
                   'Trastorno del procesamiento sensorial.',
}

OBJETIVOS = [
    'Sostener el lápiz con pinza trípode y mantener el trazo dentro del renglón al copiar '
    'oraciones cortas, con apoyo verbal intermitente.',
    'Reconocer sus emociones y usar estrategias de autorregulación (respiración, pausa sensorial) '
    'ante la frustración, con apoyo visual.',
    'Abrocharse botones y atarse los cordones de forma independiente durante la rutina de vestido.',
    'Sostener turnos y respetar reglas en juegos compartidos, aceptando perder sin conductas de oposición.',
]

# Nivel promedio por mes (1 a 5) de cada objetivo. Cuenta la historia del caso:
# la autorregulacion retrocede en junio (cierre de evaluaciones en la escuela) y
# se recupera; vida diaria es lo que mas avanza.
TRAYECTORIA = {
    3: (1.3, 1.2, 2.0, 1.0),
    4: (1.8, 1.6, 2.6, 1.4),
    5: (2.3, 2.0, 3.2, 1.8),
    6: (2.5, 1.7, 3.8, 2.2),
    7: (3.0, 2.4, 4.2, 2.4),
    8: (3.4, 3.0, 4.5, 2.9),
    9: (3.8, 3.5, 4.8, 3.3),
    10: (4.1, 3.8, 5.0, 3.6),
}

# Fechas con algo distinto de una sesion completa (el resto son completas).
ESTADOS_ESPECIALES = {
    dt.date(2026, 4, 13): ('ausencia', 'paciente'),
    dt.date(2026, 4, 27): ('incompleta', None),
    dt.date(2026, 5, 7): ('ausencia', 'paciente'),
    dt.date(2026, 5, 14): ('cortada', None),
    dt.date(2026, 6, 4): ('incompleta', None),
    dt.date(2026, 6, 18): ('ausencia', 'paciente'),
    dt.date(2026, 7, 2): ('ausencia', 'terapeuta'),
    dt.date(2026, 8, 3): ('ausencia', 'paciente'),
    dt.date(2026, 8, 24): ('cortada', None),
    dt.date(2026, 9, 10): ('ausencia', 'paciente'),
    dt.date(2026, 9, 21): ('incompleta', None),
}

# Observaciones por objetivo y franja de nivel: (1-2, 3, 4-5)
OBSERVACIONES = [
    (  # escritura
        ['Sostiene el lápiz con agarre palmar; hubo que recordarle la posición de los dedos varias veces.',
         'Trazo irregular y con mucha presión; se fatigó a los pocos minutos de escribir.',
         'Necesitó apoyo manual para ubicar los dedos y copió solo dos palabras.'],
        ['Alterna entre pinza trípode y agarre inmaduro; mejora cuando se le da una guía de posición.',
         'Mantiene el trazo en el renglón en palabras cortas y lo pierde en las más largas.',
         'Copió una oración corta con pausas; la presión del lápiz fue más adecuada que en sesiones anteriores.'],
        ['Sostuvo la pinza trípode durante toda la actividad sin recordatorios.',
         'Copió una oración completa respetando el renglón y el tamaño de las letras.',
         'Trazo fluido y de tamaño regular; pidió una pausa antes de que apareciera la fatiga.'],
    ),
    (  # autorregulacion
        ['Ante el error se frustró y abandonó la tarea; necesitó acompañamiento para retomarla.',
         'Le costó calmarse después de un cambio de actividad; aceptó la respiración guiada solo con modelado.',
         'Hubo que nombrarle la emoción; no usó estrategias por iniciativa propia.'],
        ['Reconoció que estaba enojado y aceptó ir al rincón de pausa con una indicación.',
         'Usó la respiración profunda con apoyo verbal y volvió a la actividad en pocos minutos.',
         'Toleró un cambio de consigna anticipado con una imagen; mostró tensión al principio.'],
        ['Pidió una pausa por iniciativa propia al sentirse sobrepasado y retomó la tarea solo.',
         'Ante una dificultad probó dos estrategias de las practicadas antes de pedir ayuda.',
         'Aceptó el cambio de actividad sin oposición, apoyándose en la agenda visual.'],
    ),
    (  # vida diaria
        ['Abrochó dos botones grandes con ayuda; se frustró con los botones chicos.',
         'Necesitó apoyo manual para pasar el cordón por los ojales.',
         'Participó de la práctica de vestido solo con guía física de la terapeuta.'],
        ['Abrochó la camisa completa con tiempo extra y sin ayuda física.',
         'Logró hacer el primer nudo de los cordones; el segundo lazo requirió indicación.',
         'Resolvió los botones por su cuenta y pidió ayuda solo para el cierre del cuello.'],
        ['Se abrochó y desabrochó el guardapolvo solo, en un tiempo razonable.',
         'Se ató los cordones de las zapatillas de forma independiente.',
         'Hizo la secuencia completa de vestido con la agenda visual, sin ayuda del adulto.'],
    ),
    (  # juego y turnos
        ['Jugó en paralelo, sin intercambio; se retiró cuando tuvo que esperar su turno.',
         'Aceptó compartir el material solo con la mediación de la terapeuta.',
         'Reclamó el turno varias veces y le costó aceptar que el juego terminara.'],
        ['Esperó su turno en un juego de mesa con recordatorios; reclamó al perder una ronda.',
         'Propuso una regla y logró negociarla con apoyo.',
         'Sostuvo los turnos durante la mayor parte del juego; el apoyo fue puntual.'],
        ['Sostuvo los turnos durante todo el juego y celebró los puntos del compañero.',
         'Cooperó en una construcción en conjunto, repartiendo las tareas.',
         'Aceptó perder una ronda sin enojarse y propuso la revancha.'],
    ),
]
RETROCESO_AUTORREGULACION = [
    'Llegó muy inquieto por las evaluaciones de la escuela; hubo más episodios de frustración que en las semanas previas.',
    'Volvió a necesitar apoyo para calmarse; la familia cuenta que durmió poco esa semana.',
    'Le costó empezar la sesión y la primera parte se dedicó a la regulación sensorial antes de trabajar.',
]
NOTAS_AUSENCIA = {
    'paciente': ['La familia avisó que estaba con cuadro gripal.',
                 'Faltó por un acto escolar; la familia avisó con anticipación.',
                 'Faltó sin aviso previo; la familia se comunicó después.'],
    'terapeuta': ['La terapeuta no asistió por una capacitación del centro; se reprograma.'],
}

# ---------------------------------------------------------------------------
# Respuestas del ingreso
# ---------------------------------------------------------------------------
INGRESO = {
    'carpeta': {
        'fuente': 'Derivación de la escuela y de la pediatra de cabecera; carpeta aportada por la familia.',
        'antecedentes': 'Embarazo y parto sin complicaciones, a término. Marcha a los 13 meses y lenguaje '
                        'oral dentro de lo esperado. Sin internaciones ni intervenciones quirúrgicas.',
        'diagnosticos_previos': 'Informe de la pediatra (2025): dificultades de motricidad fina y de '
                                'autorregulación. Informe de la psicopedagoga de la escuela (2025): '
                                'esfuerzo marcado en la escritura manual.',
        'tratamientos_previos': 'Acompañamiento psicopedagógico en la escuela durante 2025.',
        'medicacion': 'No toma medicación.',
    },
    'evaluacion': {
        'fecha_evaluacion': '2026-03-04',
        'motivo_consulta': 'La escuela y la familia consultan por dificultad para escribir sin cansarse, '
                           'explosiones de enojo ante la frustración y demora en vestirse solo.',
        'vida_diaria': 'Se alimenta solo y controla esfínteres. Necesita ayuda para abrocharse botones y '
                       'no se ata los cordones. Se viste con apoyo verbal constante.',
        'motricidad': 'Agarre palmar del lápiz, presión excesiva y fatiga rápida. Coordinación visomotora '
                      'por debajo de lo esperado para la edad. Motricidad gruesa adecuada.',
        'procesamiento_sensorial': 'Busca estímulos propioceptivos y se desorganiza en ambientes ruidosos. '
                                   'Rechaza etiquetas en la ropa.',
        'atencion_conducta': 'Sostiene la atención unos diez minutos en tareas de mesa. Ante el error se '
                             'frustra y abandona la actividad; se calma con acompañamiento adulto.',
        'comunicacion_juego': 'Lenguaje fluido. Prefiere el juego de construcción; le cuesta esperar el '
                              'turno y aceptar perder.',
        'escolaridad': 'Cursa cuarto grado en escuela común, con buen rendimiento oral. Los docentes '
                       'señalan lentitud y cansancio en las tareas escritas.',
        'fortalezas': 'Buen vocabulario, curiosidad, motivación por las construcciones y los juegos de '
                      'estrategia. Vínculo afectuoso con los adultos.',
        'impresion': 'Cuadro compatible con dificultades de motricidad fina y de autorregulación emocional, '
                     'con componente sensorial. Se recomienda terapia ocupacional dos veces por semana.',
    },
    'entrevista': {
        'fecha_entrevista': '2026-03-06',
        'asistentes': 'Madre y padre.',
        'preocupaciones': 'Les preocupa que se frustre con facilidad, que la escritura le cueste tanto y '
                          'que se sienta distinto de sus compañeros.',
        'rutina': 'Se levanta a las 7, va a la escuela por la mañana, almuerza en casa y hace las tareas '
                  'con ayuda. Duerme alrededor de las 21:30.',
        'desarrollo': 'Hitos del desarrollo dentro de lo esperado. Desde pequeño es muy sensible a los '
                      'ruidos fuertes y a ciertas texturas.',
        'expectativas': 'Que pueda escribir con menos esfuerzo, calmarse solo y vestirse sin ayuda.',
        'otras_observaciones': 'La familia se muestra comprometida y dispuesta a practicar en casa las '
                               'estrategias que se indiquen.',
    },
    'pti': {
        'frecuencia': '2 veces por semana',
        'areas': 'Motricidad fina y escritura, autorregulación emocional, autonomía en la vida diaria y '
                 'juego con reglas. Los cuatro objetivos concretos se cargaron en la pestaña Objetivos.',
        'estrategias': 'Enfoque lúdico y apoyo visual. Pausas sensoriales planificadas, anticipación de '
                       'los cambios con agenda visual y práctica gradual de la secuencia de vestido.',
        'coordinacion': 'Reunión trimestral con la escuela para acordar adaptaciones de las tareas '
                        'escritas. Comunicación mensual con la familia a través de los informes.',
        'criterios_revision': 'Se revisan los objetivos cada seis meses o antes si alguno se logra. Se '
                              'da de alta un objetivo cuando se sostiene en distintos contextos.',
        'fecha_revision': '2026-09-14',
    },
}
CIERRE_ETAPA = {'carpeta': dt.date(2026, 3, 4), 'evaluacion': dt.date(2026, 3, 6),
                'entrevista': dt.date(2026, 3, 10), 'pti': dt.date(2026, 3, 13)}

from _textos_paciente_modelo import MENSUAL, PTI_COORDINACION, SEMESTRAL  # noqa: E402


class ErrorDeCarga(RuntimeError):
    pass


class Api:
    """Cliente de la API con el cliente de pruebas de Flask (sin levantar el backend)."""

    def __init__(self, app, email, contrasena):
        self.cliente = app.test_client(use_cookies=False)
        r = self.cliente.post('/api/auth/login', json={'email': email, 'contrasena': contrasena})
        if r.status_code != 200:
            raise ErrorDeCarga(f'No se pudo iniciar sesión como {email} ({r.status_code}). '
                               'Revisar --email y --contrasena.')
        self.cabeceras = {'Authorization': f"Bearer {r.get_json()['token']}"}

    def llamar(self, metodo, ruta, cuerpo=None, esperado=(200, 201)):
        r = getattr(self.cliente, metodo)(ruta, headers=self.cabeceras, json=cuerpo)
        if r.status_code not in esperado:
            raise ErrorDeCarga(f'{metodo.upper()} {ruta} -> {r.status_code}: {r.get_data(as_text=True)[:400]}')
        return r.get_json(silent=True)


def sql(consulta, **params):
    db.session.execute(text(consulta), params)
    db.session.commit()


def dias_de_sesion():
    d = PRIMERA_SESION
    while d <= ULTIMA_SESION:
        if d.weekday() in (0, 3) and d not in FERIADOS:   # lunes y jueves
            yield d
        d += dt.timedelta(days=1)


def nivel_de_la_sesion(rng, objetivo, fecha):
    """Valor 1-5 alrededor del promedio del mes, interpolando hacia el mes siguiente."""
    mes = fecha.month
    actual = TRAYECTORIA[mes][objetivo]
    siguiente = TRAYECTORIA.get(mes + 1, TRAYECTORIA[mes])[objetivo]
    avance = (fecha.day - 1) / 30
    media = actual + (siguiente - actual) * avance * 0.5
    return max(1, min(5, round(media + rng.uniform(-0.6, 0.6))))


def observacion(rng, objetivo, valor, fecha):
    if objetivo == 1 and fecha.month == 6 and valor <= 2 and rng.random() < 0.7:
        return rng.choice(RETROCESO_AUTORREGULACION)
    if rng.random() < 0.2:
        return None
    franja = 0 if valor <= 2 else (1 if valor == 3 else 2)
    return rng.choice(OBSERVACIONES[objetivo][franja])


def cargar_sesiones(api, id_paciente, ids_objetivos):
    rng = random.Random(2026)
    total = ausencias = 0
    for fecha in dias_de_sesion():
        estado, ausente = ESTADOS_ESPECIALES.get(fecha, ('completa', None))
        cuerpo = {'id_paciente': id_paciente, 'fecha': fecha.isoformat(), 'hora_inicio': HORA[0],
                  'hora_fin': HORA[1], 'estado': estado, 'ausencia_de': ausente,
                  'notas': rng.choice(NOTAS_AUSENCIA[ausente]) if ausente else None}
        sesion = api.llamar('post', '/api/sesiones', cuerpo)['sesion']
        total += 1
        if estado == 'ausencia':
            ausencias += 1
            continue
        evaluados = list(range(4))
        if estado in ('incompleta', 'cortada'):
            evaluados = sorted(rng.sample(range(4), 2 if estado == 'incompleta' else 1))
        for k in evaluados:
            valor = nivel_de_la_sesion(rng, k, fecha)
            api.llamar('post', '/api/evoluciones', {
                'id_sesion': sesion['id'], 'id_objetivo': ids_objetivos[k], 'valor': valor,
                'observaciones': observacion(rng, k, valor, fecha)})
    return total, ausencias


def cargar_ingreso(api, id_paciente):
    base = f'/api/pacientes/{id_paciente}/ingreso'
    api.llamar('post', base)
    ids = []
    for etapa, respuestas in INGRESO.items():
        api.llamar('put', f'{base}/etapas/{etapa}', {'respuestas': respuestas})
        api.llamar('post', f'{base}/etapas/{etapa}/cierre')
        if etapa == 'pti':
            # Los objetivos se fijan al cerrar el PTI y antes de completar el ingreso.
            for descripcion in OBJETIVOS:
                o = api.llamar('post', '/api/objetivos', {'id_paciente': id_paciente, 'descripcion': descripcion})
                ids.append(o['objetivo']['id'])
    api.llamar('post', f'{base}/completado')
    return ids


def fechar_ingreso(id_paciente, ids_objetivos):
    sql('UPDATE pacientes SET fecha_alta = :d WHERE id = :p', d=INICIO, p=id_paciente)
    sql('UPDATE asignaciones SET fecha_desde = :d WHERE id_paciente = :p', d=INICIO, p=id_paciente)
    sql('UPDATE ingresos SET fecha_inicio = :d, fecha_completado = :c WHERE id_paciente = :p',
        d=INICIO, c=f'{OBJETIVOS_DESDE} 11:30:00', p=id_paciente)
    for etapa, dia in CIERRE_ETAPA.items():
        sql('UPDATE ingreso_etapas e JOIN ingresos i ON i.id = e.id_ingreso '
            'SET e.fecha_cierre = :f WHERE i.id_paciente = :p AND e.etapa = :e',
            f=f'{dia} 10:00:00', p=id_paciente, e=etapa)
    for id_objetivo in ids_objetivos:
        sql('UPDATE objetivos_terapeuticos SET fecha_creacion = :f WHERE id = :o',
            f=f'{OBJETIVOS_DESDE} 11:00:00', o=id_objetivo)


# ---------------------------------------------------------------------------
# Informes
# ---------------------------------------------------------------------------
MARCA = '[COMPLETAR'


def _secciones(contenido):
    """Divide en (cabecera_vacia, [(titulo, cuerpo)]) por las lineas '## '."""
    partes, titulo, cuerpo = [], None, []
    for linea in contenido.split('\n'):
        if linea.startswith('## '):
            if titulo is not None:
                partes.append((titulo, '\n'.join(cuerpo).strip()))
            titulo, cuerpo = linea[3:].strip(), []
        else:
            cuerpo.append(linea)
    if titulo is not None:
        partes.append((titulo, '\n'.join(cuerpo).strip()))
    return partes


def armar_periodico(plantilla, evolucion, cierre):
    """Mismo orden que el informe con IA: datos, periodo, asistencia, objetivos, evolucion y cierre."""
    secciones = []
    for titulo, cuerpo in _secciones(plantilla):
        if titulo.lower().startswith('observaciones de las sesiones'):
            continue                                  # la evolucion redactada la reemplaza
        if titulo.lower().startswith('cierre'):
            secciones.append(('Evolución del período', '\n\n'.join(evolucion)))
            cuerpo = cierre
        secciones.append((titulo, cuerpo))
    return '\n\n'.join(f'## {t}\n{c}' for t, c in secciones) + '\n'


def armar_pti(plantilla, coordinacion):
    secciones = []
    for titulo, cuerpo in _secciones(plantilla):
        if titulo.lower().startswith('coordinación y revisión'):
            cuerpo = coordinacion
        secciones.append((titulo, cuerpo))
    return '\n\n'.join(f'## {t}\n{c}' for t, c in secciones) + '\n'


def cargar_informe(api, id_paciente, tipo, periodo, texto_fn, publicado_el):
    informe = api.llamar('post', f'/api/pacientes/{id_paciente}/informes',
                         {'tipo': tipo, 'periodo': periodo, 'usar_ia': False})
    contenido = texto_fn(informe['contenido'])
    if MARCA in contenido:
        raise ErrorDeCarga(f'El informe {tipo} {periodo} todavía tiene marcas [COMPLETAR]:\n{contenido}')
    api.llamar('put', f"/api/informes/{informe['id']}", {'contenido': contenido})
    api.llamar('post', f"/api/informes/{informe['id']}/publicacion")
    sql('UPDATE informes SET fecha_generacion = :g, fecha_edicion = :e, fecha_publicacion = :p WHERE id = :i',
        g=f'{publicado_el} 09:00:00', e=f'{publicado_el} 10:00:00', p=f'{publicado_el} 11:00:00', i=informe['id'])
    return informe['id']


def _niveles(plantilla):
    return tuple(re.findall(r': (No logrado|Inicial|En proceso|Avanzado|Logrado) \(', plantilla))


def _periodico(textos, periodo, avisos):
    def armar(plantilla):
        if _niveles(plantilla) != textos['niveles']:
            avisos.append(f'{periodo}: los niveles calculados {_niveles(plantilla)} no coinciden con los '
                          f'del texto {textos["niveles"]}; revisar la redacción.')
        return armar_periodico(plantilla, textos['evolucion'], textos['cierre'])
    return armar


def cargar_informes(api, id_paciente):
    hechos, avisos = [], []
    for clave, textos in MENSUAL.items():
        mes = int(clave[5:])
        hechos.append(cargar_informe(api, id_paciente, 'mensual', clave, _periodico(textos, clave, avisos),
                                     dt.date(2026, mes + 1, 3)))
    for clave, textos in SEMESTRAL.items():
        hechos.append(cargar_informe(api, id_paciente, 'semestral', clave, _periodico(textos, clave, avisos),
                                     dt.date(2026, 7, 3)))
    hechos.append(cargar_informe(api, id_paciente, 'pti', 'pti', lambda p: armar_pti(p, PTI_COORDINACION),
                                 dt.date(2026, 3, 16)))
    return hechos, avisos


# ---------------------------------------------------------------------------
# Familiar
# ---------------------------------------------------------------------------
def cargar_familiar(api, id_paciente):
    r = api.llamar('post', f'/api/pacientes/{id_paciente}/familiares', {
        'nombre': 'Silvana', 'apellido': 'Paredes', 'email': EMAIL_FAMILIAR,
        'parentesco': 'madre', 'telefono': '11 5555-0147'})
    sql('UPDATE usuarios SET contrasena_hash = :h WHERE email = :e',
        h=hashear_contrasena(CONTRASENA_FAMILIAR), e=EMAIL_FAMILIAR)
    return r


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--email', default='laura.fernandez@asisto.local', help='terapeuta a la que se asigna')
    ap.add_argument('--contrasena', default='asisto2026')
    ap.add_argument('--admin', default='admin@asisto.local',
                    help='administrador que vincula a la familiar (solo el admin puede hacerlo)')
    ap.add_argument('--sin-informes', action='store_true', help='carga todo menos los informes (para pruebas)')
    args = ap.parse_args()

    app = create_app()
    with app.app_context():
        base = db.session.execute(text('SELECT DATABASE()')).scalar()
        existe = db.session.execute(text(
            "SELECT id FROM pacientes WHERE nombre = 'Mateo' AND apellido = 'Gómez'")).first()
        if existe:
            print(f'Ya existe Mateo Gómez (id {existe[0]}) en la base {base}. No se hizo nada.')
            return 0
        print(f'Base: {base}')
        api = Api(app, args.email, args.contrasena)
        admin = Api(app, args.admin, args.contrasena)

        alta = dict(PACIENTE, nro_historia=siguiente_nro_historia())
        paciente = api.llamar('post', '/api/pacientes', alta)['paciente']
        pid = paciente['id']
        print(f'1/6 Paciente creado: {paciente["nombre_completo"]} ({paciente["nro_historia"]}), id {pid}')

        cargar_familiar(admin, pid)
        print(f'2/6 Familiar vinculada: {EMAIL_FAMILIAR}')

        ids_objetivos = cargar_ingreso(api, pid)
        fechar_ingreso(pid, ids_objetivos)   # la asignacion y el alta nacen hoy: se llevan a marzo
        print(f'3/6 Ingreso completo: 4 etapas cerradas, {len(ids_objetivos)} objetivos, historia clínica generada')

        total, ausencias = cargar_sesiones(api, pid, ids_objetivos)
        print(f'4/6 Sesiones cargadas: {total} ({ausencias} ausencias) con su evolución')

        if args.sin_informes:
            print('5/6 Informes: omitidos (--sin-informes)')
        else:
            hechos, avisos = cargar_informes(api, pid)
            print(f'5/6 Informes publicados: {len(hechos)} (7 mensuales, 1 semestral, 1 PTI)')
            for aviso in avisos:
                print(f'    AVISO {aviso}')

        print('6/6 Listo. Mirar la ficha de Mateo Gómez con Laura Fernández.')
        print(f'    Familiar: {EMAIL_FAMILIAR} / {CONTRASENA_FAMILIAR}')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except ErrorDeCarga as error:
        print(f'\nERROR: {error}', file=sys.stderr)
        sys.exit(1)

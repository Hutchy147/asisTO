"""
Prueba de UI de los avisos del familiar (Entrega 4) con Chromium headless.
Requiere backend (5000) con la base demo y vite (5173) con VITE_ENTREGA=4.
Cruza dos roles: la terapeuta registra una sesion por la API y la familiar
ve el aviso en pantalla.
Uso: python3 tests/nube/ui_notificaciones.py [salida_png_dir]
"""
import re
import datetime as dt, json, os, sys, urllib.request
from playwright.sync_api import sync_playwright

BASE = 'http://localhost:5173'
API = 'http://localhost:5000/api'
SALIDA = sys.argv[1] if len(sys.argv) > 1 else '/tmp/claude-0/ui/doc/v4'
os.makedirs(SALIDA, exist_ok=True)
errores = []

def check(cond, msg):
    print(('OK   ' if cond else 'FALLA'), msg)
    if not cond:
        errores.append(msg)

def api(email, ruta, cuerpo):
    pedido = urllib.request.Request(API + '/auth/login', data=json.dumps({'email': email, 'contrasena': 'asisto2026'}).encode(), headers={'Content-Type': 'application/json'})
    token = json.load(urllib.request.urlopen(pedido))['token']
    pedido = urllib.request.Request(API + ruta, data=json.dumps(cuerpo).encode(), headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token})
    try:
        return json.load(urllib.request.urlopen(pedido))
    except urllib.error.HTTPError as e:
        return {'error': e.read().decode()}

def login(page, email):
    page.goto(BASE + '/login')
    page.fill('input[type=email]', email)
    page.fill('input[type=password]', 'asisto2026')
    page.click('button[type=submit]')
    page.wait_for_timeout(1500)

# Un dia distinto por corrida: el aviso de una sesion sale una sola vez (el
# texto lleva fecha y hora) y las sesiones de pruebas anteriores quedan en la
# base, asi que repetir fecha y hora no genera aviso nuevo (o se rechaza por
# superposicion) y la prueba fallaba en la segunda corrida. Se elige un dia
# pasado al azar; la hora es fija porque el seed deja libre la tarde.
import random
def dia_de_corrida():
    return random.randint(20, 180)

def dia_habil_pasado(atras):
    d = dt.date.today() - dt.timedelta(days=atras)
    while d.weekday() > 4:
        d -= dt.timedelta(days=1)
    return d.isoformat()

def crear_sesion_pasada(hora):
    """Sesion realizada de Tomas en un dia pasado al azar; reintenta otro dia si ese ya estaba ocupado."""
    for _ in range(15):
        r = api('laura.fernandez@asisto.local', '/sesiones',
                {'id_paciente': 1, 'fecha': dia_habil_pasado(dia_de_corrida()), 'hora_inicio': hora, 'estado': 'completa'})
        if 'error' not in r:
            return r
    raise RuntimeError(f'no se pudo crear una sesion de prueba a las {hora}: {r}')

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={'width': 1400, 'height': 900})
    page = ctx.new_page()
    consola = []
    page.on('console', lambda m: consola.append(m.text) if m.type == 'error' else None)

    login(page, 'marta.ledesma@asisto.local')
    page.wait_for_timeout(800)
    check(page.get_by_role('button', name='Avisos').count() == 1, 'barra con acceso a Avisos')
    page.screenshot(path=f'{SALIDA}/avisos_insignia.png')

    page.get_by_role('button', name='Avisos').click(); page.wait_for_timeout(1200)
    check(page.url.endswith('/familiar/notificaciones'), 'abre la pantalla de avisos')
    inicial = page.get_by_test_id('aviso').count()
    check(inicial >= 3, f'historial con avisos ({inicial})')
    cuerpo = page.locator('body').inner_text()
    check('trimestr' not in cuerpo.lower(), 'ningun aviso habla de trimestres')
    # Los avisos del seed salen de las sesiones reales: fecha y hora variables.
    check(re.search(r'Se registró la sesión del \d{2}/\d{2}/\d{4} a las \d{2}:\d{2} de Tomás\.', cuerpo) is not None,
          'tildes correctas en los avisos de demostracion')
    page.screenshot(path=f'{SALIDA}/avisos_historial.png', full_page=True)

    # preferencias: apagar "Nueva sesión registrada" y comprobar que no llega
    interruptor = page.get_by_role('checkbox', name='Nueva sesión registrada')
    interruptor.wait_for(); page.wait_for_timeout(500)
    check(interruptor.is_checked(), 'el tipo arranca habilitado')
    interruptor.click(); page.wait_for_timeout(900)
    check(not interruptor.is_checked(), 'se apaga el tipo')
    page.screenshot(path=f'{SALIDA}/avisos_preferencia_apagada.png')
    crear_sesion_pasada('19:00')
    page.reload(); page.wait_for_timeout(1200)
    check(page.get_by_test_id('aviso').count() == inicial, 'tipo apagado: no llega el aviso de la sesion nueva')
    check(not page.get_by_role('checkbox', name='Nueva sesión registrada').is_checked(), 'la preferencia persiste al recargar')

    # encenderlo y cruzar roles
    page.get_by_role('checkbox', name='Nueva sesión registrada').wait_for(); page.wait_for_timeout(500)
    page.get_by_role('checkbox', name='Nueva sesión registrada').click(); page.wait_for_timeout(900)
    crear_sesion_pasada('21:00')
    page.reload(); page.wait_for_timeout(1200)
    check(page.get_by_test_id('aviso').count() == inicial + 1, 'tipo encendido: llega el aviso de la sesion cargada por la terapeuta')
    check(page.get_by_text('Nuevo', exact=True).count() >= 1, 'el aviso nuevo figura como no leido')
    page.screenshot(path=f'{SALIDA}/avisos_nuevo.png')

    # filtrar
    page.locator('#filtro-tipo').click(); page.get_by_role('option', name='Cambios en los objetivos').click(); page.wait_for_timeout(900)
    check(page.get_by_test_id('aviso').count() >= 1 and page.get_by_text('Se registró la sesión').count() == 0, 'filtro por tipo')
    page.locator('#filtro-tipo').click(); page.get_by_role('option', name='Todos').click(); page.wait_for_timeout(700)

    # marcar leido / no leido y masivo
    # Con un solo aviso sin leer (fin de semana: el seed no tiene sesiones de
    # los ultimos tres dias) marcarlo dejaria el boton masivo sin nada que hacer.
    if page.get_by_text('Nuevo', exact=True).count() >= 2:
        page.get_by_role('button', name='Marcar como leído').first.click(); page.wait_for_timeout(800)
    page.get_by_role('button', name='Marcar todos como leídos').click(); page.wait_for_timeout(900)
    check(page.get_by_text('Nuevo', exact=True).count() == 0, 'marcar todos como leidos')
    check(page.get_by_role('button', name='Marcar todos como leídos').is_disabled(), 'sin pendientes el boton queda deshabilitado')
    page.screenshot(path=f'{SALIDA}/avisos_leidos.png')

    # el aviso llega a quien corresponde: Jorge (paciente 2) no ve el de Tomas
    page.get_by_role('button', name='Cerrar sesión').click(); page.wait_for_timeout(800)
    login(page, 'jorge.bustos@asisto.local')
    page.goto(BASE + '/familiar/notificaciones'); page.wait_for_timeout(1200)
    check(page.get_by_text('de Tomás').count() == 0, 'otro familiar no ve avisos de un paciente ajeno')

    check(not [c for c in consola if 'Failed' not in c and '401' not in c], f'sin errores de consola {consola[:2]}')
    b.close()

sys.exit(1 if errores else 0)

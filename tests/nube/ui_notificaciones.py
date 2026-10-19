"""
Prueba de UI de los avisos del familiar (Entrega 4) con Chromium headless.
Requiere backend (5000) con la base demo y vite (5173) con VITE_ENTREGA=4.
Cruza dos roles: la terapeuta registra una sesion por la API y la familiar
ve el aviso en pantalla.
Uso: python3 tests/nube/ui_notificaciones.py [salida_png_dir]
"""
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

def dia_habil_pasado(atras):
    d = dt.date.today() - dt.timedelta(days=atras)
    while d.weekday() > 4:
        d -= dt.timedelta(days=1)
    return d.isoformat()

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
    check('Se registró la sesión del 02/06/2026 de Tomas.' in cuerpo, 'tildes correctas en los avisos de demostracion')
    page.screenshot(path=f'{SALIDA}/avisos_historial.png', full_page=True)

    # preferencias: apagar "Nueva sesión registrada" y comprobar que no llega
    interruptor = page.get_by_role('checkbox', name='Nueva sesión registrada')
    interruptor.wait_for(); page.wait_for_timeout(500)
    check(interruptor.is_checked(), 'el tipo arranca habilitado')
    interruptor.click(); page.wait_for_timeout(900)
    check(not interruptor.is_checked(), 'se apaga el tipo')
    page.screenshot(path=f'{SALIDA}/avisos_preferencia_apagada.png')
    api('laura.fernandez@asisto.local', '/sesiones', {'id_paciente': 1, 'fecha': dia_habil_pasado(7), 'hora_inicio': '19:00', 'estado': 'completa'})
    page.reload(); page.wait_for_timeout(1200)
    check(page.get_by_test_id('aviso').count() == inicial, 'tipo apagado: no llega el aviso de la sesion nueva')
    check(not page.get_by_role('checkbox', name='Nueva sesión registrada').is_checked(), 'la preferencia persiste al recargar')

    # encenderlo y cruzar roles
    page.get_by_role('checkbox', name='Nueva sesión registrada').wait_for(); page.wait_for_timeout(500)
    page.get_by_role('checkbox', name='Nueva sesión registrada').click(); page.wait_for_timeout(900)
    api('laura.fernandez@asisto.local', '/sesiones', {'id_paciente': 1, 'fecha': dia_habil_pasado(8), 'hora_inicio': '19:00', 'estado': 'completa'})
    page.reload(); page.wait_for_timeout(1200)
    check(page.get_by_test_id('aviso').count() == inicial + 1, 'tipo encendido: llega el aviso de la sesion cargada por la terapeuta')
    check(page.get_by_text('Nuevo', exact=True).count() >= 1, 'el aviso nuevo figura como no leido')
    page.screenshot(path=f'{SALIDA}/avisos_nuevo.png')

    # filtrar
    page.locator('#filtro-tipo').click(); page.get_by_role('option', name='Cambios en los objetivos').click(); page.wait_for_timeout(900)
    check(page.get_by_test_id('aviso').count() >= 1 and page.get_by_text('Se registró la sesión').count() == 0, 'filtro por tipo')
    page.locator('#filtro-tipo').click(); page.get_by_role('option', name='Todos').click(); page.wait_for_timeout(700)

    # marcar leido / no leido y masivo
    page.get_by_role('button', name='Marcar como leído').first.click(); page.wait_for_timeout(800)
    page.get_by_role('button', name='Marcar todos como leídos').click(); page.wait_for_timeout(900)
    check(page.get_by_text('Nuevo', exact=True).count() == 0, 'marcar todos como leidos')
    check(page.get_by_role('button', name='Marcar todos como leídos').is_disabled(), 'sin pendientes el boton queda deshabilitado')
    page.screenshot(path=f'{SALIDA}/avisos_leidos.png')

    # el aviso llega a quien corresponde: Jorge (paciente 2) no ve el de Tomas
    page.get_by_role('button', name='Cerrar sesión').click(); page.wait_for_timeout(800)
    login(page, 'jorge.bustos@asisto.local')
    page.goto(BASE + '/familiar/notificaciones'); page.wait_for_timeout(1200)
    check(page.get_by_text('de Tomas').count() == 0, 'otro familiar no ve avisos de un paciente ajeno')

    check(not [c for c in consola if 'Failed' not in c and '401' not in c], f'sin errores de consola {consola[:2]}')
    b.close()

sys.exit(1 if errores else 0)

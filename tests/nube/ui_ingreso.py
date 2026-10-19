"""
Prueba de UI del flujo de ingreso y la configuracion del formulario (Entrega 4).
Requiere backend (5000) con la base demo y vite (5173) con VITE_ENTREGA=4.
Crea un paciente nuevo por la API (asignado a Laura) para no depender de la demo.
Uso: python3 tests/nube/ui_ingreso.py [salida_png_dir]
"""
import json, os, sys, time, urllib.request
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
    return json.load(urllib.request.urlopen(pedido))

def login(page, email):
    page.goto(BASE + '/login')
    page.fill('input[type=email]', email)
    page.fill('input[type=password]', 'asisto2026')
    page.click('button[type=submit]')
    page.wait_for_timeout(1500)

n = int(time.time()) % 100000
nuevo = api('laura.fernandez@asisto.local', '/pacientes', {
    'nombre': 'Ingreso', 'apellido': f'Pantalla{n}', 'fecha_nacimiento': '2018-05-04', 'nro_historia': f'HC-UI{n}'})
idp = nuevo['paciente']['id']
print('paciente nuevo', idp)

def llenar_etapa(page, etapa):
    """Completa los obligatorios de una etapa desplegada."""
    bloque = page.get_by_test_id(f'etapa-{etapa}')
    for c in bloque.locator('input[type=text], textarea:not([aria-hidden])').all():
        if c.is_visible() and c.is_enabled() and not c.input_value():
            c.fill('Dato de prueba para la etapa')
    for c in bloque.locator('input[type=date]').all():
        if c.is_enabled() and not c.input_value():
            c.fill('2026-10-01')
    # selects de opcion
    for s in bloque.locator('[role=combobox]').all():
        if s.is_enabled():
            s.click()
            page.get_by_role('option').nth(1).click()

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={'width': 1400, 'height': 1000})
    page = ctx.new_page()
    consola = []
    page.on('console', lambda m: consola.append(m.text) if m.type == 'error' else None)

    # --- terapeuta asignada ---
    login(page, 'laura.fernandez@asisto.local')
    page.goto(f'{BASE}/pacientes/{idp}'); page.wait_for_timeout(1200)
    page.get_by_role('tab', name='Ingreso').click(); page.wait_for_timeout(800)
    check(page.get_by_text('Todavía no tiene un ingreso iniciado').count() == 1, 'sin ingreso: invita a iniciarlo')
    page.screenshot(path=f'{SALIDA}/ingreso_vacio.png')
    page.get_by_role('button', name='Iniciar ingreso').click(); page.wait_for_timeout(1000)
    check(page.get_by_test_id('etapa-carpeta').count() == 1 and page.get_by_test_id('etapa-pti').count() == 1, 'aparecen las cuatro etapas')
    check(page.get_by_role('button', name='Completar ingreso').is_disabled(), 'no se puede completar sin etapas ni objetivos')

    for etapa in ('carpeta', 'evaluacion', 'entrevista', 'pti'):
        bloque = page.get_by_test_id(f'etapa-{etapa}')
        bloque.get_by_role('button').first.click(); page.wait_for_timeout(400)
        llenar_etapa(page, etapa)
        if etapa == 'carpeta':
            page.screenshot(path=f'{SALIDA}/ingreso_etapa.png', full_page=True)
        bloque.get_by_role('button', name='Cerrar etapa').click(); page.wait_for_timeout(900)
        check('Cerrada' in bloque.inner_text(), f'etapa {etapa} cerrada')
    req = page.get_by_test_id('requisitos').inner_text()
    check('Etapas cerradas: 4 de 4' in req and 'Objetivos activos: 0 de 3' in req, 'requisitos: 4 etapas y faltan objetivos')
    check(page.get_by_role('button', name='Completar ingreso').is_disabled(), 'sigue deshabilitado sin objetivos')
    page.screenshot(path=f'{SALIDA}/ingreso_requisitos.png', full_page=True)

    for i in range(3):
        api('laura.fernandez@asisto.local', '/objetivos', {'id_paciente': idp, 'descripcion': f'Objetivo de ingreso {i + 1} del paciente'})
    page.reload(); page.wait_for_timeout(1200)
    page.get_by_role('tab', name='Ingreso').click(); page.wait_for_timeout(800)
    boton = page.get_by_role('button', name='Completar ingreso')
    check(boton.is_enabled(), 'con 3 objetivos se habilita completar')
    boton.click(); page.wait_for_timeout(1500)
    check(page.get_by_text('La historia clínica del centro quedó generada').count() == 1, 'historia clinica generada')
    cuerpo = page.locator('body').inner_text()
    check('Objetivo de ingreso 1' in cuerpo, 'la historia incluye los objetivos')
    page.screenshot(path=f'{SALIDA}/ingreso_historia.png', full_page=True)
    check(page.get_by_role('button', name='Imprimir').count() >= 1, 'hay boton para imprimir')

    # --- otra terapeuta: solo lectura ---
    ctx2 = b.new_context(viewport={'width': 1400, 'height': 900}); p2 = ctx2.new_page()
    login(p2, 'diego.moyano@asisto.local')
    p2.goto(f'{BASE}/pacientes/{idp}'); p2.wait_for_timeout(1200)
    p2.get_by_role('tab', name='Ingreso').click(); p2.wait_for_timeout(800)
    check(p2.get_by_text('La historia clínica del centro quedó generada').count() == 1, 'otra terapeuta puede leer la historia')
    check(p2.get_by_role('tab', name='Familia').count() == 0, 'otra terapeuta no ve la pestana Familia')

    # --- administrador: configura el formulario, no ve respuestas ---
    ctx3 = b.new_context(viewport={'width': 1400, 'height': 1000}); p3 = ctx3.new_page()
    login(p3, 'admin@asisto.local')
    p3.goto(f'{BASE}/admin/formularios'); p3.wait_for_timeout(1500)
    check(p3.get_by_role('heading', name='Formulario de ingreso').count() == 1, 'admin ve la configuracion')
    check(p3.get_by_test_id('config-carpeta').count() == 1 and p3.get_by_test_id('config-pti').count() == 1, 'las cuatro etapas configurables')
    p3.screenshot(path=f'{SALIDA}/ingreso_config.png', full_page=True)
    p3.get_by_test_id('config-pti').get_by_role('button', name='Agregar campo').click(); p3.wait_for_timeout(500)
    p3.fill('#campo-clave', f'campo_ui_{n}')
    p3.fill('#campo-etiqueta', f'Observación de pantalla {n}')
    p3.get_by_role('dialog').get_by_role('button', name='Guardar').click(); p3.wait_for_timeout(1200)
    check(p3.get_by_text(f'Observación de pantalla {n}').count() >= 1, 'el campo nuevo aparece')
    interruptor = p3.get_by_role('checkbox', name=f'Visible: Observación de pantalla {n}')
    interruptor.click(); p3.wait_for_timeout(900)
    check(not interruptor.is_checked(), 'el campo se oculta (no se borra)')
    p3.goto(f'{BASE}/pacientes/{idp}'); p3.wait_for_timeout(1000)
    check(p3.get_by_role('tab', name='Ingreso').count() == 0, 'el admin no ve el ingreso de un paciente')

    # --- familiar ---
    ctx4 = b.new_context(viewport={'width': 1400, 'height': 900}); p4 = ctx4.new_page()
    login(p4, 'marta.ledesma@asisto.local')
    r = p4.request.get(f'{API}/pacientes/{idp}/historia-clinica')
    check(r.status in (401, 403), f'la familia no accede a la historia por la API ({r.status})')

    check(not consola, f'sin errores de consola {consola[:2]}')
    b.close()

print('\nRESULTADO:', 'TODO OK' if not errores else f'{len(errores)} fallas')
sys.exit(1 if errores else 0)

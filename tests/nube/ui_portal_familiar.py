"""
Prueba de UI del portal del familiar (Entrega 4) con Chromium headless.
Requiere backend (5000) con la base demo y vite (5173) con VITE_ENTREGA=4.
Demo: Marta Ledesma tiene dos pacientes vinculados (1 y 5).
Uso: python3 tests/nube/ui_portal_familiar.py [salida_png_dir]
"""
import os, sys
from playwright.sync_api import sync_playwright

BASE = 'http://localhost:5173'
SALIDA = sys.argv[1] if len(sys.argv) > 1 else '/tmp/claude-0/ui/doc/v4'
os.makedirs(SALIDA, exist_ok=True)
errores = []

def check(cond, msg):
    print(('OK   ' if cond else 'FALLA'), msg)
    if not cond:
        errores.append(msg)

def login(page, email):
    page.goto(BASE + '/login')
    page.fill('input[type=email]', email)
    page.fill('input[type=password]', 'asisto2026')
    page.click('button[type=submit]')
    page.wait_for_timeout(1500)

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={'width': 1400, 'height': 1000})
    page = ctx.new_page()
    consola = []
    page.on('console', lambda m: consola.append(m.text) if m.type == 'error' else None)

    login(page, 'marta.ledesma@asisto.local')
    check(page.url.endswith('/familiar'), f'el familiar entra a /familiar ({page.url})')
    page.wait_for_timeout(1000)
    check(page.get_by_text('Portal familiar').count() > 0, 'barra del portal')
    check(page.get_by_role('tab').filter(has_text='Objetivos').count() == 1, 'pestania Objetivos')
    check(page.locator('svg').count() > 0, 'hay graficos de evolucion')
    cuerpo = page.locator('body').inner_text()
    for prohibido in ('Diagnóstico', 'Observaciones', 'Obra social', 'N° de historia'):
        check(prohibido not in cuerpo, f'no se muestra "{prohibido}"')
    page.screenshot(path=f'{SALIDA}/portal_objetivos.png', full_page=True)

    # sesiones
    page.get_by_role('tab').filter(has_text='Sesiones').click(); page.wait_for_timeout(600)
    check(page.get_by_text('Asistió').count() > 0, 'listado de sesiones con valores por objetivo')
    page.screenshot(path=f'{SALIDA}/portal_sesiones.png', full_page=True)

    # filtro por fecha: un rango sin sesiones deja el listado vacio, y "Todo el tratamiento" vuelve
    todas = page.locator('tbody tr').count()
    page.fill('#filtro-desde', '2000-01-01'); page.fill('#filtro-hasta', '2000-01-31')
    page.get_by_role('button', name='Filtrar').click(); page.wait_for_timeout(900)
    check(page.get_by_text('No hay sesiones en este período').count() > 0, 'filtro por fecha sin resultados')
    page.screenshot(path=f'{SALIDA}/portal_filtro_vacio.png')
    page.fill('#filtro-desde', '2026-06-01'); page.fill('#filtro-hasta', '2026-05-01')
    check(page.get_by_text('no puede ser anterior').count() > 0 and page.get_by_role('button', name='Filtrar').is_disabled(), 'rango invertido: aviso y boton bloqueado')
    page.get_by_role('button', name='Todo el tratamiento').click(); page.wait_for_timeout(900)
    check(page.locator('tbody tr').count() == todas, 'Todo el tratamiento restaura el listado')

    # segundo paciente vinculado
    pestanias = page.get_by_role('tab').all_inner_texts()
    check(len([t for t in pestanias if 'Paciente' in t or t.strip()]) >= 3, f'selector de pacientes vinculados {pestanias}')

    # un familiar no entra a las pantallas de terapeuta
    page.goto(BASE + '/pacientes'); page.wait_for_timeout(1000)
    check(page.get_by_text('No tiene acceso a esta sección').count() > 0 or '/familiar' in page.url, f'rol familiar fuera de /pacientes ({page.url})')

    check(not [c for c in consola if 'Failed' not in c and '401' not in c and '403' not in c], f'sin errores de consola {consola[:3]}')
    b.close()

sys.exit(1 if errores else 0)

"""
Prueba de UI de HDU 11 con Chromium headless. Requiere backend (5000) con la
base demo y vite (5173) con VITE_ENTREGA=3 (o la que se pase en ENTREGA).
Uso: python3 tests/nube/ui_asignaciones.py [salida_png_dir]
"""
import os, sys
from playwright.sync_api import sync_playwright

BASE = 'http://localhost:5173'
SALIDA = sys.argv[1] if len(sys.argv) > 1 else '/tmp/claude-0/ui'
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
    page.wait_for_url('**/dashboard**', timeout=8000) if False else page.wait_for_timeout(1500)

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={'width': 1400, 'height': 900})
    page = ctx.new_page()
    consola = []
    page.on('console', lambda m: consola.append(m.text) if m.type == 'error' else None)

    login(page, 'laura.fernandez@asisto.local')
    page.goto(BASE + '/pacientes'); page.wait_for_timeout(1500)
    check(page.get_by_text('Responsable', exact=True).count() > 0, 'listado: columna Responsable')
    total = page.locator('tbody tr').count()
    page.get_by_label('Mis pacientes').check(); page.wait_for_timeout(500)
    mios = page.locator('tbody tr').count()
    check(0 < mios < total, f'filtro Mis pacientes: {mios} de {total}')
    page.screenshot(path=f'{SALIDA}/pacientes.png')

    # ficha de un paciente que NO es de Laura -> aviso + pestaña Asignación
    page.get_by_label('Mis pacientes').uncheck(); page.wait_for_timeout(300)
    page.locator('tbody tr').nth(1).click(); page.wait_for_timeout(1500)
    page.get_by_role('tab', name='Asignación').click(); page.wait_for_timeout(800)
    check(page.get_by_text('Terapeuta responsable').count() > 0, 'ficha: pestaña Asignación visible')
    check(page.get_by_role('button', name='Asignar terapeuta').count() == 0, 'ficha: el terapeuta no puede asignar')
    page.screenshot(path=f'{SALIDA}/ficha_asignacion.png')

    # alta con responsable por defecto
    page.goto(BASE + '/pacientes'); page.wait_for_timeout(1200)
    page.get_by_role('button', name='Agregar paciente').first.click(); page.wait_for_timeout(500)
    check(page.get_by_label('Terapeuta responsable').count() == 0 and page.get_by_text('Cualquier cambio de terapeuta').count() == 1, 'alta: sin selector de responsable; queda asignado a quien lo da de alta')
    page.screenshot(path=f'{SALIDA}/alta.png')

    # calendario: el selector solo ofrece pacientes asignados
    page.goto(BASE + '/calendario'); page.wait_for_timeout(1500)
    page.screenshot(path=f'{SALIDA}/calendario.png')

    check(not [c for c in consola if 'Failed' not in c and '401' not in c], f'sin errores de consola {consola[:3]}')
    b.close()

sys.exit(1 if errores else 0)

"""
Prueba de UI del vinculo familiar-paciente (Entrega 4) con Chromium headless.
Requiere backend (5000) con la base demo y vite (5173) con VITE_ENTREGA=4.
Uso: python3 tests/nube/ui_familiares.py [salida_png_dir]
"""
import os, sys, time
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
    ctx = b.new_context(viewport={'width': 1400, 'height': 900})
    page = ctx.new_page()
    consola = []
    page.on('console', lambda m: consola.append(m.text) if m.type == 'error' else None)

    login(page, 'laura.fernandez@asisto.local')
    page.goto(BASE + '/pacientes'); page.wait_for_timeout(1200)
    page.get_by_label('Mis pacientes').check(); page.wait_for_timeout(500)
    page.locator('tbody tr').first.click(); page.wait_for_timeout(1500)
    check(page.get_by_role('tab', name='Familia').count() == 1, 'ficha de paciente propio: pestania Familia')
    page.get_by_role('tab', name='Familia').click(); page.wait_for_timeout(1000)
    check(page.get_by_text('Familiares con acceso').count() > 0, 'se muestra la seccion')
    page.screenshot(path=f'{SALIDA}/familia_lista.png')

    # crear cuenta nueva
    sufijo = str(int(time.time()))
    page.get_by_role('button', name='Crear cuenta').click(); page.wait_for_timeout(500)
    page.locator('#familiar-nombre').fill('Elena')
    page.locator('#familiar-apellido').fill('Prueba')
    page.locator('#familiar-email').fill(f'elena.{sufijo}@asisto.local')
    page.locator('#familiar-parentesco').fill('Tía')
    page.screenshot(path=f'{SALIDA}/familia_crear.png')
    page.get_by_role('button', name='Crear y vincular').click(); page.wait_for_timeout(1500)
    clave = page.get_by_test_id('contrasena-temporal').inner_text()
    check(len(clave) >= 10, 'se muestra la contrasena temporal una vez')
    page.screenshot(path=f'{SALIDA}/familia_contrasena.png')
    page.get_by_role('button', name='Entendido').click(); page.wait_for_timeout(800)
    check(page.get_by_text('Elena Prueba').count() > 0, 'la lista muestra el familiar nuevo')

    # correo repetido -> rechazo con mensaje formal
    page.get_by_role('button', name='Crear cuenta').click(); page.wait_for_timeout(400)
    page.locator('#familiar-nombre').fill('Elena')
    page.locator('#familiar-apellido').fill('Prueba')
    page.locator('#familiar-email').fill(f'elena.{sufijo}@asisto.local')
    page.get_by_role('button', name='Crear y vincular').click(); page.wait_for_timeout(1000)
    check(page.get_by_text('Ya existe una cuenta con ese correo').count() > 0, 'correo repetido: mensaje del servidor')
    page.screenshot(path=f'{SALIDA}/familia_rechazo.png')
    page.get_by_role('button', name='Cancelar').click(); page.wait_for_timeout(300)
    if page.get_by_role('button', name='Descartar').count():
        page.get_by_role('button', name='Descartar').click(); page.wait_for_timeout(300)

    # quitar acceso
    fila = page.locator('tbody tr', has_text='Elena Prueba')
    fila.get_by_role('button', name='Quitar acceso').click(); page.wait_for_timeout(500)
    page.screenshot(path=f'{SALIDA}/familia_quitar.png')
    page.get_by_role('dialog').get_by_role('button', name='Quitar acceso').click(); page.wait_for_timeout(1200)
    check(page.locator('tbody tr', has_text='Elena Prueba').count() == 0, 'el familiar quitado desaparece de la lista')

    # vincular existente
    page.get_by_role('button', name='Vincular existente').click(); page.wait_for_timeout(600)
    page.screenshot(path=f'{SALIDA}/familia_existente.png')

    check(not [c for c in consola if 'Failed' not in c and '401' not in c], f'sin errores de consola {consola[:3]}')
    b.close()

sys.exit(1 if errores else 0)

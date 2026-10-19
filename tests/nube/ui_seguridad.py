"""
UI de recuperacion de contrasena y bloqueo (Entrega 3) con Chromium headless.
Requiere backend (5000) con la base demo y Vite (5173) con VITE_ENTREGA=3.
CAMBIA la clave de paula.cabrera en la base demo (la vuelve a dejar igual).
"""
import re, sys
from playwright.sync_api import sync_playwright

B = 'http://localhost:5173'
EMAIL = 'paula.cabrera@asisto.local'
fallas = []

def check(c, m):
    print(('OK   ' if c else 'FALLA'), m)
    if not c: fallas.append(m)

with sync_playwright() as p:
    br = p.chromium.launch()
    pg = br.new_page(viewport={'width': 1200, 'height': 800})

    # 1) bloqueo en pantalla: 5 intentos con clave mala
    pg.goto(B + '/login')
    check(pg.get_by_text('¿Olvidó su contraseña?').count() == 1, 'login: link de recuperacion')
    for i in range(5):
        pg.fill('input[type=email]', EMAIL); pg.fill('input[type=password]', 'mala')
        pg.click('button[type=submit]'); pg.wait_for_timeout(700)
    check(pg.get_by_text('Demasiados intentos fallidos').count() == 1, 'login: mensaje de bloqueo tras 5 fallos')
    pg.fill('input[type=password]', 'asisto2026'); pg.click('button[type=submit]'); pg.wait_for_timeout(800)
    check('/login' in pg.url and pg.get_by_text('Demasiados intentos').count() == 1, 'login: la clave correcta tampoco entra bloqueada')
    pg.screenshot(path='/tmp/claude-0/ui/login_bloqueado.png')

    # 2) recuperar -> enlace (modo desarrollo) -> nueva clave
    pg.get_by_text('¿Olvidó su contraseña?').click()
    pg.fill('input[type=email]', EMAIL); pg.click('button[type=submit]'); pg.wait_for_timeout(800)
    check(pg.get_by_text('se genero un enlace').count() == 1, 'recuperar: aviso generico')
    pg.get_by_text('abrir el enlace de recuperación').click(); pg.wait_for_timeout(500)
    check('/restablecer/' in pg.url, 'restablecer: se abre con el token')
    campos = pg.locator('input[type=password]')
    campos.nth(0).fill('NuevaClave2026'); campos.nth(1).fill('Distinta2026'); pg.wait_for_timeout(200)
    check(pg.get_by_text('No coinciden.').count() == 1 and pg.locator('button[type=submit]').is_disabled(), 'restablecer: no coinciden bloquea el boton')
    campos.nth(1).fill('NuevaClave2026')
    pg.click('button[type=submit]'); pg.wait_for_timeout(1000)
    check(pg.get_by_text('Contraseña actualizada').count() == 1, 'restablecer: confirmacion')
    pg.screenshot(path='/tmp/claude-0/ui/restablecido.png')
    token_url = None

    # 3) ya desbloqueada y con la clave nueva entra; el enlace no se puede reusar
    pg.goto(B + '/login')
    pg.fill('input[type=email]', EMAIL); pg.fill('input[type=password]', 'NuevaClave2026')
    pg.click('button[type=submit]'); pg.wait_for_timeout(1500)
    check('/login' not in pg.url, 'login con la clave nueva entra (el bloqueo se levanto)')
    br.close()
sys.exit(1 if fallas else 0)

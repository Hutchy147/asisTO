"""
UI de la auditoria de seguridad de la V6: la sesion vive en una cookie HttpOnly
(nada en localStorage), F5 la conserva, cerrar sesion la revoca de verdad, un
texto con HTML se muestra como texto (no se ejecuta) y la pagina no se deja
embeber en un iframe. Backend 5000 + Vite 5173, base demo.
Cambia el nombre de un paciente a un texto con HTML y lo restaura al final.
"""
import subprocess, sys
from playwright.sync_api import sync_playwright
B = 'http://localhost:5173'
fallas = []
XSS = '<img src=x onerror="window.__xss=1">Zz'


def sql(q):
    return subprocess.run(['mysql', 'asisto', '-N', '-e', q], check=True, capture_output=True, text=True).stdout.strip()


def check(c, m):
    print(('OK   ' if c else 'FALLA'), m)
    if not c: fallas.append(m)


original = sql("SELECT apellido FROM pacientes WHERE id = 13")
try:
    sql(f"UPDATE pacientes SET apellido = '{XSS.replace(chr(39), chr(39) * 2)}' WHERE id = 13")
    with sync_playwright() as p:
        br = p.chromium.launch()
        ctx = br.new_context(viewport={'width': 1400, 'height': 950})
        pg = ctx.new_page()
        pg.goto(B + '/login'); pg.fill('input[type=email]', 'laura.fernandez@asisto.local')
        pg.fill('input[type=password]', 'asisto2026'); pg.click('button[type=submit]'); pg.wait_for_timeout(1800)

        almacenado = pg.evaluate('JSON.stringify(Object.assign({}, localStorage))')
        check('eyJ' not in almacenado, f'ningún JWT en localStorage ({almacenado})')
        cookies = ctx.cookies()
        sesion = [c for c in cookies if c['name'] == 'asisto_sesion']
        check(len(sesion) == 1 and sesion[0]['httpOnly'] and sesion[0]['sameSite'] == 'Strict',
              'la sesión es una cookie HttpOnly y SameSite=Strict')
        check(pg.evaluate("document.cookie.includes('asisto_sesion')") is False, 'el JavaScript de la página no ve la cookie')

        pg.reload(); pg.wait_for_timeout(2000)
        check('/panel' in pg.url and pg.get_by_text('Cerrar sesión').count() >= 1, 'F5 conserva la sesión')

        # XSS almacenado: el nombre con HTML se ve como texto y no ejecuta nada
        pg.goto(B + '/pacientes'); pg.wait_for_timeout(1800)
        check(pg.get_by_text('onerror', exact=False).count() >= 1, 'el texto con HTML se muestra literal')
        check(pg.evaluate('window.__xss') is None, 'el HTML del nombre no se ejecutó')

        # cerrar sesión: el token anterior deja de servir aunque alguien lo hubiera copiado
        token = sesion[0]['value']
        pg.get_by_text('Cerrar sesión').first.click(); pg.wait_for_timeout(1500)
        check('/login' in pg.url, 'cerrar sesión vuelve al login')
        r = pg.request.get('http://localhost:5000/api/auth/me', headers={'Authorization': f'Bearer {token}'})
        check(r.status == 401, f'el token de la sesión cerrada ya no sirve ({r.status})')
        pg.goto(B + '/pacientes'); pg.wait_for_timeout(1500)
        check('/login' in pg.url, 'sin sesión, una ruta protegida manda al login')

        # cabeceras de la página y de la API
        r = pg.request.get(B + '/login')
        check(r.headers.get('x-frame-options') == 'DENY', 'la página no se deja embeber en un iframe')
        r = pg.request.get('http://localhost:5000/api/health')
        check(r.headers.get('cache-control') == 'no-store' and r.headers.get('x-frame-options') == 'DENY',
              'la API manda no-store y X-Frame-Options')
        br.close()
finally:
    sql(f"UPDATE pacientes SET apellido = '{original}' WHERE id = 13")

print('FALLAS:', len(fallas)) if fallas else print('TODO OK')
sys.exit(1 if fallas else 0)

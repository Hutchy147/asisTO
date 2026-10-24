"""
UI de las cuentas de acceso del administrador: dar de alta un correo con su
clave, ver los datos para entregar, entrar con esa cuenta, deshabilitarla,
habilitarla y restablecer la clave. Backend 5000 + Vite 5173 con
VITE_ENTREGA=6, base demo. Crea una cuenta de prueba y la borra al final.
"""
import re
import subprocess
import sys
from playwright.sync_api import sync_playwright

B = 'http://localhost:5173'
EMAIL = 'nueva.prueba@asisto.local'
CLAVE = 'Entrada2026x'
fallas = []


def sql(q):
    return subprocess.run(['mysql', 'asisto', '-N', '-e', q], check=True, capture_output=True, text=True).stdout.strip()


def check(c, m):
    print(('OK   ' if c else 'FALLA'), m)
    if not c: fallas.append(m)


def limpiar():
    sql(f"DELETE FROM terapeutas WHERE id_usuario IN (SELECT id FROM usuarios WHERE email = '{EMAIL}')")
    sql(f"DELETE FROM auditoria_accesos WHERE email = '{EMAIL}'")
    sql(f"DELETE FROM usuarios WHERE email = '{EMAIL}'")


def entrar(pg, email, clave='asisto2026'):
    pg.context.clear_cookies()
    pg.goto(B + '/login'); pg.fill('input[type=email]', email); pg.fill('input[type=password]', clave)
    pg.click('button[type=submit]'); pg.wait_for_timeout(1800)


limpiar()
try:
    with sync_playwright() as p:
        br = p.chromium.launch()
        pg = br.new_context(viewport={'width': 1400, 'height': 1000}).new_page()
        entrar(pg, 'admin@asisto.local')
        pg.get_by_role('button', name='Cuentas de acceso').click(); pg.wait_for_timeout(1500)
        check('/admin/usuarios' in pg.url and pg.get_by_text('Solo pueden ingresar los correos que figuran acá').count() == 1,
              'el menú del administrador lleva a las cuentas de acceso')
        check(pg.get_by_text('laura.fernandez@asisto.local').count() >= 1, 'el listado muestra los correos precargados')

        # --- alta ---
        pg.get_by_role('button', name='Nueva cuenta').click(); pg.wait_for_timeout(600)
        d = pg.get_by_role('dialog')
        check(d.locator('#cuenta-matricula').count() == 0, 'sin elegir rol no pide datos del rol')
        d.locator('#cuenta-rol').click(); pg.get_by_role('option', name='Terapeuta').click(); pg.wait_for_timeout(300)
        check(d.locator('#cuenta-matricula').count() == 1, 'un terapeuta pide su matrícula')
        d.locator('#cuenta-nombre').fill('Nora'); d.locator('#cuenta-apellido').fill('Prueba')
        d.locator('#cuenta-email').fill(EMAIL)
        d.locator('#cuenta-contrasena').fill('corta')
        d.locator('#cuenta-matricula').fill('MP-9555')
        d.get_by_role('button', name='Crear cuenta').click(); pg.wait_for_timeout(1000)
        check(d.get_by_text('al menos 8 caracteres').count() >= 1, 'una clave corta se rechaza diciendo por qué')
        d.get_by_role('button', name='Generar una').click(); pg.wait_for_timeout(800)
        generada = d.locator('#cuenta-contrasena').input_value()
        check(len(generada) >= 8, f'«Generar una» completa la clave ({len(generada)} caracteres)')
        d.locator('#cuenta-contrasena').fill(CLAVE)
        d.get_by_role('button', name='Crear cuenta').click(); pg.wait_for_timeout(1500)
        entrega = pg.get_by_role('dialog')
        check(entrega.get_by_text('Cuenta creada').count() >= 1 and entrega.locator(f'input[value="{CLAVE}"]').count() == 1
              and entrega.locator(f'input[value="{EMAIL}"]').count() == 1, 'muestra el correo y la clave para entregar')
        check(entrega.get_by_text('no se vuelve a mostrar').count() >= 1, 'avisa que la clave no se vuelve a mostrar')
        entrega.get_by_role('button', name='Listo').click(); pg.wait_for_timeout(500)
        fila = pg.get_by_role('row').filter(has_text=EMAIL)
        check(fila.count() == 1 and fila.get_by_text('Habilitada').count() == 1 and fila.get_by_text('Matrícula MP-9555').count() == 1,
              'la cuenta nueva figura habilitada, con su matrícula')

        # --- entra con la cuenta nueva ---
        entrar(pg, EMAIL, CLAVE)
        check('/panel' in pg.url, 'la cuenta nueva entra con la clave cargada y llega a su panel')

        # --- deshabilitar y habilitar ---
        entrar(pg, 'admin@asisto.local')
        pg.goto(B + '/admin/usuarios'); pg.wait_for_timeout(1500)
        pg.get_by_role('button', name=re.compile('^Deshabilitar a Nora')).click(); pg.wait_for_timeout(400)
        check(pg.get_by_role('dialog').get_by_text('cerrarán sus sesiones abiertas').count() == 1, 'la confirmación explica qué pasa')
        pg.get_by_role('dialog').get_by_role('button', name='Deshabilitar').click(); pg.wait_for_timeout(1500)
        check(pg.get_by_role('row').filter(has_text=EMAIL).get_by_text('Deshabilitada').count() == 1, 'queda deshabilitada')
        entrar(pg, EMAIL, CLAVE)
        check('/login' in pg.url and pg.get_by_text('Email o contraseña incorrectos').count() >= 1, 'deshabilitada, no entra')
        entrar(pg, 'admin@asisto.local')
        pg.goto(B + '/admin/usuarios'); pg.wait_for_timeout(1500)
        pg.get_by_role('button', name=re.compile('^Habilitar a Nora')).click(); pg.wait_for_timeout(400)
        pg.get_by_role('dialog').get_by_role('button', name='Habilitar').click(); pg.wait_for_timeout(1500)
        check(pg.get_by_role('row').filter(has_text=EMAIL).get_by_text('Habilitada').count() == 1, 'se vuelve a habilitar')

        # --- la propia cuenta no se deshabilita ---
        mia = pg.get_by_role('row').filter(has_text='admin@asisto.local')
        check(mia.get_by_role('button', name=re.compile('^Deshabilitar')).count() == 0, 'el administrador no ve «Deshabilitar» en su propia cuenta')

        # --- restablecer la clave ---
        pg.get_by_role('button', name=re.compile('^Restablecer la contraseña de Nora')).click(); pg.wait_for_timeout(500)
        d = pg.get_by_role('dialog')
        d.locator('#clave-nueva').fill('Segunda2026y')
        d.get_by_role('button', name='Restablecer').click(); pg.wait_for_timeout(1500)
        check(pg.get_by_role('dialog').get_by_text('Contraseña restablecida').count() >= 1, 'muestra la clave nueva para entregar')
        pg.get_by_role('dialog').get_by_role('button', name='Listo').click(); pg.wait_for_timeout(400)
        entrar(pg, EMAIL, 'Segunda2026y')
        check('/panel' in pg.url, 'entra con la clave restablecida')

        # --- el rol no administrador no ve la pantalla ---
        pg.goto(B + '/admin/usuarios'); pg.wait_for_timeout(1200)
        check(pg.get_by_text('No tiene acceso a esta sección').count() == 1, 'un terapeuta no entra a las cuentas de acceso')
        br.close()
finally:
    limpiar()

print('FALLAS:', len(fallas)) if fallas else print('TODO OK')
sys.exit(1 if fallas else 0)

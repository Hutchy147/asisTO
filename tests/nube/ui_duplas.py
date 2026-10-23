"""
UI de duplas (Entrega 5): el calendario muestra la dupla como un solo bloque,
se crea una dupla nueva, se forma otra sobre un turno individual y se quita.
Backend 5000 + Vite 5173 con VITE_ENTREGA=5, base demo, como Laura.
"""
import subprocess, sys
from playwright.sync_api import sync_playwright
B = 'http://localhost:5173'
V = '/tmp/claude-0/ui/doc/v5/'
fallas = []

def sql(q):
    return subprocess.run(['mysql', 'asisto', '-N', '-e', q], check=True, capture_output=True, text=True).stdout.strip()

def check(c, m):
    print(('OK   ' if c else 'FALLA'), m)
    if not c: fallas.append(m)

def limpiar():
    # turnos de prueba (martes 06:00) y sus sesiones futuras
    sql("DELETE FROM sesiones WHERE hora_inicio='06:00:00' AND estado='incompleta' AND fecha>=CURDATE()")
    sql("DELETE FROM agenda_recurrente WHERE hora_inicio='06:00:00' AND dia_semana=2")

limpiar()
with sync_playwright() as p:
    br = p.chromium.launch()
    pg = br.new_page(viewport={'width': 1400, 'height': 950})
    pg.goto(B + '/login'); pg.fill('input[type=email]', 'laura.fernandez@asisto.local'); pg.fill('input[type=password]', 'asisto2026')
    pg.click('button[type=submit]'); pg.wait_for_timeout(1500)
    pg.goto(B + '/calendario'); pg.wait_for_timeout(2500)
    bloque = pg.get_by_role('button', name='Turno del Lunes a las 15:00', exact=False)
    check(bloque.count() == 1, 'la dupla demo es un solo bloque en el calendario')
    check('Bruno Peralta y Benicio Herrera' in (bloque.inner_text() if bloque.count() else ''), 'el bloque muestra los dos nombres')
    pg.screenshot(path=V + '01_calendario_dupla.png')

    # crear dupla nueva
    pg.get_by_role('button', name='Nuevo turno', exact=True).click(); pg.wait_for_timeout(500)
    pg.locator('#turno-paciente').click(); pg.get_by_role('option', name='Tomás Aguirre').click()
    pg.locator('#turno-companero').click(); pg.get_by_role('option', name='Lucía Molina').click()
    pg.locator('#turno-dia').click(); pg.get_by_role('option', name='Martes', exact=True).click()
    pg.fill('#turno-inicio', '06:00'); pg.fill('#turno-fin', '06:45')
    pg.screenshot(path=V + '02_nueva_dupla.png')
    pg.get_by_role('button', name='Guardar turno').click(); pg.wait_for_timeout(2200)
    check(pg.get_by_role('button', name='Turno del Martes a las 06:00').count() == 1, 'la dupla nueva aparece como un bloque')
    check(sql("SELECT COUNT(*) FROM sesiones WHERE hora_inicio='06:00:00' AND id_dupla IS NOT NULL AND fecha>=CURDATE()") not in ('0', ''), 'se generaron sesiones en dupla')

    # quitar solo a uno
    pg.get_by_role('button', name='Turno del Martes a las 06:00').click(); pg.wait_for_timeout(500)
    check(pg.get_by_text('Dupla terapéutica').count() == 1, 'el dialogo explica la dupla')
    pg.screenshot(path=V + '03_dialogo_dupla.png')
    pg.get_by_role('button', name='Quitar solo a Tomás Aguirre').click(); pg.wait_for_timeout(1500)
    b = pg.get_by_role('button', name='Turno del Martes a las 06:00')
    check(b.count() == 1 and 'Lucía Molina' in b.inner_text() and ' y ' not in b.inner_text(), 'el compañero queda como turno individual')

    # formar dupla sobre el individual
    b.click(); pg.wait_for_timeout(500)
    pg.locator('#turno-sumar-companero').click(); pg.get_by_role('option', name='Emilia Paz').click()
    pg.get_by_role('button', name='Formar dupla').click(); pg.wait_for_timeout(2200)
    b = pg.get_by_role('button', name='Turno del Martes a las 06:00')
    check(b.count() == 1 and 'Lucía Molina y Emilia Paz' in b.inner_text(), 'se formo la dupla sobre el turno individual')

    # quitar la dupla completa
    b.click(); pg.wait_for_timeout(500)
    pg.get_by_role('button', name='Quitar la dupla').click(); pg.wait_for_timeout(1500)
    check(pg.get_by_role('button', name='Turno del Martes a las 06:00').count() == 0, 'quitar la dupla saca los dos turnos')

    # panel y detalle
    pg.goto(B + '/panel'); pg.wait_for_timeout(2500)
    pg.screenshot(path=V + '04_panel_dupla.png')
    br.close()

limpiar()
if fallas:
    print('\nFALLAS:', len(fallas)); sys.exit(1)
print('\nTodo OK')

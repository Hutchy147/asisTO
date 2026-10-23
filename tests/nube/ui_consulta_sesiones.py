"""
UI de consulta de sesiones y tendencias (Entrega 5): pantalla Sesiones con
filtros y paginacion, detalle de solo lectura de una sesion ajena, y la
seccion de tendencia en la pestaña Progreso. Backend 5000 + Vite 5173 con
VITE_ENTREGA=5, base demo, como Laura. Solo lee: no deja datos.
"""
import sys
from playwright.sync_api import sync_playwright
B = 'http://localhost:5173'
V = '/tmp/claude-0/ui/doc/v5/'
fallas = []

def check(c, m):
    print(('OK   ' if c else 'FALLA'), m)
    if not c: fallas.append(m)

with sync_playwright() as p:
    br = p.chromium.launch()
    pg = br.new_page(viewport={'width': 1400, 'height': 950})
    pg.goto(B + '/login'); pg.fill('input[type=email]', 'laura.fernandez@asisto.local'); pg.fill('input[type=password]', 'asisto2026')
    pg.click('button[type=submit]'); pg.wait_for_timeout(1800)

    pg.get_by_role('link', name='Sesiones').click(); pg.wait_for_timeout(2200)
    check(pg.url.endswith('/sesiones'), 'el menu lleva a Sesiones')
    check(pg.get_by_text('Sesiones registradas').count() >= 1, 'titulo de la pantalla')
    filas = pg.locator('tbody tr')
    check(filas.count() > 0, 'lista sesiones registradas')
    check(pg.get_by_text('Página 1 de').count() == 1, 'muestra la paginacion')
    check(pg.get_by_text('Agendada').count() == 0, 'no muestra sesiones agendadas')
    pg.screenshot(path=V + '07_sesiones_registradas.png')

    # paginacion
    pg.get_by_role('button', name='Siguiente').click(); pg.wait_for_timeout(1200)
    check(pg.get_by_text('Página 2 de').count() == 1, 'pasa a la pagina 2')
    pg.get_by_role('button', name='Anterior').click(); pg.wait_for_timeout(1000)

    # filtro por estado
    pg.locator('#filtro-estado').click(); pg.get_by_role('option', name='Ausencias').click(); pg.wait_for_timeout(1500)
    chips = pg.locator('tbody tr').all_inner_texts()
    check(len(chips) > 0 and all('Ausente' in t for t in chips), 'el filtro de estado deja solo ausencias')
    pg.locator('#filtro-estado').click(); pg.get_by_role('option', name='Todos').click(); pg.wait_for_timeout(1000)

    # todas las terapeutas: aparece una sesion de otra terapeuta y se abre en solo lectura
    pg.locator('#filtro-terapeuta').click(); pg.get_by_role('option', name='Todos los terapeutas').click(); pg.wait_for_timeout(1500)
    ajena = pg.locator('tbody tr', has_text='Moyano').first
    check(ajena.count() == 1, 'con "todas" se ven sesiones de otra terapeuta')
    ajena.click(); pg.wait_for_timeout(1500)
    check(pg.get_by_text('otro terapeuta').count() >= 1, 'el detalle de una sesion ajena lo aclara')
    check(pg.get_by_role('button', name='Editar sesión').count() == 0, 'no ofrece editar una sesion ajena')
    pg.keyboard.press('Escape'); pg.wait_for_timeout(500)

    # rango invertido
    pg.fill('#filtro-desde', '2026-10-19'); pg.fill('#filtro-hasta', '2026-10-01'); pg.wait_for_timeout(800)
    check(pg.get_by_text('La fecha inicial es posterior a la final').count() == 1, 'avisa un rango invertido')

    # tendencias en la ficha de un paciente (dupla demo: Bruno Peralta)
    pg.goto(B + '/pacientes/4'); pg.wait_for_timeout(2000)
    pg.get_by_role('tab', name='Progreso').click(); pg.wait_for_timeout(2500)
    caja = pg.get_by_test_id('tendencias')
    check(caja.count() == 1, 'la pestaña Progreso trae la tendencia por objetivo')
    texto = caja.inner_text()
    check(any(w in texto for w in ('Mejora', 'Se mantiene', 'Retrocede')), 'muestra la tendencia en palabras')
    check('Mejoró' in texto or 'Sin cambios' in texto, 'muestra la comparacion con el periodo anterior')
    check('%' not in texto, 'no muestra porcentajes')
    pg.screenshot(path=V + '08_tendencia_progreso.png')
    pg.locator('#tendencia-dias').click(); pg.get_by_role('option', name='Últimos 90 días').click(); pg.wait_for_timeout(1500)
    check(pg.get_by_test_id('tendencias').get_by_text('Sin datos suficientes').count() >= 1, 'un periodo sin historia previa dice que faltan datos')

    # roles
    for email in ('rrhh', ):
        pass
    pr = br.new_page(viewport={'width': 1400, 'height': 900})
    pr.goto(B + '/login'); pr.fill('input[type=email]', 'silvia.quiroga@asisto.local'); pr.fill('input[type=password]', 'asisto2026')
    pr.click('button[type=submit]'); pr.wait_for_timeout(1800)
    pr.goto(B + '/sesiones'); pr.wait_for_timeout(1500)
    check(not pr.url.endswith('/sesiones') or pr.get_by_text('no puede ver').count() > 0, 'RRHH no accede a Sesiones')
    br.close()

if fallas:
    print('\nFALLAS:', len(fallas)); sys.exit(1)
print('\nTodo OK')

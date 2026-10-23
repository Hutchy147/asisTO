"""
UI del portal del paciente (Entrega 6): Camila ve sus objetivos y su progreso,
solo en palabras, sin informes y sin pantallas de terapeuta. Backend 5000 + Vite
5173 con VITE_ENTREGA=6, base demo. No escribe nada.
"""
import re, sys
from playwright.sync_api import sync_playwright
B = 'http://localhost:5173'
SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
fallas = []

def check(c, m):
    print(('OK   ' if c else 'FALLA'), m)
    if not c: fallas.append(m)

with sync_playwright() as p:
    br = p.chromium.launch()
    pg = br.new_page(viewport={'width': 1300, 'height': 950})
    pg.goto(B + '/login'); pg.fill('input[type=email]', 'camila.rios@asisto.local'); pg.fill('input[type=password]', 'asisto2026')
    pg.click('button[type=submit]'); pg.wait_for_timeout(1800)
    check(pg.url.endswith('/paciente'), f'Camila entra a /paciente ({pg.url})')
    pg.wait_for_timeout(1500)
    check(pg.get_by_text('Mi seguimiento').count() >= 1, 'barra del portal del paciente')
    check(pg.get_by_text('Camila Ríos').count() >= 1, 'muestra su nombre')
    check(pg.get_by_text('Mis objetivos').count() >= 1, 'lista sus objetivos')
    check(pg.get_by_text('Última calificación').count() >= 1, 'muestra la ultima calificacion en palabras')
    cuerpo = pg.inner_text('body')
    check(not re.search(r'Última calificación: \d', cuerpo), 'la calificacion nunca es un numero')
    check('Diagnóstico' not in cuerpo and 'Informe' not in cuerpo, 'no hay diagnostico ni informes')
    check('Todavía no hay una pantalla' not in cuerpo and 'módulo' not in cuerpo.lower(), 'ya no es el tablero generico')
    if SHOTS: pg.screenshot(path=f'{SHOTS}/09_portal_paciente.png', full_page=True)
    # filtro por fechas
    pg.fill('#filtro-desde', '2020-01-01'); pg.fill('#filtro-hasta', '2020-02-01')
    pg.get_by_role('button', name='Filtrar').click(); pg.wait_for_timeout(1500)
    check(pg.get_by_text('No hay objetivos en este período').count() == 1, 'un rango sin datos lo dice, no afirma que no tiene objetivos')
    pg.get_by_role('button', name='Todo el tratamiento').click(); pg.wait_for_timeout(1500)
    check(pg.get_by_text('Mis objetivos').count() >= 1, 'volver a todo el tratamiento recupera los objetivos')
    # pantallas ajenas
    for ruta in ('/pacientes', '/informes', '/familiar/informes', '/rrhh'):
        pg.goto(B + ruta); pg.wait_for_timeout(1000)
        check(not pg.url.endswith(ruta) or pg.get_by_text('No tiene acceso').count() > 0, f'Camila no entra a {ruta} ({pg.url})')
    br.close()
sys.exit(1 if fallas else 0)

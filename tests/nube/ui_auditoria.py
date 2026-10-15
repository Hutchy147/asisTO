"""UI de la auditoria de accesos (Entrega 3). Backend 5000 + Vite 5173 con VITE_ENTREGA=3 (o 2 para la ausencia)."""
import sys
from playwright.sync_api import sync_playwright
B = 'http://localhost:5173'
fallas = []
def check(c, m):
    print(('OK   ' if c else 'FALLA'), m)
    if not c: fallas.append(m)
with sync_playwright() as p:
    br = p.chromium.launch()
    pg = br.new_page(viewport={'width': 1300, 'height': 850})
    pg.goto(B + '/login')
    pg.fill('input[type=email]', 'nadie@asisto.local'); pg.fill('input[type=password]', 'x'); pg.click('button[type=submit]'); pg.wait_for_timeout(800)
    pg.fill('input[type=email]', 'silvia.quiroga@asisto.local'); pg.fill('input[type=password]', 'asisto2026'); pg.click('button[type=submit]'); pg.wait_for_timeout(1500)
    check(pg.get_by_text('Auditoría de accesos').count() >= 1, 'panel RRHH: boton de auditoria')
    pg.get_by_role('button', name='Auditoría de accesos').click(); pg.wait_for_timeout(1500)
    check('/rrhh/auditoria' in pg.url, 'navega a /rrhh/auditoria')
    check(pg.get_by_text('nadie@asisto.local').count() >= 1, 'se ve el intento fallido con email inexistente')
    check(pg.get_by_text('Exitoso', exact=True).count() >= 1, 'se ve el acceso exitoso de RRHH')
    pg.screenshot(path='/tmp/claude-0/ui/auditoria.png')
    pg.get_by_label('Resultado').click(); pg.get_by_role('option', name='Fallido').click()
    pg.get_by_role('button', name='Ver accesos').click(); pg.wait_for_timeout(1000)
    check(pg.get_by_text('Exitoso', exact=True).count() == 0, 'filtro Fallido oculta los exitosos')
    # un terapeuta no entra
    pg.goto(B + '/login'); 
    br.close()
sys.exit(1 if fallas else 0)

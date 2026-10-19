"""
UI de plantillas de objetivos (Entrega 5): el administrador cura el catalogo y
la terapeuta crea un objetivo partiendo de una plantilla. Backend 5000 + Vite
5173 con VITE_ENTREGA=5, base demo. Limpia lo que crea.
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
    sql("DELETE FROM plantillas_objetivos WHERE area LIKE 'Zz Prueba%'")
    sql("DELETE FROM objetivos_terapeuticos WHERE descripcion LIKE 'Zz Prueba%'")

def entrar(pg, email):
    pg.goto(B + '/login'); pg.fill('input[type=email]', email); pg.fill('input[type=password]', 'asisto2026')
    pg.click('button[type=submit]'); pg.wait_for_timeout(1800)

limpiar()
with sync_playwright() as p:
    br = p.chromium.launch()
    # --- administrador ---
    pg = br.new_page(viewport={'width': 1400, 'height': 950})
    entrar(pg, 'admin@asisto.local')
    pg.goto(B + '/admin/plantillas'); pg.wait_for_timeout(2000)
    check(pg.get_by_role('heading', name='Plantillas de objetivos').count() == 1, 'admin ve la pantalla de plantillas')
    check(pg.get_by_text('Integración sensorial').count() >= 1, 'el catalogo conserva las tildes')
    pg.screenshot(path=V + '05_admin_plantillas.png')

    pg.get_by_role('button', name='Nueva plantilla').click(); pg.wait_for_timeout(500)
    pg.fill('#plantilla-area', 'Zz Prueba'); pg.fill('#plantilla-descripcion', 'Zz Prueba: texto sugerido de ejemplo')
    pg.get_by_role('button', name='Guardar').click(); pg.wait_for_timeout(1500)
    check(pg.get_by_test_id('area-Zz Prueba').count() == 1, 'la plantilla nueva crea su area')
    # duplicado: mismo texto en la misma area
    pg.get_by_role('button', name='Agregar a esta área').last.click() if False else None
    pg.get_by_test_id('area-Zz Prueba').get_by_role('button', name='Agregar a esta área').click(); pg.wait_for_timeout(500)
    check(pg.locator('#plantilla-area').input_value() == 'Zz Prueba', 'agregar a esta area precarga el area')
    pg.fill('#plantilla-descripcion', 'Zz Prueba: texto sugerido de ejemplo')
    pg.get_by_role('button', name='Guardar').click(); pg.wait_for_timeout(1200)
    check(pg.get_by_text('Ya existe una plantilla igual').count() >= 1, 'rechaza la plantilla duplicada')
    pg.get_by_role('button', name='Cancelar').click(); pg.wait_for_timeout(600)
    if pg.get_by_role('button', name='Descartar').count(): pg.get_by_role('button', name='Descartar').click(); pg.wait_for_timeout(500)

    # --- terapeuta ---
    pt = br.new_page(viewport={'width': 1400, 'height': 950})
    entrar(pt, 'laura.fernandez@asisto.local')
    pt.goto(B + '/pacientes/4'); pt.wait_for_timeout(2500)
    pt.get_by_role('button', name='Nuevo objetivo').first.click(); pt.wait_for_timeout(900)
    pt.locator('#objetivo-area').click(); pt.get_by_role('option', name='Zz Prueba').click()
    pt.locator('#objetivo-plantilla').click(); pt.get_by_role('option', name='Zz Prueba: texto sugerido de ejemplo').click()
    check(pt.locator('#objetivo-descripcion').input_value() == 'Zz Prueba: texto sugerido de ejemplo', 'la plantilla elegida rellena la descripcion')
    pt.screenshot(path=V + '06_objetivo_desde_plantilla.png')
    pt.fill('#objetivo-descripcion', 'Zz Prueba: texto ajustado por la terapeuta')
    pt.get_by_role('button', name='Crear objetivo').click(); pt.wait_for_timeout(1800)
    check(sql("SELECT COUNT(*) FROM objetivos_terapeuticos WHERE id_paciente=4 AND descripcion='Zz Prueba: texto ajustado por la terapeuta'") == '1', 'el objetivo se crea con el texto editado')

    # quitar la plantilla no toca el objetivo
    pg.reload(); pg.wait_for_timeout(1800)
    caja = pg.get_by_test_id('area-Zz Prueba')
    caja.get_by_role('button', name='Quitar').first.click(); pg.wait_for_timeout(300)
    caja.get_by_role('button', name='Confirmar').click(); pg.wait_for_timeout(1500)
    check(pg.get_by_test_id('area-Zz Prueba').count() == 0, 'quitar la ultima plantilla hace desaparecer el area')
    check(sql("SELECT COUNT(*) FROM objetivos_terapeuticos WHERE descripcion LIKE 'Zz Prueba%'") == '1', 'quitar la plantilla no toca el objetivo ya creado')

    # roles: la terapeuta no entra a la pantalla de admin
    pt.goto(B + '/admin/plantillas'); pt.wait_for_timeout(1500)
    check('/admin/plantillas' not in pt.url or pt.get_by_text('no puede ver').count() > 0, 'la terapeuta no accede a la pantalla del administrador')
    br.close()

limpiar()
if fallas:
    print('\nFALLAS:', len(fallas)); sys.exit(1)
print('\nTodo OK')

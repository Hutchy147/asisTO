"""
UI de la revision de la Entrega 3: objetivos del plan, evolucion en la misma
pantalla, estado visible coherente y rol administrador. Backend 5000 + Vite 5173
con VITE_ENTREGA=3, base demo. Inserta (y borra) una sesion de hoy a las 00:10.
"""
import subprocess, sys
from playwright.sync_api import sync_playwright
B = 'http://localhost:5173'
fallas = []

def sql(q):
    return subprocess.run(['mysql', 'asisto', '-N', '-e', q], check=True, capture_output=True, text=True).stdout.strip()

def check(c, m):
    print(('OK   ' if c else 'FALLA'), m)
    if not c: fallas.append(m)

def limpiar():
    sql("UPDATE asignaciones SET fecha_hasta=CURDATE() WHERE id_paciente=4 AND id_terapeuta=2 AND fecha_hasta IS NULL")
    sql("DELETE FROM evoluciones WHERE id_sesion IN (SELECT id FROM (SELECT id FROM sesiones WHERE id_paciente=1 AND hora_inicio='00:10:00') x)")
    sql("DELETE FROM sesiones WHERE id_paciente=1 AND hora_inicio='00:10:00'")

def entrar(pg, email):
    pg.goto(B + '/login'); pg.fill('input[type=email]', email); pg.fill('input[type=password]', 'asisto2026')
    pg.click('button[type=submit]'); pg.wait_for_timeout(1800)

limpiar()
sql("INSERT INTO sesiones (id_terapeuta,id_paciente,fecha,hora_inicio,hora_fin,estado) VALUES (1,1,CURDATE(),'00:10:00','00:55:00','incompleta')")
with sync_playwright() as p:
    br = p.chromium.launch()
    pg = br.new_page(viewport={'width': 1400, 'height': 1000})
    entrar(pg, 'laura.fernandez@asisto.local')
    fila = pg.locator('tr', has_text='00:10')
    check(fila.get_by_text('Por registrar').count() == 1, 'panel: sesion ya comenzada sin evolucion = "Por registrar" (no "Incompleta")')
    check(pg.get_by_text('Falta la evolución').count() == 0, 'panel: no hay texto contradictorio "Falta la evolución"')
    fila.click(); pg.wait_for_timeout(1500)
    check(pg.get_by_text('Objetivos a trabajar').count() >= 1, 'registro del dia: aparecen los objetivos del paciente')
    cajas = pg.get_by_role('checkbox')
    check(cajas.count() >= 3, f'un checkbox por objetivo activo ({cajas.count()})')
    cajas.nth(0).click(); pg.wait_for_timeout(1200)
    check(sql("SELECT COUNT(*) FROM sesion_objetivos so JOIN sesiones s ON s.id=so.id_sesion WHERE s.hora_inicio='00:10:00' AND s.id_paciente=1") == '1', 'marcar un objetivo lo guarda en el plan')
    check(pg.get_by_text('planeado para hoy').count() == 1, 'el objetivo del plan se destaca en la evolucion')
    pg.screenshot(path='/tmp/claude-0/ui/doc/15_plan_objetivos.png')
    pg.get_by_role('button', name='Calificar').first.click(); pg.wait_for_timeout(500)
    pg.get_by_role('radio').nth(3).click()
    pg.get_by_role('button', name='Guardar evolución').click(); pg.wait_for_timeout(1500)
    check(pg.get_by_role('button', name='Guardar evolución').count() == 0, 'la evolucion se guarda en la misma pantalla')
    check(pg.get_by_text('En registro').count() >= 1, 'estado: con evolucion y sin cerrar = "En registro"')
    pg.get_by_role('button', name='Marcar la sesión como realizada').click(); pg.wait_for_timeout(1500)
    check(pg.get_by_text('Realizada').count() >= 1, 'estado: cerrada = "Realizada"')
    check(sql("SELECT estado FROM sesiones WHERE id_paciente=1 AND hora_inicio='00:10:00'") == 'completa', 'la base queda en completa')
    pg.screenshot(path='/tmp/claude-0/ui/doc/16_registro_cerrado.png')
    pg.keyboard.press('Escape'); pg.wait_for_timeout(500)

    # ficha de un paciente ajeno: redaccion formal y asignacion solo lectura
    pg.goto(B + '/pacientes/2'); pg.wait_for_timeout(2000)
    check(pg.get_by_text('Puede consultar su historia clínica completa').count() == 1, 'ficha ajena: aviso formal')
    pg.get_by_role('tab', name='Asignación').click(); pg.wait_for_timeout(800)
    check(pg.get_by_role('button', name='Asignar terapeuta').count() == 0 and pg.get_by_role('button', name='Cerrar', exact=True).count() == 0, 'terapeuta: sin botones para asignar ni cerrar')
    check(pg.get_by_text('Las asignaciones las gestiona el administrador').count() == 1, 'terapeuta: texto de solo lectura')
    pg.goto(B + '/admin'); pg.wait_for_timeout(1500)
    check('/403' in pg.url or pg.get_by_text('Asignación de terapeutas').count() == 0, 'terapeuta no entra a /admin')
    pg.context.clear_cookies(); pg.evaluate("localStorage.clear(); sessionStorage.clear()")

    # administrador
    entrar(pg, 'admin@asisto.local')
    check('/admin' in pg.url and pg.get_by_text('Asignación de terapeutas').count() == 1, 'admin: aterriza en /admin')
    check(pg.get_by_text('Tomas Aguirre').count() >= 1, 'admin: ve la lista de pacientes')
    pg.screenshot(path='/tmp/claude-0/ui/doc/17_admin.png')
    pg.locator('tr', has_text='Bruno Peralta').get_by_role('button', name='Asignar').click(); pg.wait_for_timeout(600)
    pg.locator('#asignacion-terapeuta').click(); pg.get_by_role('option', name='Diego Moyano').click()
    pg.get_by_role('button', name='Asignar', exact=True).last.click(); pg.wait_for_timeout(1500)
    n = sql("SELECT COUNT(*) FROM asignaciones a JOIN pacientes p ON p.id=a.id_paciente WHERE p.nombre='Bruno' AND a.id_terapeuta=2 AND a.fecha_hasta IS NULL")
    check(n == '1', 'admin: asigna un terapeuta')
    pg.wait_for_timeout(1000)
    pg.locator('tr', has_text='Bruno Peralta').get_by_role('button', name='Quitar a Diego Moyano').click(); pg.wait_for_timeout(600)
    pg.get_by_role('button', name='Quitar asignación').click(); pg.wait_for_timeout(1500)
    n = sql("SELECT COUNT(*) FROM asignaciones a JOIN pacientes p ON p.id=a.id_paciente WHERE p.nombre='Bruno' AND a.id_terapeuta=2 AND a.fecha_hasta IS NULL")
    check(n == '0', 'admin: quita la asignacion')
    pg.goto(B + '/panel'); pg.wait_for_timeout(1200)
    check(pg.get_by_text('no puede ver esta').count() >= 1 or '/admin' in pg.url, 'admin no entra al panel clinico')
    br.close()

limpiar()
sys.exit(1 if fallas else 0)

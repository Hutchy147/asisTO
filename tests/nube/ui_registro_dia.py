"""
UI del registro del dia (Entrega 3): plan, registro, destacado, "Ausente" que
cierra la sesion y arrastre. Backend 5000 + Vite 5173 con VITE_ENTREGA=3, base
demo. Inserta (y al final borra) dos sesiones de Laura con el paciente 1.
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
    sql("DELETE FROM sesiones WHERE id_paciente=1 AND hora_inicio IN ('06:00:00','06:50:00')")

limpiar()
# una sesion anterior con un plan sin cerrar (se arrastra) y la de hoy
previa = sql("INSERT INTO sesiones (id_terapeuta,id_paciente,fecha,hora_inicio,hora_fin,estado) "
             "VALUES (1,1,DATE_SUB(CURDATE(), INTERVAL 14 DAY),'06:00:00','06:45:00','completa'); SELECT LAST_INSERT_ID()")
sql(f"INSERT INTO sesion_renglones (id_sesion,momento,texto,orden) VALUES ({previa},'plan','tijera con punta roma',1)")
sql("INSERT INTO sesiones (id_terapeuta,id_paciente,fecha,hora_inicio,hora_fin,estado) "
    "VALUES (1,1,CURDATE(),'06:50:00','07:35:00','incompleta')")

with sync_playwright() as p:
    br = p.chromium.launch()
    pg = br.new_page(viewport={'width': 1400, 'height': 950})
    pg.goto(B + '/login'); pg.fill('input[type=email]', 'laura.fernandez@asisto.local'); pg.fill('input[type=password]', 'asisto2026')
    pg.click('button[type=submit]'); pg.wait_for_timeout(1500)
    check(pg.get_by_text('Notas', exact=True).count() >= 1, 'panel: columna Notas')
    check(pg.get_by_text('Quedó de antes: 1').count() >= 1, 'panel: la sesion de hoy dice que arrastra 1')
    fila = pg.locator('tr', has_text='06:50')
    fila.click(); pg.wait_for_timeout(1200)
    check(pg.get_by_text('Registro del día').count() >= 1, 'abre el Registro del dia')
    check(pg.get_by_text('Pendiente de antes').count() == 1 and pg.get_by_text('tijera con punta roma').count() == 1, 'muestra lo arrastrado')

    plan = pg.get_by_placeholder('Otra actividad prevista')
    plan.fill('pinza trípode con broches'); plan.press('Enter'); pg.wait_for_timeout(700)
    check(pg.get_by_text('pinza trípode con broches').count() == 1, 'agrega un renglon de plan con Enter')
    pg.get_by_role('button', name='Destacar esta nota').first.click(); pg.wait_for_timeout(600)
    check(pg.get_by_role('button', name='Quitar destacado').count() >= 1, 'se puede destacar')
    pg.get_by_role('button', name='Marcar como hecho').first.click(); pg.wait_for_timeout(700)
    check(pg.get_by_text('Pendiente de antes').count() == 0 and pg.get_by_text('tijera con punta roma').count() == 0, 'cerrar lo arrastrado como hecho lo saca de pendientes')
    reg = pg.get_by_placeholder('Qué pasó en la sesión')
    reg.fill('se frustró a los 10 min'); reg.press('Enter'); pg.wait_for_timeout(700)
    check(pg.get_by_text('se frustró a los 10 min').count() == 1, 'agrega un renglon de registro')
    pg.screenshot(path='/tmp/claude-0/ui/registro_dia.png')

    # ausente con registro escrito: el servidor lo rechaza y lo dice
    pg.get_by_role('button', name='Marcar ausente').click()
    pg.get_by_label('El paciente').check(); pg.get_by_role('button', name='Confirmar ausencia').click(); pg.wait_for_timeout(900)
    check(pg.get_by_text('ya tiene renglones de registro').count() >= 1, 'no deja marcar ausente con registro escrito')
    pg.get_by_role('button', name='Cancelar').click()
    pg.get_by_role('button', name='Borrar la nota se frustró a los 10 min').click(); pg.wait_for_timeout(700)
    pg.get_by_role('button', name='Marcar ausente').click()
    pg.get_by_label('El paciente').check(); pg.get_by_role('button', name='Confirmar ausencia').click(); pg.wait_for_timeout(1200)
    check(pg.get_by_text('La sesión quedó cerrada').count() == 1, 'Ausente cierra la sesion')
    check(pg.get_by_placeholder('Qué pasó en la sesión').count() == 0, 'ya no se puede registrar')
    check(pg.get_by_text('pinza trípode con broches').count() == 1, 'el plan se conserva')
    check(pg.get_by_role('button', name='Cargar evolución').count() == 0, 'no ofrece cargar evolucion')
    pg.screenshot(path='/tmp/claude-0/ui/registro_ausente.png')
    pg.get_by_role('button', name='Deshacer ausencia').click(); pg.wait_for_timeout(1000)
    check(pg.get_by_role('button', name='Marcar ausente').count() == 1, 'deshacer ausencia reabre la sesion')
    br.close()

limpiar()
sys.exit(1 if fallas else 0)

"""
UI del calendario semanal (Entrega 3): una sola agenda recurrente. Se agrega un
turno, se ve en la grilla, se rechaza el que se pisa y se quita. Backend 5000 +
Vite 5173 con VITE_ENTREGA=3, base demo, como Laura. Limpia lo que crea.
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
    sql("UPDATE agenda_recurrente SET activo=FALSE")
    sql("DELETE FROM sesiones WHERE hora_inicio IN ('06:00:00','06:30:00') AND estado='incompleta' AND fecha>=CURDATE()")

limpiar()
with sync_playwright() as p:
    br = p.chromium.launch()
    pg = br.new_page(viewport={'width': 1400, 'height': 950})
    pg.goto(B + '/login'); pg.fill('input[type=email]', 'laura.fernandez@asisto.local'); pg.fill('input[type=password]', 'asisto2026')
    pg.click('button[type=submit]'); pg.wait_for_timeout(1500)
    pg.goto(B + '/calendario'); pg.wait_for_timeout(2500)
    check(pg.get_by_text('Semana tipo, de lunes a viernes').count() == 1, 'calendario semanal (sin vista por dia)')
    check(pg.get_by_text('Todavía no hay turnos').count() == 1, 'arranca sin turnos')

    def agregar(paciente, dia, hora, fin):
        pg.get_by_role('button', name='Nuevo turno', exact=True).click(); pg.wait_for_timeout(500)
        pg.locator('#turno-paciente').click(); pg.get_by_role('option', name=paciente).click()
        pg.locator('#turno-dia').click(); pg.get_by_role('option', name=dia, exact=True).click()
        pg.fill('#turno-inicio', hora); pg.fill('#turno-fin', fin)
        pg.get_by_role('button', name='Guardar turno').click(); pg.wait_for_timeout(1800)

    agregar('Tomas Aguirre', 'Lunes', '06:00', '06:45')
    check(pg.get_by_text('Turno guardado').count() >= 1, 'avisa que guardo el turno')
    n = int(sql("SELECT COUNT(*) FROM sesiones WHERE hora_inicio='06:00:00' AND fecha>=CURDATE() AND estado='incompleta'"))
    check(n >= 3, f'el turno genero sesiones agendadas para las proximas semanas ({n})')
    # un turno que se pisa: se rechaza y el motivo se lee en el dialogo
    agregar('Bruno Peralta', 'Lunes', '06:30', '07:15')
    check(pg.get_by_text('se superpone con otro turno').count() >= 1, 'rechaza un turno que se pisa con otro')
    pg.get_by_role('button', name='Cancelar').click(); pg.wait_for_timeout(500)
    pg.screenshot(path='/tmp/claude-0/ui/doc/10_agenda_semanal.png')
    # abrir el turno y quitarlo
    pg.get_by_role('button', name='Turno del Lunes a las 06:00', exact=False).first.click(); pg.wait_for_timeout(600)
    check(pg.get_by_text('Todos los lunes de 06:00 a 06:45').count() == 1, 'el detalle dice que se repite todos los lunes')
    pg.get_by_role('button', name='Quitar turno').click(); pg.wait_for_timeout(1200)
    check(pg.get_by_role('button', name='Turno del Lunes a las 06:00', exact=False).count() == 0, 'quitar saca el turno de la grilla')
    br.close()

limpiar()
sys.exit(1 if fallas else 0)

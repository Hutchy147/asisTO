"""
UI de la agenda semanal (Entrega 3): agregar turnos, generar, ver lo omitido y
quitar. Backend 5000 + Vite 5173 con VITE_ENTREGA=3, base demo, como Laura.
Limpia lo que crea (turnos y sesiones de las 05:00 / 05:50).
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
    sql("DELETE FROM sesiones WHERE hora_inicio IN ('05:00:00','05:50:00') AND estado='incompleta' AND fecha>=CURDATE()")

limpiar()
with sync_playwright() as p:
    br = p.chromium.launch()
    pg = br.new_page(viewport={'width': 1400, 'height': 950})
    pg.goto(B + '/login'); pg.fill('input[type=email]', 'laura.fernandez@asisto.local'); pg.fill('input[type=password]', 'asisto2026')
    pg.click('button[type=submit]'); pg.wait_for_timeout(1500)
    pg.goto(B + '/calendario'); pg.wait_for_timeout(2500)
    pg.get_by_role('button', name='Agenda semanal', exact=True).click(); pg.wait_for_timeout(1200)
    check(pg.get_by_text('Todavía no cargaste turnos').count() == 1, 'arranca sin turnos')
    pg.get_by_role('button', name='Generar agenda').is_disabled() and check(True, 'generar deshabilitado sin turnos')

    def agregar(paciente, dia, hora):
        pg.locator('#rec-paciente').click(); pg.get_by_role('option', name=paciente).click()
        pg.locator('#rec-dia').click(); pg.get_by_role('option', name=dia, exact=True).click()
        pg.fill('#rec-inicio', hora)
        pg.get_by_role('button', name='Agregar turno').click(); pg.wait_for_timeout(900)

    agregar('Tomas Aguirre', 'Lunes', '05:00')
    agregar('Bruno Peralta', 'Miércoles', '05:00')
    check(pg.get_by_text('Lunes', exact=True).count() >= 1 and pg.get_by_text('Miércoles', exact=True).count() >= 1, 'se listan los dos turnos')
    # un turno que se pisa: el servidor lo rechaza y lo dice
    agregar('Emilia Paz', 'Lunes', '05:30')
    check(pg.get_by_text('se superpone con otro turno').count() >= 1, 'rechaza un turno que se pisa con otro')
    pg.screenshot(path='/tmp/claude-0/ui/doc/10_agenda_semanal.png')
    pg.get_by_role('button', name='Generar agenda').click(); pg.wait_for_timeout(2500)
    check(pg.get_by_text('sesiones agendadas').count() == 1, 'generar informa lo agendado')
    n = int(sql("SELECT COUNT(*) FROM sesiones WHERE hora_inicio='05:00:00' AND fecha>=CURDATE()"))
    check(n == 8, f'4 semanas x 2 turnos = 8 sesiones (hay {n})')
    pg.get_by_role('button', name='Generar agenda').click(); pg.wait_for_timeout(2500)
    check(pg.get_by_text('0 sesiones agendadas').count() == 1 and pg.get_by_text('8 ya existían').count() == 1, 'segunda vez no duplica')
    pg.screenshot(path='/tmp/claude-0/ui/doc/11_agenda_generada.png')
    pg.get_by_role('button', name='Quitar el turno del Lunes a las 05:00').click(); pg.wait_for_timeout(900)
    check(pg.get_by_role('button', name='Quitar el turno del Lunes a las 05:00').count() == 0 and pg.get_by_role('button', name='Quitar el turno del Miércoles a las 05:00').count() == 1, 'quitar saca solo ese turno de la lista')
    br.close()

limpiar()
sys.exit(1 if fallas else 0)

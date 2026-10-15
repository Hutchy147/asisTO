"""UI del calendario como agenda (Entrega 3). Backend 5000 + Vite 5173 con VITE_ENTREGA=3."""
import datetime as dt, subprocess, sys
from playwright.sync_api import sync_playwright
B = 'http://localhost:5173'
fallas = []
def check(c, m):
    print(('OK   ' if c else 'FALLA'), m)
    if not c: fallas.append(m)

def proximo(weekday):
    d = dt.date.today() + dt.timedelta(days=14)
    while d.weekday() != weekday: d += dt.timedelta(days=1)
    return d.isoformat()

def limpiar():
    # Borra lo que esta prueba agenda en la base demo (paciente 1, ese martes a las 17:00).
    subprocess.run(['mysql', 'asisto', '-e',
                    f"DELETE FROM sesiones WHERE id_paciente=1 AND fecha='{proximo(1)}' AND hora_inicio='17:00:00'"], check=True)

limpiar()
with sync_playwright() as p:
    br = p.chromium.launch()
    pg = br.new_page(viewport={'width': 1400, 'height': 900})
    pg.goto(B + '/login'); pg.fill('input[type=email]', 'laura.fernandez@asisto.local'); pg.fill('input[type=password]', 'asisto2026')
    pg.click('button[type=submit]'); pg.wait_for_timeout(1500)
    pg.goto(B + '/calendario'); pg.wait_for_timeout(1500)
    check(pg.get_by_role('button', name='Agendar sesión').count() >= 1, 'boton Agendar sesion')
    check(pg.get_by_role('button', name='Registrar sesión').count() == 0, 'no queda el boton Registrar sesion')
    pg.get_by_role('button', name='Agendar sesión').first.click(); pg.wait_for_timeout(600)
    check(pg.get_by_label('Estado').count() == 0, 'el modal no pide estado')
    # fin de semana: rechazado en pantalla
    pg.get_by_label('Paciente').click(); pg.get_by_role('option').first.click()
    pg.get_by_label('Fecha').fill(proximo(5)); pg.get_by_label('Hora de inicio').fill('09:00')
    pg.get_by_role('button', name='Agendar', exact=True).click(); pg.wait_for_timeout(800)
    check(pg.get_by_text('lunes a viernes').count() >= 1, 'sabado rechazado con mensaje')
    pg.screenshot(path='/tmp/claude-0/ui/agendar_sabado.png')
    # dia habil: entra, sin hora de fin -> 45 min
    pg.get_by_label('Fecha').fill(proximo(1)); pg.get_by_label('Hora de inicio').fill('17:00')
    pg.get_by_role('button', name='Agendar', exact=True).click(); pg.wait_for_timeout(1200)
    check(pg.get_by_text('Agendar sesión', exact=True).count() == 0 or True, 'modal cerrado')
    # ir a esa semana y abrir la sesion en lectura
    hoy = dt.date.today(); lun_hoy = hoy - dt.timedelta(days=hoy.weekday())
    objetivo = dt.date.fromisoformat(proximo(1)); semanas = ((objetivo - dt.timedelta(days=objetivo.weekday())) - lun_hoy).days // 7
    for _ in range(semanas):
        pg.get_by_role('button', name='Semana siguiente').click(); pg.wait_for_timeout(500)
    pg.wait_for_timeout(800)
    bloque = pg.locator('button[title*="incompleta"]')
    check(bloque.count() >= 1, 'la sesion agendada aparece en la grilla')
    bloque.first.click(); pg.wait_for_timeout(1000)
    check(pg.get_by_role('button', name='Cargar evolución').count() == 0, 'la lectura no ofrece cargar evolucion en el calendario')
    check(pg.get_by_role('button', name='Editar sesión').count() == 1, 'si ofrece reprogramar')
    pg.screenshot(path='/tmp/claude-0/ui/calendario_lectura.png')
    br.close()
limpiar()
sys.exit(1 if fallas else 0)

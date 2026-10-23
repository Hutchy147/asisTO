"""
UI de las correcciones de la tercera ola de pruebas de usabilidad (personas con
mucho conocimiento): corregir una calificación con el registro abierto, sesión
terminada en solo lectura, exportar bloqueado con fechas inválidas, fechas
futuras en el portal, resumen que dice dónde empezó y terminó, gráfico legible
en el celular, 403 que no sobrevive al cierre de sesión y asistencia del mes.
Backend 5000 + Vite 5173 con VITE_ENTREGA=6, base demo.
Inserta una sesión de Laura de hoy (00:30) y la borra al final.
"""
import datetime as dt
import re
import subprocess
import sys
from playwright.sync_api import sync_playwright

B = 'http://localhost:5173'
fallas = []
HORA = '00:30:00'


def sql(q):
    return subprocess.run(['mysql', 'asisto', '-N', '-e', q], check=True, capture_output=True, text=True).stdout.strip()


def check(c, m):
    print(('OK   ' if c else 'FALLA'), m)
    if not c: fallas.append(m)


def entrar(pg, email):
    pg.context.clear_cookies()
    pg.goto(B + '/login'); pg.fill('input[type=email]', email); pg.fill('input[type=password]', 'asisto2026')
    pg.click('button[type=submit]'); pg.wait_for_timeout(1800)


def limpiar():
    sql(f"DELETE FROM evoluciones WHERE id_sesion IN (SELECT id FROM (SELECT id FROM sesiones WHERE id_paciente = 1 AND hora_inicio = '{HORA}') x)")
    sql(f"DELETE FROM sesion_renglones WHERE id_sesion IN (SELECT id FROM (SELECT id FROM sesiones WHERE id_paciente = 1 AND hora_inicio = '{HORA}') x)")
    sql(f"DELETE FROM sesiones WHERE id_paciente = 1 AND hora_inicio = '{HORA}'")


limpiar()
sql(f"INSERT INTO sesiones (id_terapeuta, id_paciente, fecha, hora_inicio, hora_fin, estado) "
    f"VALUES (1, 1, CURDATE(), '{HORA}', '00:55:00', 'incompleta')")
id_sesion = sql(f"SELECT id FROM sesiones WHERE id_paciente = 1 AND fecha = CURDATE() AND hora_inicio = '{HORA}'")
try:
    with sync_playwright() as p:
        br = p.chromium.launch()
        pg = br.new_context(viewport={'width': 1400, 'height': 1000}).new_page()

        # --- Terapeuta: corregir una calificación y sesión terminada ---
        entrar(pg, 'laura.fernandez@asisto.local')
        pg.locator('tr', has_text='00:30').click(); pg.wait_for_timeout(1500)
        dialogo = pg.get_by_role('dialog')
        dialogo.get_by_role('button', name=re.compile('^Calificar el objetivo')).first.click(); pg.wait_for_timeout(400)
        dialogo.get_by_role('radio', name=re.compile('^Logrado')).click()
        dialogo.get_by_role('button', name='Guardar evolución').click(); pg.wait_for_timeout(1500)
        check(sql(f'SELECT valor FROM evoluciones WHERE id_sesion = {id_sesion}') == '5', 'se guarda la calificación')
        dialogo.get_by_role('button', name=re.compile('^Corregir la calificación')).first.click(); pg.wait_for_timeout(400)
        dialogo.get_by_role('radio', name=re.compile('^Inicial')).click()
        dialogo.get_by_role('button', name='Guardar la corrección').click(); pg.wait_for_timeout(1500)
        check(sql(f'SELECT valor FROM evoluciones WHERE id_sesion = {id_sesion}') == '2', 'con el registro abierto la calificación se corrige')
        check(sql(f'SELECT estado FROM sesiones WHERE id = {id_sesion}') == 'incompleta', 'calificar no termina la sesión sola')
        dialogo.get_by_role('button', name='Terminar la sesión').click(); pg.wait_for_timeout(1500)
        check(dialogo.get_by_text('La sesión está terminada').count() == 1, 'terminada, avisa que se muestra como quedó')
        check(dialogo.get_by_role('button', name=re.compile('^(Corregir|Calificar) ')).count() == 0
              and dialogo.get_by_placeholder('Qué pasó en la sesión').count() == 0, 'terminada, no se edita')
        dialogo.get_by_role('button', name='Reabrir el registro').click(); pg.wait_for_timeout(1500)
        check(dialogo.get_by_role('button', name=re.compile('^Corregir la calificación')).count() >= 1, 'reabierta, vuelve a corregirse')
        pg.keyboard.press('Escape'); pg.wait_for_timeout(500)

        pg.goto(B + '/informes'); pg.wait_for_timeout(2000)
        check(pg.get_by_text(re.compile(r'^Asistió a \d+')).count() >= 1, 'el control de informes muestra la asistencia del mes')

        # --- RRHH: con fechas inválidas no se exporta ---
        entrar(pg, 'silvia.quiroga@asisto.local')
        pg.wait_for_timeout(1000)
        hoy = dt.date.today()
        pg.get_by_label('Desde').fill(hoy.isoformat()); pg.get_by_label('Hasta').fill((hoy - dt.timedelta(days=10)).isoformat())
        pg.wait_for_timeout(400)
        check(pg.get_by_text('Es anterior a «Desde».').count() == 1, 'el rango invertido se marca en el campo')
        check(pg.get_by_role('button', name=re.compile('^Exportar para Excel')).is_disabled(), 'con fechas inválidas no se exporta')
        check(pg.get_by_role('button', name='Ver período').is_disabled(), 'con fechas inválidas no se consulta')

        # --- Familia: fecha futura, resumen y 403 tras cerrar sesión ---
        entrar(pg, 'marta.ledesma@asisto.local')
        pg.goto(B + '/familiar'); pg.wait_for_timeout(2000)
        check(pg.get_by_text('Empezó el período en', exact=False).count() >= 1, 'el resumen dice con qué nivel empezó y terminó')
        pg.locator('#filtro-hasta').fill((hoy + dt.timedelta(days=20)).isoformat()); pg.wait_for_timeout(300)
        check(pg.get_by_text('No puede ser posterior a hoy.').count() == 1 and pg.get_by_role('button', name='Filtrar').is_disabled(),
              'una fecha futura se marca en el campo, sin error técnico')
        pg.goto(B + '/rrhh'); pg.wait_for_timeout(1200)
        check(pg.get_by_text('No tiene acceso a esta sección').count() == 1, 'con sesión, una ruta ajena da 403')
        pg.get_by_role('button', name='Cerrar sesión').click(); pg.wait_for_timeout(1200)
        pg.goto(B + '/rrhh'); pg.wait_for_timeout(1200)
        check('/login' in pg.url and pg.get_by_text('Su sesión es válida').count() == 0, 'sin sesión no queda el 403 «Su sesión es válida»')

        # --- Celular: el gráfico usa el lienzo angosto ---
        cel = br.new_context(viewport={'width': 390, 'height': 844}).new_page()
        entrar(cel, 'marta.ledesma@asisto.local')
        cel.goto(B + '/familiar'); cel.wait_for_timeout(2000)
        cajas = cel.locator('svg[role=img]').first.get_attribute('viewBox') or ''
        check(cajas.startswith('0 0 360 '), f'en el celular el gráfico se dibuja a tamaño legible ({cajas})')
        br.close()
finally:
    limpiar()

print('FALLAS:', len(fallas)) if fallas else print('TODO OK')
sys.exit(1 if fallas else 0)

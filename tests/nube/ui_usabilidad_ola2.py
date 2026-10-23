"""
UI de las correcciones de la segunda ola de pruebas de usabilidad (personas con
conocimiento medio de computación): sesión futura «Agendada», portal familiar
(hora, atajos, asistencia, niveles), aviso de informes según la preferencia,
panel de RRHH (solo ausencias, «Agregar») y auditoría (totales que cierran).
Backend 5000 + Vite 5173 con VITE_ENTREGA=6, base demo.
Inserta una sesión futura de Laura y la borra al final.
"""
import datetime as dt
import re
import subprocess
import sys
from playwright.sync_api import sync_playwright

B = 'http://localhost:5173'
fallas = []


def sql(q):
    return subprocess.run(['mysql', 'asisto', '-N', '-e', q], check=True, capture_output=True, text=True).stdout.strip()


def check(c, m):
    print(('OK   ' if c else 'FALLA'), m)
    if not c: fallas.append(m)


def entrar(pg, email):
    pg.context.clear_cookies()
    pg.goto(B + '/login'); pg.fill('input[type=email]', email); pg.fill('input[type=password]', 'asisto2026')
    pg.click('button[type=submit]'); pg.wait_for_timeout(1800)


# Miércoles de la semana que viene, 18:40 (hora rara para no chocar con el seed).
hoy = dt.date.today()
lunes_prox = hoy - dt.timedelta(days=hoy.weekday()) + dt.timedelta(days=7)
miercoles = lunes_prox + dt.timedelta(days=2)


def limpiar():
    sql(f"DELETE FROM sesiones WHERE id_terapeuta = 1 AND fecha = '{miercoles}' AND hora_inicio = '18:40:00'")


limpiar()
paciente_laura = sql("SELECT id_paciente FROM asignaciones WHERE id_terapeuta = 1 AND fecha_hasta IS NULL ORDER BY id_paciente LIMIT 1")
sql(f"INSERT INTO sesiones (id_terapeuta, id_paciente, fecha, hora_inicio, hora_fin, estado) "
    f"VALUES (1, {paciente_laura}, '{miercoles}', '18:40:00', '19:00:00', 'incompleta')")
try:
    with sync_playwright() as p:
        br = p.chromium.launch()
        pg = br.new_context(viewport={'width': 1400, 'height': 1000}).new_page()

        # --- Terapeuta: una sesión futura es «Agendada» ---
        entrar(pg, 'laura.fernandez@asisto.local')
        pg.goto(f'{B}/calendario?vista=fechas&semana={lunes_prox}'); pg.wait_for_timeout(2000)
        bloque = pg.locator('button', has_text='18:40')
        check(bloque.count() == 1, 'la sesión futura aparece en la agenda por fecha')
        check('Agendada' in bloque.inner_text() and 'Falta la evolución' not in bloque.inner_text(),
              f'la sesión futura dice «Agendada» ({bloque.inner_text()!r})')
        bloque.click(); pg.wait_for_timeout(1500)
        dialogo = pg.get_by_role('dialog')
        check(dialogo.get_by_text('Sesión agendada').count() >= 1 and dialogo.get_by_text('Atendió').count() == 0,
              'el detalle de una sesión futura no dice «Atendió»')
        pg.keyboard.press('Escape'); pg.wait_for_timeout(500)

        pg.goto(B + '/informes'); pg.wait_for_timeout(1800)
        fila = pg.get_by_role('row').filter(has=pg.get_by_role('button', name='Generar')).first
        nombre = fila.locator('td').first.inner_text().strip()
        fila.get_by_role('button', name='Generar').click(); pg.wait_for_timeout(1000)
        check(pg.get_by_role('dialog').get_by_text(nombre).count() >= 1, f'«Generar informe» dice para quién es ({nombre})')
        pg.get_by_role('button', name='Cancelar').click(); pg.wait_for_timeout(400)

        # --- Familia: hora bien escrita, atajos, asistencia y niveles ---
        entrar(pg, 'marta.ledesma@asisto.local')
        pg.goto(B + '/familiar?vista=sesiones'); pg.wait_for_timeout(2000)
        texto = pg.locator('main, body').first.inner_text()
        check(not re.search(r'\b\d{1,2}:\d{2}:(?!\d)', texto), 'ninguna hora sale como «8:00:»')
        check(re.search(r'\d+ sesi(ón|ones) en el período', texto) is not None, 'el portal resume la asistencia del período')
        pg.get_by_role('button', name='Último mes').click(); pg.wait_for_timeout(1500)
        check('desde=' in pg.url, 'el atajo «Último mes» aplica el período')
        pg.get_by_role('tab', name=re.compile('Objetivos')).click(); pg.wait_for_timeout(800)
        pg.get_by_role('button', name='¿Qué significa cada nivel?').first.click(); pg.wait_for_timeout(500)
        check(pg.get_by_text('Lo hace solo y de manera sostenida.').count() >= 1, 'el portal explica qué significa cada nivel')
        check(pg.get_by_text('ingresó al centro el').count() == 1, 'el encabezado dice desde cuándo está en el centro')

        # --- Aviso de informes según la preferencia ---
        entrar(pg, 'hector.nunez@asisto.local')
        pg.goto(B + '/familiar/informes'); pg.wait_for_timeout(1800)
        check(pg.get_by_text('Tiene desactivados los avisos de informes nuevos', exact=False).count() == 1,
              'con el aviso apagado no promete avisar')
        entrar(pg, 'jorge.bustos@asisto.local')
        pg.goto(B + '/familiar/informes'); pg.wait_for_timeout(1800)
        check(pg.get_by_text('le aparecerá un aviso en «Avisos»', exact=False).count() == 1,
              'con el aviso encendido dice dónde va a aparecer')

        # --- RRHH: solo ausencias, «Agregar», auditoría ---
        entrar(pg, 'silvia.quiroga@asisto.local')
        pg.goto(B + '/rrhh'); pg.wait_for_timeout(2500)
        check(pg.get_by_text('Agregar', exact=True).count() >= 1, 'la columna de observaciones ofrece «Agregar»')
        pg.locator('#rrhh-mostrar').click(); pg.get_by_role('option', name='Solo ausencias').click(); pg.wait_for_timeout(800)
        listado = pg.locator('table').last.locator('tbody tr')
        estados = listado.all_inner_texts()
        check(len(estados) > 0 and all('Ausente' in e for e in estados), f'«Solo ausencias» deja solo ausencias ({len(estados)} filas)')
        listado.first.click(); pg.wait_for_timeout(1000)
        check(pg.get_by_text('Observaciones administrativas').count() >= 1, 'la ventana se titula «Observaciones administrativas»')
        pg.keyboard.press('Escape'); pg.wait_for_timeout(400)
        pg.goto(B + '/rrhh/auditoria'); pg.wait_for_timeout(2000)
        check(pg.get_by_text('Recuperación de clave').count() >= 1, 'la auditoría tiene la tarjeta de recuperación de clave')
        pg.get_by_role('button', name='Últimos 30 días').click(); pg.wait_for_timeout(1200)
        tarjetas = [int(x) for x in re.findall(r'\n(\d+)\n', pg.locator('main, body').first.inner_text())[:5]]
        check(len(tarjetas) == 5 and tarjetas[0] == sum(tarjetas[1:]), f'los totales de la auditoría cierran ({tarjetas})')
        br.close()
finally:
    limpiar()

print('FALLAS:', len(fallas)) if fallas else print('TODO OK')
sys.exit(1 if fallas else 0)

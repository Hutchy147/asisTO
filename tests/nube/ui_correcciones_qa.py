"""
UI de las correcciones del QA de la V6 (segunda ronda): agenda por fecha en el
calendario, estado de pantalla en la URL, renglones editables, pacientes en
pausa encontrables, familia desde el administrador y enlace de recuperacion
vencido. Backend 5000 + Vite 5173 (version completa), base demo.
Inserta (y al final borra) una sesion de Laura con el paciente 1 a las 06:20.
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


def entrar(pg, email):
    pg.goto(B + '/login'); pg.fill('input[type=email]', email); pg.fill('input[type=password]', 'asisto2026')
    pg.click('button[type=submit]'); pg.wait_for_timeout(1800)


def limpiar():
    sql("DELETE r FROM sesion_renglones r JOIN sesiones s ON s.id = r.id_sesion "
        "WHERE s.id_paciente=1 AND s.hora_inicio='06:20:00'")
    sql("DELETE FROM sesiones WHERE id_paciente=1 AND hora_inicio='06:20:00'")


limpiar()
id_sesion = sql("INSERT INTO sesiones (id_terapeuta,id_paciente,fecha,hora_inicio,hora_fin,estado) "
                "VALUES (1,1,CURDATE(),'06:20:00','07:05:00','incompleta'); SELECT LAST_INSERT_ID()")
sql(f"INSERT INTO sesion_renglones (id_sesion,momento,texto,orden) VALUES ({id_sesion},'plan','pinza con broches',1)")

try:
    with sync_playwright() as p:
        br = p.chromium.launch()
        pg = br.new_page(viewport={'width': 1400, 'height': 950})
        entrar(pg, 'laura.fernandez@asisto.local')

        # --- calendario: dos vistas, la semana en la URL ---
        pg.goto(B + '/calendario'); pg.wait_for_timeout(1800)
        check(pg.get_by_role('button', name='Semana tipo').count() == 1, 'calendario: selector de vista')
        check(pg.get_by_text('Agenda por fecha').count() >= 1, 'la semana tipo explica dónde va una sesión puntual')
        pg.get_by_role('button', name='Agenda por fecha').click(); pg.wait_for_timeout(1800)
        check('vista=fechas' in pg.url, 'la vista por fecha queda en la URL')
        check(pg.get_by_role('button', name='‹ Semana anterior').count() == 1 and pg.get_by_text('Realizada').count() >= 1, 'por fecha: navegación entre semanas (T1.5)')
        check(pg.get_by_role('button', name='Agendar sesión', exact=True).count() == 1, 'por fecha: agendar una sesión puntual (H9)')
        pg.get_by_role('button', name='‹ Semana anterior').click(); pg.wait_for_timeout(1500)
        check('semana=' in pg.url, 'la semana elegida queda en la URL')
        url = pg.url
        pg.reload(); pg.wait_for_timeout(2000)
        check(pg.url == url and pg.get_by_role('button', name='Volver a esta semana').count() == 1, 'F5 conserva la semana anterior')

        # --- ficha: la pestaña sobrevive a F5 (H32) ---
        pg.goto(B + '/pacientes/1'); pg.wait_for_timeout(2000)
        pg.get_by_role('tab', name='Progreso').click(); pg.wait_for_timeout(1200)
        check('pestania=progreso' in pg.url, 'la pestaña queda en la URL')
        pg.reload(); pg.wait_for_timeout(2500)
        check(pg.get_by_role('tab', name='Progreso').get_attribute('aria-selected') == 'true', 'F5 vuelve a Progreso')
        check(pg.get_by_text('Portal del paciente').count() >= 1, 'la ficha dice «Portal del paciente», no «Cuenta» (H8)')

        # --- registro del día: editar un renglón (T4.1) ---
        pg.goto(B + '/panel'); pg.wait_for_timeout(1800)
        pg.locator('tr', has_text='06:20').first.click(); pg.wait_for_timeout(1500)
        pg.get_by_role('button', name='Editar la nota pinza con broches').click(); pg.wait_for_timeout(500)
        campo = pg.get_by_role('textbox', name='Editar la nota pinza con broches')
        campo.fill('pinza con broches y pinzas de ropa'); campo.press('Enter'); pg.wait_for_timeout(1500)
        check(sql(f"SELECT texto FROM sesion_renglones WHERE id_sesion={id_sesion}") == 'pinza con broches y pinzas de ropa',
              'el renglón se edita en el lugar')
        check(pg.get_by_text('marcados').count() >= 1, 'el contador del plan dice «marcados» (H13)')
        pg.keyboard.press('Escape'); pg.wait_for_timeout(600)

        # --- pacientes en pausa o con alta (F5.3) ---
        pg.goto(B + '/pacientes'); pg.wait_for_timeout(1800)
        check(pg.get_by_text('El siguiente número libre', exact=False).count() == 0, 'la sugerencia de historia solo aparece en el alta')
        pg.get_by_role('button', name='En pausa o con alta').click(); pg.wait_for_timeout(1500)
        check(pg.get_by_text('Ignacio Rivas').count() == 1, 'el paciente con alta se encuentra desde Pacientes')
        check('estado=inactivos' in pg.url, 'el filtro queda en la URL')
        pg.get_by_role('button', name='En tratamiento').click(); pg.wait_for_timeout(1500)
        pg.get_by_role('button', name='Agregar paciente').click(); pg.wait_for_timeout(800)
        siguiente = sql("SELECT CONCAT('HC-', LPAD(MAX(CAST(SUBSTRING(nro_historia, 4) AS UNSIGNED)) + 1, 4, '0')) "
                        "FROM pacientes WHERE nro_historia REGEXP '^HC-[0-9]+$'")
        check(pg.get_by_text(f'El siguiente número libre es {siguiente}').count() == 1, f'sugiere {siguiente} y no un número ocupado (F4.4)')
        pg.keyboard.press('Escape'); pg.wait_for_timeout(500)

        # --- administrador: familia de un paciente de baja (H16) ---
        pa = br.new_page(viewport={'width': 1400, 'height': 950})
        entrar(pa, 'admin@asisto.local')
        pa.locator('tr', has_text='Ignacio Rivas').get_by_role('button', name='Familia').click(); pa.wait_for_timeout(1500)
        check(pa.get_by_text('solo se pueden quitar accesos').count() == 1, 'admin: la familia de un paciente de baja, solo quitar')
        pa.get_by_role('button', name='Cerrar').click(); pa.wait_for_timeout(500)

        # --- enlace de recuperación vencido: se avisa al abrirlo (F1.3) ---
        pr = br.new_page(viewport={'width': 1200, 'height': 900})
        pr.goto(B + '/restablecer/un-enlace-que-no-existe'); pr.wait_for_timeout(1500)
        check(pr.get_by_text('Este enlace ya no es válido').count() == 1, 'el enlace inválido se avisa antes de completar nada')
        check(pr.get_by_label('Contraseña nueva').count() == 0, 'no pide contraseñas con un enlace inválido')
        br.close()
finally:
    limpiar()

print('FALLAS:', len(fallas)) if fallas else print('TODO OK')
sys.exit(1 if fallas else 0)

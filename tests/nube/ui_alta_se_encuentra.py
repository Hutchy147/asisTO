"""
Un paciente con el alta tiene que poder encontrarse (reporte del usuario: al
dar el alta aparecía «Reactivar» pero, al salir de la ficha, el paciente no
estaba en ningún lado). Cubre: la ficha manda al listado donde figura, el
filtro «En pausa o con alta» cuenta cuántos hay, la búsqueda en «En
tratamiento» avisa que está ahí y se puede reactivar desde ahí.
Backend 5000 + Vite 5173 con VITE_ENTREGA=6, base demo. Crea un paciente de
prueba asignado a Laura y lo borra al final.
"""
import subprocess
import sys
from playwright.sync_api import sync_playwright

B = 'http://localhost:5173'
APELLIDO = 'Zzaltaprueba'
fallas = []


def sql(q):
    return subprocess.run(['mysql', 'asisto', '-N', '-e', q], check=True, capture_output=True, text=True).stdout.strip()


def check(c, m):
    print(('OK   ' if c else 'FALLA'), m)
    if not c: fallas.append(m)


def limpiar():
    ids = f"(SELECT id FROM pacientes WHERE apellido = '{APELLIDO}')"
    sql(f"DELETE FROM asignaciones WHERE id_paciente IN {ids}")
    sql(f"DELETE FROM objetivos_terapeuticos WHERE id_paciente IN {ids}")
    sql(f"DELETE FROM pacientes WHERE apellido = '{APELLIDO}'")


limpiar()
sql(f"INSERT INTO pacientes (nombre, apellido, fecha_nacimiento, diagnostico, nro_historia, activo, fecha_alta) "
    f"VALUES ('Pablo', '{APELLIDO}', '2015-05-05', 'Prueba', 'HC-9999', TRUE, CURDATE())")
id_paciente = sql(f"SELECT id FROM pacientes WHERE apellido = '{APELLIDO}'")
sql(f"INSERT INTO asignaciones (id_terapeuta, id_paciente, fecha_desde) VALUES (1, {id_paciente}, CURDATE())")
try:
    with sync_playwright() as p:
        br = p.chromium.launch()
        pg = br.new_context(viewport={'width': 1400, 'height': 1000}).new_page()
        pg.goto(B + '/login'); pg.fill('input[type=email]', 'laura.fernandez@asisto.local'); pg.fill('input[type=password]', 'asisto2026')
        pg.click('button[type=submit]'); pg.wait_for_timeout(1800)

        pg.goto(f'{B}/pacientes/{id_paciente}'); pg.wait_for_timeout(2000)
        pg.get_by_role('button', name='Dar el alta').first.click(); pg.wait_for_timeout(500)
        d = pg.get_by_role('dialog')
        for campo in d.locator('textarea, input[type=text]').all():
            campo.fill('Cumplió los objetivos del plan')
        d.get_by_role('button', name='Dar el alta').click(); pg.wait_for_timeout(1800)
        check(pg.get_by_role('button', name='Reactivar').count() >= 1, 'tras el alta la ficha ofrece Reactivar')
        check(pg.get_by_text('Lo encuentra después en Pacientes, en «En pausa o con alta»').count() == 1,
              'la ficha dice dónde se lo encuentra después')
        check(pg.get_by_role('button', name='Ver el listado').count() == 1, 'la ficha ofrece ir al listado')

        # 1) el botón de volver lleva al listado donde figura
        pg.get_by_role('button', name='Volver a pacientes en pausa o con alta').click(); pg.wait_for_timeout(1500)
        check('estado=inactivos' in pg.url and pg.get_by_text(f'Pablo {APELLIDO}', exact=False).count() >= 1,
              'volver lleva a «En pausa o con alta», donde el paciente figura')

        # 2) en «En tratamiento» el filtro cuenta y la búsqueda avisa
        pg.goto(B + '/pacientes'); pg.wait_for_timeout(1500)
        check(pg.get_by_role('button', name='En pausa o con alta (', exact=False).count() == 1, 'el filtro dice cuántos hay en pausa o con alta')
        pg.get_by_placeholder('Buscar por nombre o historia').fill(APELLIDO); pg.wait_for_timeout(500)
        check(pg.get_by_text('No está entre los pacientes en tratamiento').count() == 1, 'buscarlo en «En tratamiento» avisa dónde está')
        pg.get_by_role('button', name='Ver en pausa o con alta').click(); pg.wait_for_timeout(1500)
        check(pg.get_by_text(f'Pablo {APELLIDO}', exact=False).count() >= 1, 'el aviso lleva al paciente')

        # 3) se reactiva desde ahí
        pg.get_by_text(f'Pablo {APELLIDO}', exact=False).first.click(); pg.wait_for_timeout(1500)
        pg.get_by_role('button', name='Reactivar').first.click(); pg.wait_for_timeout(500)
        pg.get_by_role('dialog').get_by_role('button', name='Reactivar').click(); pg.wait_for_timeout(1800)
        check(sql(f'SELECT activo FROM pacientes WHERE id = {id_paciente}') == '1', 'se reactiva desde ahí')
        br.close()
finally:
    limpiar()

print('FALLAS:', len(fallas)) if fallas else print('TODO OK')
sys.exit(1 if fallas else 0)

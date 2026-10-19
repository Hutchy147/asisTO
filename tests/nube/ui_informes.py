"""
UI de informes (Entrega 6): ficha de paciente con la pestana Informes, control
mensual, y el recorrido de publicacion hasta que la familia lo lee. Backend 5000
+ Vite 5173 con VITE_ENTREGA=6, base demo. Laura (terapeuta), Marta (familiar).
Limpia lo que cambia: el borrador del paciente 5 vuelve a borrador y se borran
los avisos de informe que genera la publicacion.
"""
import re, subprocess, sys
from playwright.sync_api import sync_playwright
B = 'http://localhost:5173'
SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
fallas = []

def sql(q):
    return subprocess.run(['mysql', 'asisto', '-N', '-e', q], check=True, capture_output=True, text=True).stdout.strip()

def check(c, m):
    print(('OK   ' if c else 'FALLA'), m)
    if not c: fallas.append(m)

def shot(pg, nombre):
    if SHOTS: pg.screenshot(path=f'{SHOTS}/{nombre}.png')

def login(pg, email):
    pg.goto(B + '/login'); pg.fill('input[type=email]', email); pg.fill('input[type=password]', 'asisto2026')
    pg.click('button[type=submit]'); pg.wait_for_timeout(1500)

# Los avisos del seed no se tocan: solo se borran los que genera esta prueba.
ULTIMO_AVISO = sql("SELECT COALESCE(MAX(id),0) FROM notificaciones")

def limpiar():
    sql("DELETE FROM informes WHERE id_paciente=1 AND version>1")
    sql("UPDATE informes SET estado='final' WHERE id_paciente=1 AND version=1 AND tipo IN ('mensual','semestral')")
    sql("UPDATE informes SET estado='borrador', fecha_publicacion=NULL, contenido=contenido_original, fecha_edicion=NULL WHERE id=3")
    sql(f"DELETE FROM notificaciones WHERE id > {ULTIMO_AVISO}")

limpiar()
with sync_playwright() as p:
    br = p.chromium.launch()
    ctx = br.new_context(viewport={'width': 1400, 'height': 950}, accept_downloads=True)
    pg = ctx.new_page()
    login(pg, 'laura.fernandez@asisto.local')

    # --- ficha: historial de informes ---
    pg.goto(B + '/pacientes/1'); pg.wait_for_timeout(2000)
    pg.get_by_role('tab', name='Informes').click(); pg.wait_for_timeout(1500)
    check(pg.get_by_text('Informe mensual').count() >= 1 and pg.get_by_text('Informe semestral').count() >= 1, 'el historial lista el mensual y el semestral')
    check(pg.get_by_role('button', name='Generar informe').count() == 1, 'Laura (asignada) ve Generar informe')
    shot(pg, '01_ficha_informes')

    # --- abrir uno publicado: lectura, sin textarea, con PDF ---
    pg.get_by_role('row').filter(has_text='Informe mensual').get_by_role('button', name='Abrir').first.click(); pg.wait_for_timeout(1500)
    check(pg.locator('textarea').count() == 0, 'un informe publicado no se edita')
    check(pg.get_by_role('button', name='Corregir').count() == 1, 'ofrece Corregir')
    check(pg.get_by_text('Publicado').count() >= 1, 'muestra el estado Publicado')
    shot(pg, '02_informe_publicado')
    with pg.expect_download() as d:
        pg.get_by_role('button', name='Descargar PDF').click()
    check(d.value.suggested_filename.startswith('informe-mensual-2026-09-') and d.value.suggested_filename.endswith('.pdf'), f'descarga el PDF ({d.value.suggested_filename})')
    path = d.value.path()
    check(open(path, 'rb').read(5) == b'%PDF-', 'el archivo descargado es un PDF')

    # --- corregir: nace un borrador v2 editable, el original sigue vigente ---
    pg.get_by_role('button', name='Corregir').click(); pg.wait_for_timeout(500)
    pg.get_by_role('button', name='Crear corrección').click(); pg.wait_for_timeout(2000)
    check(pg.locator('textarea[aria-label="Contenido del informe"]').count() == 1, 'la corrección abre un borrador editable')
    check(pg.get_by_text('Versión 2').count() >= 1, 'es la versión 2')
    check(sql("SELECT estado FROM informes WHERE id_paciente=1 AND tipo='mensual' AND periodo='2026-09' AND version=1") == 'final', 'la versión 1 sigue publicada hasta publicar la 2')
    area = pg.locator('textarea[aria-label="Contenido del informe"]')
    area.fill(area.input_value() + '\n\nTexto agregado por la prueba.')
    pg.get_by_role('button', name='Guardar', exact=True).click(); pg.wait_for_timeout(1200)
    check('Texto agregado por la prueba' in sql("SELECT contenido FROM informes WHERE id_paciente=1 AND version=2 AND tipo='mensual'"), 'Guardar persiste el texto editado')
    # diarios al costado
    pg.get_by_role('button', name='Ver diarios del período').click(); pg.wait_for_timeout(1800)
    check(pg.get_by_text('Diarios del período').count() >= 1 and pg.get_by_text('Objetivos evaluados').count() >= 1, 'el panel muestra los diarios del período')
    shot(pg, '03_borrador_con_diarios')
    # marca pendiente bloquea publicar
    area.fill(area.input_value() + '\n[COMPLETAR: cierre]')
    check(pg.get_by_role('button', name='Publicar', exact=True).is_disabled(), 'con una marca [COMPLETAR] Publicar queda bloqueado')
    shot(pg, '04_marca_pendiente')
    # descartar el borrador
    pg.get_by_role('button', name='Descartar borrador').click(); pg.wait_for_timeout(500)
    pg.get_by_role('button', name='Descartar', exact=True).click(); pg.wait_for_timeout(1500)
    check(sql("SELECT COUNT(*) FROM informes WHERE id_paciente=1 AND version=2") == '0', 'descartar elimina el borrador')

    # --- generar: avisa si ya hay un borrador de ese periodo ---
    pg.goto(B + '/pacientes/7'); pg.wait_for_timeout(2000)
    pg.get_by_role('tab', name='Informes').click(); pg.wait_for_timeout(1200)
    pg.get_by_role('button', name='Generar informe').click(); pg.wait_for_timeout(800)
    pg.fill('#informe-mes', '2026-09'); pg.wait_for_timeout(300)
    check(pg.get_by_text('Ya existe un borrador de este período').count() == 1, 'avisa que generar reemplaza el borrador existente')
    shot(pg, '05_generar_informe')
    pg.get_by_role('button', name='Cancelar').click(); pg.wait_for_timeout(400)

    # --- control mensual ---
    pg.goto(B + '/informes'); pg.wait_for_timeout(2000)
    pg.fill('#control-mes', '2026-09'); pg.wait_for_timeout(1500)
    check(pg.get_by_text('Mensuales publicados').count() == 1, 'el control muestra el resumen')
    check(pg.get_by_role('row').filter(has_text='Tomas Aguirre').get_by_text('Publicado').count() >= 1, 'Tomas figura con el mensual publicado')
    check(pg.get_by_role('row').filter(has_text='Lucia Molina').get_by_text('Borrador').count() >= 1, 'Lucia figura en borrador')
    shot(pg, '06_control_mensual')
    pg.get_by_role('row').filter(has_text='Lucia Molina').get_by_role('button', name='Abrir').first.click(); pg.wait_for_timeout(1500)
    check(pg.locator('textarea[aria-label="Contenido del informe"]').count() == 1, 'desde el control se abre el borrador')
    pg.get_by_role('button', name='Cerrar').click(); pg.wait_for_timeout(500)

    # --- publicar el borrador del paciente 5 (de Diego/otra terapeuta) lo hace su asignada ---
    due = sql("SELECT u.email FROM informes i JOIN terapeutas t ON t.id=i.id_terapeuta JOIN usuarios u ON u.id=t.id_usuario WHERE i.id=3")
    pg2 = ctx.new_page()
    pg2.goto(B + '/login'); pg2.evaluate('localStorage.clear()'); pg2.close()
    ctx.clear_cookies()
    pg = ctx.new_page(); pg.goto(B + '/login'); pg.evaluate('localStorage.clear()')
    login(pg, due)
    pg.goto(B + '/pacientes/5'); pg.wait_for_timeout(2000)
    pg.get_by_role('tab', name='Informes').click(); pg.wait_for_timeout(1200)
    pg.get_by_role('button', name='Abrir').first.click(); pg.wait_for_timeout(1500)
    a5 = pg.locator('textarea[aria-label="Contenido del informe"]')
    check(pg.get_by_role('button', name='Publicar', exact=True).is_disabled(), 'el borrador sembrado trae marcas [COMPLETAR] y no se puede publicar')
    a5.fill(re.sub(r'\[COMPLETAR[^\]]*\]', 'Texto revisado por la terapeuta.', a5.input_value())); pg.wait_for_timeout(300)
    pg.get_by_role('button', name='Publicar', exact=True).click(); pg.wait_for_timeout(500)
    pg.get_by_role('button', name='Publicar', exact=True).last.click(); pg.wait_for_timeout(2500)
    check(sql("SELECT estado FROM informes WHERE id=3") == 'final', 'publicar deja el informe en estado final')

    # --- la familia lo ve ---
    pg.evaluate('localStorage.clear()')
    login(pg, 'marta.ledesma@asisto.local')
    pg.goto(B + '/familiar/informes'); pg.wait_for_timeout(2000)
    check(pg.get_by_text('Informe mensual').count() >= 1, 'Marta ve los informes publicados')
    pg.get_by_role('tab', name='Mia Cardozo').click(); pg.wait_for_timeout(1500)
    check(pg.get_by_text('Informe mensual').count() >= 1, 'Marta ve el informe recien publicado de Mia')
    shot(pg, '07_informes_familiar')
    pg.get_by_role('button', name='Leer').first.click(); pg.wait_for_timeout(1500)
    check(pg.get_by_role('dialog').get_by_text('Equipo terapéutico').count() == 0 and pg.locator('textarea').count() == 0, 'el lector no ofrece edicion')
    shot(pg, '08_lector_familiar')
    with pg.expect_download() as d2:
        pg.get_by_role('button', name='Descargar PDF').click()
    check(d2.value.suggested_filename.endswith('.pdf'), 'la familia descarga el PDF')
    br.close()

limpiar()
sys.exit(1 if fallas else 0)

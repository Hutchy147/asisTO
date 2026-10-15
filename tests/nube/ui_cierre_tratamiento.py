"""
UI del cierre de tratamiento (Entrega 3, bloque 9): pausa con motivo, banner,
reactivar, dialogo de alta y aviso de minimo de objetivos. Backend 5000 + Vite
5173 con VITE_ENTREGA=3, base demo, como Laura. Deja al paciente como estaba.
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

# paciente de Laura con >= 3 objetivos activos, y otro con menos de 3 (si hay)
base = ("SELECT a.id_paciente FROM asignaciones a JOIN terapeutas t ON t.id=a.id_terapeuta JOIN usuarios u ON u.id=t.id_usuario "
        "JOIN pacientes p ON p.id=a.id_paciente WHERE u.email='laura.fernandez@asisto.local' AND a.fecha_hasta IS NULL AND p.activo=TRUE "
        "AND (SELECT COUNT(*) FROM objetivos_terapeuticos o WHERE o.id_paciente=p.id AND o.activo=TRUE) {} ORDER BY 1 LIMIT 1")
pid = sql(base.format('>= 3'))
corto = sql("SELECT p.id FROM pacientes p WHERE p.activo=TRUE AND (SELECT COUNT(*) FROM objetivos_terapeuticos o WHERE o.id_paciente=p.id AND o.activo=TRUE) < 3 ORDER BY 1 LIMIT 1")
check(bool(pid), f'hay paciente de Laura con 3+ objetivos ({pid})')

try:
    with sync_playwright() as p:
        br = p.chromium.launch()
        pg = br.new_page(viewport={'width': 1400, 'height': 950})
        pg.goto(B + '/login'); pg.fill('input[type=email]', 'laura.fernandez@asisto.local'); pg.fill('input[type=password]', 'asisto2026')
        pg.click('button[type=submit]'); pg.wait_for_timeout(1500)
        pg.goto(f'{B}/pacientes/{pid}'); pg.wait_for_timeout(2000)
        check(pg.get_by_role('button', name='Pausar tratamiento').count() == 1, 'ofrece Pausar tratamiento')
        check(pg.get_by_role('button', name='Dar el alta').count() == 1, 'ofrece Dar el alta (no "Dar de baja")')
        check(pg.get_by_text('Faltan').count() == 0, 'con 3+ objetivos no avisa que faltan')

        pg.get_by_role('button', name='Pausar tratamiento').click(); pg.wait_for_timeout(500)
        check(pg.get_by_role('button', name='Pausar', exact=True).is_disabled(), 'Pausar deshabilitado sin motivo')
        pg.screenshot(path='/tmp/claude-0/ui/doc/12_pausar_tratamiento.png')
        pg.get_by_label('Motivo de la baja').fill('Viaje familiar de dos semanas')
        pg.get_by_role('button', name='Pausar', exact=True).click(); pg.wait_for_timeout(1500)
        check(pg.get_by_text('Tratamiento en pausa').count() == 1, 'banner de pausa')
        check(pg.get_by_text('Viaje familiar de dos semanas').count() >= 1, 'muestra el motivo')
        check(pg.get_by_role('button', name='Reactivar').count() == 1, 'ofrece Reactivar')
        pg.screenshot(path='/tmp/claude-0/ui/doc/13_tratamiento_en_pausa.png')
        n = sql(f"SELECT COUNT(*) FROM objetivos_terapeuticos WHERE id_paciente={pid} AND activo=TRUE")
        check(int(n) >= 3, f'la pausa no archivo objetivos ({n} activos)')

        pg.get_by_role('button', name='Reactivar').click(); pg.wait_for_timeout(500)
        check(pg.get_by_text('siguen como estaban').count() >= 1, 'el dialogo de reactivar habla de la pausa')
        pg.get_by_role('button', name='Reactivar').last.click(); pg.wait_for_timeout(1500)
        check(pg.get_by_text('Tratamiento en pausa').count() == 0, 'reactivado: sin banner')

        # dialogo de alta: se abre con numeros y se cancela
        pg.get_by_role('button', name='Dar el alta').click(); pg.wait_for_timeout(900)
        check(pg.get_by_text('se archivan sus').count() == 1, 'el alta dice que archiva objetivos')
        pg.get_by_role('button', name='Cancelar').click(); pg.wait_for_timeout(400)

        if corto:
            pg.goto(f'{B}/pacientes/{corto}'); pg.wait_for_timeout(2000)
            check(pg.get_by_text('Faltan').count() == 1, f'paciente {corto} con menos de 3: avisa cuantos faltan')
            pg.screenshot(path='/tmp/claude-0/ui/doc/14_faltan_objetivos.png')
        br.close()
finally:
    sql(f"UPDATE pacientes SET activo=TRUE, fecha_baja=NULL, tipo_cierre=NULL, motivo_baja=NULL WHERE id={pid}")
sys.exit(1 if fallas else 0)

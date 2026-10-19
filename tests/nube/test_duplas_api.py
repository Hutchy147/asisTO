"""
tests/nube/test_duplas_api.py — duplas terapeuticas (Entrega 5).

Una dupla es UNA terapeuta con DOS pacientes en el mismo horario. seed.sql:
pacientes 1 y 3 -> Laura (vigente), paciente 2 -> Diego.

Todas las sesiones y turnos de estas pruebas viven entre las 02:00 y las
02:59, y cada prueba los borra al empezar y al terminar.
"""
import concurrent.futures
import datetime as dt
import unittest

from sqlalchemy.exc import DBAPIError

from _base import BaseApi, hoy


def primera_fecha(weekday, desde=None):
    """Primera fecha desde hoy (inclusive) que cae en `weekday` (0 = lunes)."""
    d = desde or hoy()
    while d.weekday() != weekday:
        d += dt.timedelta(days=1)
    return d


class DuplasApi(BaseApi):
    def limpiar(self):
        self.sql("DELETE FROM sesiones WHERE hora_inicio >= '02:00:00' AND hora_inicio < '03:00:00'")
        self.sql('UPDATE agenda_recurrente SET activo = FALSE')

    def setUp(self):
        self.limpiar()
        self.addCleanup(self.limpiar)

    def turno_dupla(self, quien='laura', **extra):
        cuerpo = {'id_paciente': 1, 'id_paciente_2': 3, 'dia_semana': 1, 'hora_inicio': '02:00'}
        cuerpo.update(extra)
        return self.llamar(quien, 'post', '/api/agenda-recurrente', json=cuerpo)

    def generar(self, semanas=2, quien='laura'):
        return self.llamar(quien, 'post', '/api/agenda-recurrente/generar', json={'semanas': semanas})

    def sesiones_dupla(self):
        return self.sql("""SELECT id, id_paciente, fecha, hora_inicio, hora_fin, id_dupla, estado
                             FROM sesiones WHERE hora_inicio = '02:00:00' ORDER BY fecha, id_paciente""")

    # ------------------------------------------------------------------
    # Turno semanal en dupla
    # ------------------------------------------------------------------
    def test_crear_turno_en_dupla_y_listarlo(self):
        r = self.turno_dupla()
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        cuerpo = r.get_json()
        self.assertEqual(cuerpo['turno']['id_dupla'], cuerpo['companero']['id_dupla'])
        self.assertEqual(cuerpo['id_dupla'], cuerpo['turno']['id'])
        self.assertEqual((cuerpo['turno']['hora_inicio'], cuerpo['turno']['hora_fin']),
                         ('02:00:00', '02:45:00'))

        lista = self.llamar('laura', 'get', '/api/agenda-recurrente').get_json()
        self.assertEqual(lista['total'], 2)
        a, b = lista['plantillas']
        self.assertEqual(a['id_dupla'], b['id_dupla'])
        self.assertEqual(a['companero']['id_turno'], b['id'])
        self.assertEqual(b['companero']['id_paciente'], a['id_paciente'])
        # cada terapeuta ve solo la suya
        self.assertEqual(self.llamar('diego', 'get', '/api/agenda-recurrente').get_json()['total'], 0)

    def test_validaciones_del_turno_en_dupla_con_control_positivo(self):
        casos = (
            ({'id_paciente_2': 1}, 400, 'distintos'),          # el mismo paciente dos veces
            ({'id_paciente_2': 2}, 400, 'asignados'),          # paciente de Diego
            ({'id_paciente_2': 999}, 404, 'no existe'),
            ({'dia_semana': 6}, 400, None),                    # sabado
            ({'hora_inicio': '02:00', 'hora_fin': '02:00'}, 400, None),
        )
        for extra, estado, fragmento in casos:
            r = self.turno_dupla(**extra)
            self.assertEqual(r.status_code, estado, (extra, r.get_data(as_text=True)))
            if fragmento:
                self.assertIn(fragmento, r.get_json()['mensaje'].lower(), extra)
        self.assertEqual(self.llamar('laura', 'get', '/api/agenda-recurrente').get_json()['total'], 0)
        self.assertEqual(self.turno_dupla().status_code, 201)   # el mismo pedido valido entra

    def test_permisos_del_turno_en_dupla(self):
        # Diego no tiene asignados a los pacientes 1 y 3
        r = self.turno_dupla('diego')
        self.assertEqual(r.status_code, 400)
        self.assertIn('asignados', r.get_json()['mensaje'])
        for quien in ('rrhh', 'familiar', 'admin', None):
            self.assertIn(self.turno_dupla(quien).status_code, (401, 403), quien)

    def test_solape_de_un_turno_en_dupla_con_otros_turnos(self):
        self.assertEqual(self.turno_dupla().status_code, 201)
        r = self.turno_dupla(hora_inicio='02:30')
        self.assertEqual(r.status_code, 409, r.get_data(as_text=True))
        self.assertIn('superpone', r.get_json()['mensaje'])
        # un turno individual encima de la dupla tambien se rechaza
        r = self.llamar('laura', 'post', '/api/agenda-recurrente',
                        json={'id_paciente': 1, 'dia_semana': 1, 'hora_inicio': '02:30'})
        self.assertEqual((r.status_code, r.get_json()['campo']), (400, 'hora_inicio'))
        # pegado y en otro dia entran
        self.assertEqual(self.turno_dupla(hora_inicio='02:45').status_code, 201)
        self.assertEqual(self.turno_dupla(dia_semana=2).status_code, 201)

    def test_sumar_companero_a_un_turno_individual(self):
        r = self.llamar('laura', 'post', '/api/agenda-recurrente',
                        json={'id_paciente': 1, 'dia_semana': 2, 'hora_inicio': '02:00'})
        id_turno = r.get_json()['turno']['id']
        ruta = f'/api/agenda-recurrente/{id_turno}/companero'

        for quien, cuerpo, estado in (
            ('diego', {'id_paciente': 3}, 403),     # turno ajeno
            ('laura', {}, 400),                     # falta el paciente
            ('laura', {'id_paciente': 1}, 400),     # el mismo paciente
            ('laura', {'id_paciente': 2}, 400),     # no asignado a Laura
            ('laura', {'id_paciente': 999}, 404),
        ):
            self.assertEqual(self.llamar(quien, 'post', ruta, json=cuerpo).status_code, estado, (quien, cuerpo))
        self.assertEqual(self.llamar('laura', 'get', '/api/agenda-recurrente').get_json()['plantillas'][0]['id_dupla'], None)

        r = self.llamar('laura', 'post', ruta, json={'id_paciente': 3})
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        lista = self.llamar('laura', 'get', '/api/agenda-recurrente').get_json()
        self.assertEqual(lista['total'], 2)
        self.assertEqual(lista['plantillas'][0]['id_dupla'], lista['plantillas'][1]['id_dupla'])
        # ya es una dupla completa: no admite un tercero
        r = self.llamar('laura', 'post', ruta, json={'id_paciente': 3})
        self.assertEqual(r.status_code, 409, r.get_data(as_text=True))
        self.assertIn('ya integra', r.get_json()['mensaje'])

    def test_quitar_un_paciente_o_la_dupla_entera(self):
        cuerpo = self.turno_dupla().get_json()
        id_a, id_b = cuerpo['turno']['id'], cuerpo['companero']['id']
        # quitar solo a uno: el otro queda como turno individual
        r = self.llamar('laura', 'delete', f'/api/agenda-recurrente/{id_a}')
        self.assertEqual(r.status_code, 200)
        lista = self.llamar('laura', 'get', '/api/agenda-recurrente').get_json()
        self.assertEqual([(t['id'], t['id_dupla'], t['companero']) for t in lista['plantillas']],
                         [(id_b, None, None)])
        # la dupla entera
        otra = self.turno_dupla(dia_semana=3).get_json()
        r = self.llamar('laura', 'delete', f"/api/agenda-recurrente/{otra['turno']['id']}?dupla=1")
        self.assertEqual(r.status_code, 200)
        lista = self.llamar('laura', 'get', '/api/agenda-recurrente').get_json()
        self.assertEqual([t['id'] for t in lista['plantillas']], [id_b])
        # el turno que queda puede recibir otro companero
        self.assertEqual(self.llamar('laura', 'delete', f'/api/agenda-recurrente/{id_a}').status_code, 404)

    # ------------------------------------------------------------------
    # Generacion de sesiones en dupla
    # ------------------------------------------------------------------
    def test_generar_crea_las_dos_sesiones_y_es_idempotente(self):
        self.turno_dupla(dia_semana=1)
        g = self.generar(2).get_json()
        self.assertEqual((g['creadas'], g['existentes'], g['omitidas']), (4, 0, []), g)

        filas = self.sesiones_dupla()
        self.assertEqual(len(filas), 4)
        for i in (0, 2):
            a, b = filas[i], filas[i + 1]
            self.assertEqual((a.fecha, b.fecha), (a.fecha, a.fecha))
            self.assertEqual(a.id_dupla, b.id_dupla)
            self.assertEqual(a.id_dupla, min(a.id, b.id))
            self.assertEqual((a.hora_inicio, a.hora_fin), (b.hora_inicio, b.hora_fin))
            self.assertEqual({a.id_paciente, b.id_paciente}, {1, 3})
            self.assertEqual((a.estado, b.estado), ('incompleta', 'incompleta'))
        self.assertNotEqual(filas[0].id_dupla, filas[2].id_dupla)

        g = self.generar(2).get_json()
        self.assertEqual((g['creadas'], g['existentes'], g['omitidas']), (0, 4, []), g)
        self.assertEqual(len(self.sesiones_dupla()), 4)

    def test_generar_suma_al_companero_cuando_una_sesion_ya_existia(self):
        # La sesion de Tomas ya estaba agendada como individual
        fecha = primera_fecha(1).isoformat()   # el martes que viene (o hoy)
        r = self.llamar('laura', 'post', '/api/sesiones', json={
            'id_paciente': 1, 'fecha': fecha, 'hora_inicio': '02:00', 'estado': 'incompleta'})
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        self.turno_dupla(dia_semana=2)

        g = self.generar(1).get_json()
        self.assertEqual((g['creadas'], g['existentes'], g['omitidas']), (1, 1, []), g)
        filas = self.sesiones_dupla()
        self.assertEqual([f.id_paciente for f in filas], [1, 3])
        self.assertEqual(filas[0].id_dupla, filas[1].id_dupla)
        self.assertEqual(filas[0].id_dupla, filas[0].id)

    def test_generar_omite_con_motivo_si_la_sesion_existente_ya_esta_en_otra_dupla(self):
        fecha = primera_fecha(1).isoformat()
        # Sesion de Tomas ya en dupla con alguien mas: forzado por SQL
        self.sql("""INSERT INTO sesiones (id_terapeuta, id_paciente, fecha, hora_inicio, hora_fin, estado)
                    VALUES (1, 1, :f, '02:00:00', '02:45:00', 'incompleta')""", f=fecha)
        self.sql("UPDATE sesiones SET id_dupla = id WHERE fecha = :f AND hora_inicio = '02:00:00'", f=fecha)
        self.turno_dupla(dia_semana=2)
        g = self.generar(1).get_json()
        self.assertEqual(g['creadas'], 0, g)
        self.assertEqual(len(g['omitidas']), 1, g)
        self.assertIn('otra dupla', g['omitidas'][0]['motivo'])

    # ------------------------------------------------------------------
    # Reglas de la base
    # ------------------------------------------------------------------
    def test_una_sesion_ajena_a_la_dupla_no_puede_pisar_el_horario(self):
        self.turno_dupla(dia_semana=1)
        self.generar(1)
        fecha = self.sesiones_dupla()[0].fecha.isoformat()
        r = self.llamar('laura', 'post', '/api/sesiones', json={
            'id_paciente': 2, 'fecha': fecha, 'hora_inicio': '02:15', 'estado': 'incompleta'})
        self.assertEqual(r.status_code, 400)
        self.assertIn('superponen', r.get_json()['mensaje'])
        # control positivo: fuera de la dupla el rechazo es otro (asignacion)
        r = self.llamar('laura', 'post', '/api/sesiones', json={
            'id_paciente': 2, 'fecha': fecha, 'hora_inicio': '02:45', 'estado': 'incompleta'})
        self.assertEqual(r.status_code, 400)
        self.assertNotIn('superponen', r.get_json()['mensaje'])

    def intentar_sql(self, consulta, **params):
        """Ejecuta SQL y devuelve el mensaje del error de la base, o None si entro."""
        try:
            self.sql(consulta, **params)
        except DBAPIError as error:
            return str(error.orig)
        return None

    def test_los_triggers_de_dupla_por_sql(self):
        fecha = primera_fecha(0).isoformat()
        alta = """INSERT INTO sesiones (id_terapeuta, id_paciente, fecha, hora_inicio, hora_fin, estado, id_dupla)
                  VALUES (1, :p, :f, :ini, :fin, 'incompleta', :d)"""
        self.assertIsNone(self.intentar_sql(alta, p=1, f=fecha, ini='02:00:00', fin='02:45:00', d=None))
        id_a = self.sql("SELECT id FROM sesiones WHERE hora_inicio = '02:00:00'")[0].id
        self.assertIsNone(self.intentar_sql('UPDATE sesiones SET id_dupla = id WHERE id = :i', i=id_a))

        # otro horario aunque se pise con la dupla: no es la misma dupla
        msg = self.intentar_sql(alta, p=3, f=fecha, ini='02:00:00', fin='02:30:00', d=id_a)
        self.assertIn('mismo horario', msg or '')
        # otra terapeuta
        msg = self.intentar_sql("""INSERT INTO sesiones (id_terapeuta, id_paciente, fecha, hora_inicio, hora_fin, estado, id_dupla)
                                   VALUES (2, 2, :f, '02:00:00', '02:45:00', 'incompleta', :d)""", f=fecha, d=id_a)
        self.assertIn('misma terapeuta', msg or '')
        # control positivo: el mismo horario exacto entra
        self.assertIsNone(self.intentar_sql(alta, p=3, f=fecha, ini='02:00:00', fin='02:45:00', d=id_a))
        # y una tercera sesion ya no
        msg = self.intentar_sql(alta, p=2, f=fecha, ini='02:00:00', fin='02:45:00', d=id_a)
        self.assertIn('maximo dos', msg or '')

    def llamar_dupla(self, **params):
        """CALL p_registrar_dupla y lectura de los OUT en la MISMA conexion."""
        from sqlalchemy import text
        from app import db
        with self.app.app_context():
            db.session.execute(text("""CALL p_registrar_dupla(:t, :p1, :p2, :f, '02:00:00', '02:45:00',
                                                               @d, @s1, @s2, @m)"""), params)
            fila = db.session.execute(text('SELECT @d, @s1, @s2, @m')).first()
            db.session.commit()
            return tuple(fila)

    def test_p_registrar_dupla_es_atomica(self):
        fecha = primera_fecha(0).isoformat()
        # el paciente 2 no esta asignado a Laura: no tiene que quedar NINGUNA de las dos
        d, s1, s2, m = self.llamar_dupla(t=1, p1=1, p2=2, f=fecha)
        self.assertEqual((d, s1, s2), (None, None, None))
        self.assertIn('no tiene asignado', m)
        self.assertEqual(len(self.sesiones_dupla()), 0)
        # control positivo con los dos asignados
        d, s1, s2, m = self.llamar_dupla(t=1, p1=1, p2=3, f=fecha)
        self.assertEqual((d, m), (s1, 'Dupla registrada correctamente'))
        self.assertEqual(len(self.sesiones_dupla()), 2)
        # el mismo paciente dos veces
        self.assertIn('distintos', self.llamar_dupla(t=1, p1=1, p2=1, f=fecha)[3])

    # ------------------------------------------------------------------
    # Lectura y edicion
    # ------------------------------------------------------------------
    def test_la_lista_y_el_detalle_dicen_quien_es_el_companero(self):
        self.turno_dupla(dia_semana=1)
        self.generar(1)
        a, b = self.sesiones_dupla()[:2]
        desde = a.fecha.isoformat()
        lista = self.llamar('laura', 'get', f'/api/sesiones?desde={desde}&hasta={desde}').get_json()
        por_id = {s['id']: s for s in lista['sesiones']}
        self.assertEqual(por_id[a.id]['id_dupla'], a.id_dupla)
        self.assertEqual(por_id[a.id]['companero']['id_sesion'], b.id)
        self.assertEqual(por_id[b.id]['companero']['id_paciente'], a.id_paciente)
        self.assertIn('nombre_completo', por_id[a.id]['companero'])

        detalle = self.llamar('diego', 'get', f'/api/sesiones/{a.id}').get_json()   # lectura abierta
        self.assertEqual(detalle['sesion']['companero']['id_sesion'], b.id)
        # una sesion individual no tiene companero
        self.sql("""INSERT INTO sesiones (id_terapeuta, id_paciente, fecha, hora_inicio, hora_fin, estado)
                    VALUES (1, 1, :f, '02:50:00', '03:35:00', 'incompleta')""", f=desde)
        sola = self.sql("SELECT id FROM sesiones WHERE hora_inicio = '02:50:00'")[0].id
        detalle = self.llamar('laura', 'get', f'/api/sesiones/{sola}').get_json()
        self.assertIsNone(detalle['sesion']['companero'])
        self.assertIsNone(detalle['sesion']['id_dupla'])

    def test_reprogramar_una_sesion_de_dupla_mueve_las_dos(self):
        self.turno_dupla(dia_semana=1)
        self.generar(1)
        a, b = self.sesiones_dupla()[:2]
        nueva = (a.fecha + dt.timedelta(days=1)).isoformat()    # martes
        cuerpo = {'estado': 'incompleta', 'fecha': nueva, 'hora_inicio': '02:10',
                  'hora_fin': '02:55', 'notas': 'cambio de dia'}
        r = self.llamar('laura', 'put', f'/api/sesiones/{a.id}', json=cuerpo)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertIn('También se reprogramó la sesión de', r.get_json()['mensaje'])
        filas = self.sql('SELECT id, fecha, hora_inicio, hora_fin, notas, id_dupla FROM sesiones WHERE id IN (:a, :b)',
                         a=a.id, b=b.id)
        for f in filas:
            self.assertEqual((f.fecha.isoformat(), str(f.hora_inicio), str(f.hora_fin)),
                             (nueva, '2:10:00', '2:55:00'))
            self.assertEqual(f.id_dupla, a.id_dupla)
        # las notas son de cada sesion, no se copian a la hermana
        self.assertEqual({f.id: f.notas for f in filas}, {a.id: 'cambio de dia', b.id: None})

    def test_editar_estado_o_notas_no_toca_a_la_hermana(self):
        self.turno_dupla(dia_semana=1)
        self.generar(1)
        a, b = self.sesiones_dupla()[:2]
        cuerpo = {'estado': 'ausencia', 'ausencia_de': 'paciente',
                  'fecha': a.fecha.isoformat(), 'hora_inicio': '02:00', 'hora_fin': '02:45'}
        r = self.llamar('laura', 'put', f'/api/sesiones/{a.id}', json=cuerpo)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertNotIn('También se reprogramó', r.get_json()['mensaje'])
        estados = {f.id: f.estado for f in self.sql('SELECT id, estado FROM sesiones WHERE id IN (:a, :b)', a=a.id, b=b.id)}
        self.assertEqual(estados, {a.id: 'ausencia', b.id: 'incompleta'})
        # y la hermana sigue siendo editable por su cuenta (Diego no puede)
        self.assertEqual(self.llamar('diego', 'put', f'/api/sesiones/{b.id}', json=cuerpo).status_code, 403)

    def test_reprogramar_la_dupla_encima_de_otra_sesion_se_rechaza_y_no_mueve_ninguna(self):
        self.turno_dupla(dia_semana=1)
        self.generar(1)
        a, b = self.sesiones_dupla()[:2]
        # una sesion individual de Laura en el horario destino
        self.sql("""INSERT INTO sesiones (id_terapeuta, id_paciente, fecha, hora_inicio, hora_fin, estado)
                    VALUES (1, 1, :f, '02:50:00', '03:35:00', 'incompleta')""",
                 f=(a.fecha + dt.timedelta(days=1)).isoformat())
        cuerpo = {'estado': 'incompleta', 'fecha': (a.fecha + dt.timedelta(days=1)).isoformat(),
                  'hora_inicio': '02:50', 'hora_fin': '03:35'}
        r = self.llamar('laura', 'put', f'/api/sesiones/{a.id}', json=cuerpo)
        self.assertEqual(r.status_code, 400, r.get_data(as_text=True))
        self.assertIn('superponen', r.get_json()['mensaje'])
        fechas = {f.fecha for f in self.sql('SELECT fecha FROM sesiones WHERE id IN (:a, :b)', a=a.id, b=b.id)}
        self.assertEqual(fechas, {a.fecha})

    # ------------------------------------------------------------------
    # RRHH
    # ------------------------------------------------------------------
    def test_rrhh_no_marca_como_superpuestas_a_las_sesiones_de_una_dupla(self):
        self.turno_dupla(dia_semana=1)
        self.generar(1)
        a, b = self.sesiones_dupla()[:2]
        d = a.fecha.isoformat()

        def superposiciones():
            r = self.llamar('rrhh', 'get', f'/api/rrhh/reporte-sesiones?desde={d}&hasta={d}')
            self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
            return {s['id_sesion']: s['superposiciones'] for s in r.get_json()['sesiones']
                    if s['id_sesion'] in (a.id, b.id)}

        self.assertEqual(superposiciones(), {a.id: 0, b.id: 0})
        # control: si se rompe la dupla, el solape vuelve a contarse
        self.sql('UPDATE sesiones SET id_dupla = NULL WHERE id IN (:a, :b)', a=a.id, b=b.id)
        self.assertEqual(superposiciones(), {a.id: 1, b.id: 1})

    # ------------------------------------------------------------------
    # Concurrencia
    # ------------------------------------------------------------------
    def test_dos_pedidos_simultaneos_para_el_mismo_turno_en_dupla(self):
        token = self.token('laura')
        cuerpo = {'id_paciente': 1, 'id_paciente_2': 3, 'dia_semana': 4, 'hora_inicio': '02:00'}

        def pedir(_):
            cliente = self.app.test_client()
            return cliente.post('/api/agenda-recurrente', json=cuerpo,
                                headers={'Authorization': f'Bearer {token}'}).status_code

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            estados = sorted(pool.map(pedir, range(2)))
        self.assertEqual(estados, [201, 409], estados)
        self.assertEqual(self.llamar('laura', 'get', '/api/agenda-recurrente').get_json()['total'], 2)


if __name__ == '__main__':
    unittest.main()

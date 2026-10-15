"""
tests/nube/test_renglones_api.py — notas de campo en renglones (Entrega 3):
plan / registro, destacado, cierre y arrastre. Control positivo junto a cada
rechazo. seed.sql: paciente 1 y 3 -> Laura; 2 -> Diego.
"""
import datetime as dt
import unittest

from sqlalchemy.exc import DBAPIError

from _base import BaseApi, db, dia_habil_pasado, hoy
from test_agenda_api import proximo_dia


class RenglonesApi(BaseApi):
    def _sesion(self, fecha, hora='09:00', paciente=1, estado='incompleta', quien='laura', **extra):
        cuerpo = {'id_paciente': paciente, 'fecha': fecha, 'hora_inicio': hora, 'estado': estado}
        cuerpo.update(extra)
        r = self.llamar(quien, 'post', '/api/sesiones', json=cuerpo)
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        return r.get_json()['sesion']['id']

    def _renglon(self, id_sesion, momento='plan', texto='trabajar pinza', quien='laura', **extra):
        return self.llamar(quien, 'post', f'/api/sesiones/{id_sesion}/renglones',
                           json={'momento': momento, 'texto': texto, **extra})

    # --- escritura y reglas del momento -----------------------------------
    def test_plan_en_sesion_futura_y_registro_solo_si_ya_ocurrio(self):
        futura = self._sesion(proximo_dia(1, 20), '08:00')
        pasada = self._sesion(dia_habil_pasado(3), '08:00')
        self.assertEqual(self._renglon(futura, 'plan').status_code, 201)
        r = self._renglon(futura, 'registro')
        self.assertEqual((r.status_code, r.get_json()['campo']), (400, 'momento'), r.get_data(as_text=True))
        # control positivo: el mismo registro en una sesion que ya paso entra
        self.assertEqual(self._renglon(pasada, 'registro').status_code, 201)

    def test_ausente_cierra_el_registro_pero_no_el_plan(self):
        id_s = self._sesion(dia_habil_pasado(4), '10:00', estado='ausencia', ausencia_de='paciente')
        r = self._renglon(id_s, 'registro')
        self.assertEqual((r.status_code, r.get_json()['campo']), (400, 'momento'))
        self.assertIn('ausencia', r.get_json()['mensaje'])
        self.assertEqual(self._renglon(id_s, 'plan').status_code, 201)   # el plan se conserva

    def test_no_se_puede_pasar_a_ausencia_con_registro_escrito(self):
        id_s = self._sesion(dia_habil_pasado(5), '11:00')
        self.assertEqual(self._renglon(id_s, 'plan').status_code, 201)
        self.assertEqual(self._renglon(id_s, 'registro', 'se mostro motivado').status_code, 201)
        edicion = {'estado': 'ausencia', 'ausencia_de': 'paciente',
                   'fecha': dia_habil_pasado(5), 'hora_inicio': '11:00'}
        r = self.llamar('laura', 'put', f'/api/sesiones/{id_s}', json=edicion)
        self.assertEqual((r.status_code, r.get_json()['campo']), (400, 'estado'), r.get_data(as_text=True))
        self.assertIn('renglones de registro', r.get_json()['mensaje'])
        # control positivo: con SOLO plan, la misma edicion entra
        solo_plan = self._sesion(dia_habil_pasado(5), '12:00')
        self._renglon(solo_plan, 'plan')
        edicion['hora_inicio'] = '12:00'
        r = self.llamar('laura', 'put', f'/api/sesiones/{solo_plan}', json=edicion)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))

    def test_validaciones_de_texto_momento_y_tope(self):
        id_s = self._sesion(proximo_dia(2, 20), '08:00')
        for cuerpo, campo in (({'momento': 'plan', 'texto': '   '}, 'texto'),
                              ({'momento': 'plan', 'texto': 'x' * 161}, 'texto'),
                              ({'momento': 'otro', 'texto': 'ok'}, 'momento'),
                              ({'texto': 'sin momento'}, 'momento')):
            r = self.llamar('laura', 'post', f'/api/sesiones/{id_s}/renglones', json=cuerpo)
            self.assertEqual((r.status_code, r.get_json()['campo']), (400, campo), cuerpo)
        # el limite exacto de largo entra (control positivo)
        self.assertEqual(self._renglon(id_s, 'plan', 'x' * 160).status_code, 201)
        # tope de 30 por momento
        for i in range(29):
            self.assertEqual(self._renglon(id_s, 'plan', f'r{i}').status_code, 201)
        r = self._renglon(id_s, 'plan', 'uno de mas')
        self.assertEqual(r.status_code, 400)
        self.assertIn('30 renglones', r.get_json()['mensaje'])

    def test_se_guarda_recortado_y_con_marca(self):
        id_s = self._sesion(proximo_dia(3, 20), '08:00')
        r = self._renglon(id_s, 'plan', '  pinza trípode  ', destacado=True)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.get_json()['renglon']['texto'], 'pinza trípode')
        self.assertTrue(r.get_json()['renglon']['destacado'])

    # --- autoria -----------------------------------------------------------
    def test_solo_el_terapeuta_de_la_sesion_escribe_la_lectura_es_abierta(self):
        id_s = self._sesion(dia_habil_pasado(6), '08:00')
        id_r = self._renglon(id_s, 'plan').get_json()['renglon']['id']
        # Diego NO escribe en la sesion de Laura...
        self.assertEqual(self._renglon(id_s, 'plan', quien='diego').status_code, 403)
        self.assertEqual(self.llamar('diego', 'put', f'/api/renglones/{id_r}', json={'texto': 'x'}).status_code, 403)
        self.assertEqual(self.llamar('diego', 'post', f'/api/renglones/{id_r}/cierre', json={'cierre': 'hecho'}).status_code, 403)
        self.assertEqual(self.llamar('diego', 'delete', f'/api/renglones/{id_r}').status_code, 403)
        # ...pero si la lee
        r = self.llamar('diego', 'get', f'/api/sesiones/{id_s}/renglones')
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.get_json()['es_propia'])
        self.assertEqual(len(r.get_json()['plan']), 1)
        # control positivo: Laura si edita, cierra y borra lo suyo
        self.assertEqual(self.llamar('laura', 'put', f'/api/renglones/{id_r}', json={'texto': 'nuevo'}).status_code, 200)
        # roles ajenos
        self.assertEqual(self.llamar('rrhh', 'get', f'/api/sesiones/{id_s}/renglones').status_code, 403)
        self.assertEqual(self.llamar(None, 'get', f'/api/sesiones/{id_s}/renglones').status_code, 401)
        self.assertEqual(self.llamar('laura', 'get', '/api/sesiones/99999/renglones').status_code, 404)
        self.assertEqual(self.llamar('laura', 'put', '/api/renglones/99999', json={'texto': 'x'}).status_code, 404)

    def test_editar_marcar_cerrar_reabrir_y_borrar(self):
        id_s = self._sesion(dia_habil_pasado(7), '08:00')
        id_r = self._renglon(id_s, 'plan').get_json()['renglon']['id']
        r = self.llamar('laura', 'put', f'/api/renglones/{id_r}', json={'texto': 'pinza fina', 'destacado': True})
        self.assertEqual(r.get_json()['renglon']['texto'], 'pinza fina')
        self.assertTrue(r.get_json()['renglon']['destacado'])
        r = self.llamar('laura', 'post', f'/api/renglones/{id_r}/cierre', json={'cierre': 'hecho'})
        self.assertEqual(r.get_json()['renglon']['cierre'], 'hecho')
        r = self.llamar('laura', 'post', f'/api/renglones/{id_r}/cierre', json={'cierre': None})   # reabrir
        self.assertIsNone(r.get_json()['renglon']['cierre'])
        r = self.llamar('laura', 'post', f'/api/renglones/{id_r}/cierre', json={'cierre': 'raro'})
        self.assertEqual((r.status_code, r.get_json()['campo']), (400, 'cierre'))
        # el registro no se cierra: solo el plan
        id_reg = self._renglon(id_s, 'registro').get_json()['renglon']['id']
        r = self.llamar('laura', 'post', f'/api/renglones/{id_reg}/cierre', json={'cierre': 'hecho'})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.llamar('laura', 'delete', f'/api/renglones/{id_r}').status_code, 200)
        self.assertEqual(self.llamar('laura', 'delete', f'/api/renglones/{id_r}').status_code, 404)

    # --- arrastre ----------------------------------------------------------
    def test_arrastre_de_lo_pendiente_hasta_cerrarlo(self):
        antes = self._sesion(dia_habil_pasado(20), '08:00', paciente=3)
        despues = self._sesion(dia_habil_pasado(2), '08:00', paciente=3)
        otro_paciente = self._sesion(dia_habil_pasado(2), '09:00', paciente=1)
        r1 = self._renglon(antes, 'plan', 'tijera punta roma').get_json()['renglon']['id']
        r2 = self._renglon(antes, 'plan', 'secuencia de 3 pasos').get_json()['renglon']['id']
        self._renglon(antes, 'registro', 'esto no se arrastra')
        d = self.llamar('laura', 'get', f'/api/sesiones/{despues}/renglones').get_json()
        self.assertEqual([a['texto'] for a in d['arrastre']], ['tijera punta roma', 'secuencia de 3 pasos'])
        self.assertEqual(d['arrastre'][0]['fecha_sesion'], dia_habil_pasado(20))
        # otro paciente no recibe nada
        self.assertEqual(self.llamar('laura', 'get', f'/api/sesiones/{otro_paciente}/renglones').get_json()['arrastre'], [])
        # la sesion de origen no se arrastra a si misma
        self.assertEqual(self.llamar('laura', 'get', f'/api/sesiones/{antes}/renglones').get_json()['arrastre'], [])
        # cerrar uno como hecho y otro como descartado los saca del arrastre
        self.llamar('laura', 'post', f'/api/renglones/{r1}/cierre', json={'cierre': 'hecho'})
        d = self.llamar('laura', 'get', f'/api/sesiones/{despues}/renglones').get_json()
        self.assertEqual([a['id'] for a in d['arrastre']], [r2])
        self.llamar('laura', 'post', f'/api/renglones/{r2}/cierre', json={'cierre': 'descartado'})
        self.assertEqual(self.llamar('laura', 'get', f'/api/sesiones/{despues}/renglones').get_json()['arrastre'], [])

    def test_el_plan_de_una_ausencia_se_arrastra(self):
        # "Ausente" anota al lado y lo planificado se mueve hacia adelante
        ausente = self._sesion(dia_habil_pasado(15), '10:00', paciente=3, estado='ausencia', ausencia_de='paciente')
        sig = self._sesion(dia_habil_pasado(1), '10:00', paciente=3)
        self._renglon(ausente, 'plan', 'juego con plastilina')
        d = self.llamar('laura', 'get', f'/api/sesiones/{sig}/renglones').get_json()
        self.assertEqual([a['texto'] for a in d['arrastre']], ['juego con plastilina'])

    def test_resumen_en_el_panel_del_dia(self):
        if hoy().weekday() > 4:
            self.skipTest('hoy es fin de semana: no se puede agendar para hoy')
        # las otras pruebas dejan pendientes del paciente 3: se mide la DIFERENCIA
        previo = self._arrastre_de_paciente_3_hoy()
        antes = self._sesion(dia_habil_pasado(25), '15:00', paciente=3)
        self._renglon(antes, 'plan', 'pendiente viejo')
        id_hoy = self._sesion(hoy().isoformat(), '16:00', paciente=3)
        self._renglon(id_hoy, 'plan', 'plan de hoy')
        self._renglon(id_hoy, 'registro', 'registro de hoy')
        sesiones = self.llamar('laura', 'get', '/api/sesiones/hoy').get_json()['sesiones']
        mia = next(s for s in sesiones if s['id'] == id_hoy)
        self.assertEqual((mia['renglones']['plan'], mia['renglones']['registro']), (1, 1))
        self.assertEqual(mia['renglones']['arrastre'], previo + 1)

    def _arrastre_de_paciente_3_hoy(self):
        # arrastre que tendria una sesion de hoy del paciente 3 (pendientes de fechas < hoy)
        f = self.sql("SELECT COUNT(*) FROM sesion_renglones r JOIN sesiones s ON s.id = r.id_sesion "
                     "WHERE r.momento='plan' AND r.cierre IS NULL AND s.id_paciente=3 AND s.id_terapeuta=1 "
                     "AND s.fecha < CURRENT_DATE")
        return int(f[0][0])

    def test_concurrencia_el_tope_de_30_es_exacto(self):
        import threading
        id_s = self._sesion(proximo_dia(4, 25), '08:00')
        token = self.token('laura')
        resultados = []

        def escribir(i):
            cliente = self.app.test_client()
            r = cliente.post(f'/api/sesiones/{id_s}/renglones',
                             headers={'Authorization': f'Bearer {token}'},
                             json={'momento': 'plan', 'texto': f'paralelo {i}'})
            resultados.append(r.status_code)

        hilos = [threading.Thread(target=escribir, args=(i,)) for i in range(40)]
        for h in hilos: h.start()
        for h in hilos: h.join()
        self.assertEqual(sorted(set(resultados)), [201, 400], resultados)
        self.assertEqual(resultados.count(201), 30)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM sesion_renglones WHERE id_sesion=:s", s=id_s)[0][0], 30)

    # --- la base, sin la API ----------------------------------------------
    def test_la_base_rechaza_lo_que_la_api_no_deja_pasar(self):
        id_s = self._sesion(dia_habil_pasado(8), '08:00')
        with self.app.app_context():
            from sqlalchemy import text
            for sql in ("INSERT INTO sesion_renglones (id_sesion, momento, texto, cierre) VALUES (%d, 'registro', 'x', 'hecho')" % id_s,
                        "INSERT INTO sesion_renglones (id_sesion, momento, texto) VALUES (%d, 'plan', '   ')" % id_s):
                with self.assertRaises(DBAPIError):
                    db.session.execute(text(sql))
                db.session.rollback()


if __name__ == '__main__':
    unittest.main()

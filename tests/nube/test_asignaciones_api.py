"""
tests/nube/test_asignaciones_api.py — HDU 11 por la API, con control positivo
al lado de cada rechazo.

seed.sql: terapeuta 1 = Laura, terapeuta 2 = Diego. Paciente 1 -> Laura
(vigente), 2 -> Diego, 3 -> Laura, 4 dado de baja.
"""
import unittest

from _base import BaseApi, dias, dia_habil_pasado


class AsignacionesApi(BaseApi):
    def test_terapeutas_solo_para_terapeutas(self):
        r = self.llamar('laura', 'get', '/api/terapeutas')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.get_json()['terapeutas']), 2)
        self.assertEqual(self.llamar('rrhh', 'get', '/api/terapeutas').status_code, 403)
        self.assertEqual(self.llamar('familiar', 'get', '/api/terapeutas').status_code, 403)
        self.assertEqual(self.llamar(None, 'get', '/api/terapeutas').status_code, 401)

    def test_historial_del_paciente_y_lectura_abierta(self):
        # Laura lee las asignaciones de un paciente que NO es suyo (lectura abierta)
        r = self.llamar('laura', 'get', '/api/pacientes/2/asignaciones')
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertEqual(d['vigentes'], 1)
        self.assertEqual(d['asignaciones'][0]['terapeuta'], 'Diego Moyano')
        # paciente 1 tiene una vigente y una cerrada: vigente primero
        d1 = self.llamar('laura', 'get', '/api/pacientes/1/asignaciones').get_json()
        self.assertEqual([a['vigente'] for a in d1['asignaciones']], [True, False])
        # paciente dado de baja: se puede leer
        self.assertEqual(self.llamar('laura', 'get', '/api/pacientes/4/asignaciones').status_code, 200)
        self.assertEqual(self.llamar('laura', 'get', '/api/pacientes/999/asignaciones').status_code, 404)
        self.assertEqual(self.llamar('rrhh', 'get', '/api/pacientes/2/asignaciones').status_code, 403)

    def test_abrir_y_rechazos(self):
        # control positivo: paciente 3 no tiene a Diego -> entra
        r = self.llamar('laura', 'post', '/api/pacientes/3/asignaciones', json={'id_terapeuta': 2})
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        id_a = r.get_json()['asignacion']['id']
        self.assertTrue(r.get_json()['asignacion']['vigente'])
        # segunda vigente del mismo par
        r = self.llamar('laura', 'post', '/api/pacientes/3/asignaciones', json={'id_terapeuta': 2})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.get_json()['campo'], 'id_terapeuta')
        # paciente de baja
        r = self.llamar('laura', 'post', '/api/pacientes/4/asignaciones', json={'id_terapeuta': 1})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.get_json()['campo'], 'id_paciente')
        # terapeuta inexistente, faltante, fecha futura y fecha mal escrita
        r = self.llamar('laura', 'post', '/api/pacientes/3/asignaciones', json={'id_terapeuta': 99})
        self.assertEqual((r.status_code, r.get_json()['campo']), (400, 'id_terapeuta'))
        r = self.llamar('laura', 'post', '/api/pacientes/3/asignaciones', json={})
        self.assertEqual((r.status_code, r.get_json()['campo']), (400, 'id_terapeuta'))
        r = self.llamar('laura', 'post', '/api/pacientes/1/asignaciones',
                        json={'id_terapeuta': 2, 'fecha_desde': dias(3)})
        self.assertEqual((r.status_code, r.get_json()['campo']), (400, 'fecha_desde'))
        r = self.llamar('laura', 'post', '/api/pacientes/1/asignaciones',
                        json={'id_terapeuta': 2, 'fecha_desde': '15/10/2026'})
        self.assertEqual((r.status_code, r.get_json()['campo']), (400, 'fecha_desde'))
        r = self.llamar('laura', 'post', '/api/pacientes/999/asignaciones', json={'id_terapeuta': 1})
        self.assertEqual(r.status_code, 400)
        # RRHH y familiar no escriben
        for quien in ('rrhh', 'familiar', 'paciente'):
            r = self.llamar(quien, 'post', '/api/pacientes/3/asignaciones', json={'id_terapeuta': 1})
            self.assertEqual(r.status_code, 403, quien)
        # cierre: ok, repetido 409, inexistente 404, rol 403
        self.assertEqual(self.llamar('rrhh', 'post', f'/api/asignaciones/{id_a}/cierre', json={}).status_code, 403)
        r = self.llamar('laura', 'post', f'/api/asignaciones/{id_a}/cierre', json={})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertFalse(r.get_json()['asignacion']['vigente'])
        self.assertEqual(self.llamar('laura', 'post', f'/api/asignaciones/{id_a}/cierre', json={}).status_code, 409)
        self.assertEqual(self.llamar('laura', 'post', '/api/asignaciones/99999/cierre', json={}).status_code, 404)
        # fecha de cierre anterior al inicio: la rechaza el trigger
        r = self.llamar('laura', 'post', '/api/pacientes/3/asignaciones', json={'id_terapeuta': 2})
        id_b = r.get_json()['asignacion']['id']
        r = self.llamar('laura', 'post', f'/api/asignaciones/{id_b}/cierre', json={'fecha_hasta': '2020-01-01'})
        self.assertEqual((r.status_code, r.get_json()['campo']), (400, 'fecha_hasta'))
        self.assertEqual(self.llamar('laura', 'post', f'/api/asignaciones/{id_b}/cierre', json={}).status_code, 200)

    def test_listado_marca_asignado_a_mi(self):
        d = self.llamar('laura', 'get', '/api/pacientes').get_json()['pacientes']
        por_id = {p['id']: p for p in d}
        self.assertTrue(por_id[1]['asignado_a_mi'])
        self.assertFalse(por_id[2]['asignado_a_mi'])
        self.assertEqual(por_id[2]['responsables'], ['Diego Moyano'])
        d2 = {p['id']: p for p in self.llamar('diego', 'get', '/api/pacientes').get_json()['pacientes']}
        self.assertTrue(d2[2]['asignado_a_mi'])
        self.assertFalse(d2[1]['asignado_a_mi'])


class Regla8PorApi(BaseApi):
    """Escribir solo sobre pacientes asignados a la fecha de la sesion."""

    def sesion(self, quien, id_paciente, fecha, hora='09:00:00'):
        return self.llamar(quien, 'post', '/api/sesiones', json={
            'id_paciente': id_paciente, 'fecha': fecha, 'hora_inicio': hora,
            'hora_fin': hora[:3] + '45:00', 'estado': 'completa'})

    def test_sesion_solo_con_asignacion_a_esa_fecha(self):
        f1 = dia_habil_pasado(1)
        # Laura NO tiene al paciente 2: rebota, y marca el campo
        r = self.sesion('laura', 2, f1)
        self.assertEqual(r.status_code, 400, r.get_data(as_text=True))
        self.assertEqual(r.get_json()['campo'], 'id_paciente')
        # control positivo: Laura registra sobre SU paciente 1 en el mismo horario
        r = self.sesion('laura', 1, f1)
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        # Se le asigna el paciente 2 desde hace 10 dias y se la cierra hace 5
        # (dias corridos: las fechas de abajo se usan tal cual)
        r = self.llamar('laura', 'post', '/api/pacientes/2/asignaciones',
                        json={'id_terapeuta': 1, 'fecha_desde': dias(-10)})
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        id_a = r.get_json()['asignacion']['id']
        r = self.llamar('laura', 'post', f'/api/asignaciones/{id_a}/cierre',
                        json={'fecha_hasta': dias(-5)})
        self.assertEqual(r.status_code, 200)
        # carga retroactiva DENTRO de la ventana: entra
        dentro = dia_habil_pasado(7)
        self.assertLessEqual(dentro, dias(-5))
        self.assertGreaterEqual(dentro, dias(-10))
        r = self.sesion('laura', 2, dentro, '10:00:00')
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        # FUERA de la ventana (despues del cierre): rebota
        r = self.sesion('laura', 2, dia_habil_pasado(1), '11:00:00')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.get_json()['campo'], 'id_paciente')

    def test_lectura_abierta_entre_terapeutas(self):
        for ruta in ('/api/pacientes/2', '/api/pacientes/2/sesiones', '/api/pacientes/2/evolucion'):
            self.assertEqual(self.llamar('laura', 'get', ruta).status_code, 200, ruta)

    def test_evolucion_sobre_paciente_ajeno_se_rechaza_en_la_base(self):
        # Una sesion de Diego sobre el paciente 2 (suya), y Laura NO puede
        # cargar evolucion ahi (autoria). Para la regla 8 en si, por SQL:
        # un INSERT directo de sesion de Laura sobre paciente 2 tambien rebota.
        with self.app.app_context():
            from sqlalchemy import text
            from sqlalchemy.exc import SQLAlchemyError
            try:
                db_sess = __import__('app').db.session
                db_sess.execute(text(
                    "INSERT INTO sesiones (id_terapeuta,id_paciente,fecha,hora_inicio,hora_fin,estado) "
                    "VALUES (1,2,CURDATE() - INTERVAL 2 DAY,'15:00:00','15:45:00','completa')"))
                db_sess.commit()
                self.fail('El INSERT directo no deberia entrar (regla 8 en la base)')
            except SQLAlchemyError as e:
                __import__('app').db.session.rollback()
                self.assertIn('no tiene asignado', str(e))


class AltaConAsignacionApi(BaseApi):
    def _alta(self, quien, extra=None, historia='HC-9001'):
        cuerpo = {'nombre': 'Test', 'apellido': 'Alta', 'fecha_nacimiento': '2015-03-02',
                  'nro_historia': historia}
        cuerpo.update(extra or {})
        return self.llamar(quien, 'post', '/api/pacientes', json=cuerpo)

    def test_alta_asigna_a_quien_la_hace_por_omision(self):
        r = self._alta('laura')
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        idp = r.get_json()['paciente']['id']
        d = self.llamar('laura', 'get', f'/api/pacientes/{idp}/asignaciones').get_json()
        self.assertEqual(d['vigentes'], 1)
        self.assertEqual(d['asignaciones'][0]['terapeuta'], 'Laura Fernandez')

    def test_alta_con_responsable_elegido(self):
        r = self._alta('laura', {'id_terapeuta': 2}, 'HC-9002')
        self.assertEqual(r.status_code, 201)
        idp = r.get_json()['paciente']['id']
        d = self.llamar('laura', 'get', f'/api/pacientes/{idp}/asignaciones').get_json()
        self.assertEqual(d['asignaciones'][0]['id_terapeuta'], 2)
        # el listado lo marca como de Diego y no mio para Laura
        lista = self.llamar('laura', 'get', '/api/pacientes').get_json()['pacientes']
        p = next(x for x in lista if x['id'] == idp)
        self.assertFalse(p['asignado_a_mi'])
        self.assertEqual(p['responsables'], ['Diego Moyano'])

    def test_alta_con_responsable_inexistente_no_pierde_al_paciente(self):
        r = self._alta('laura', {'id_terapeuta': 99}, 'HC-9003')
        self.assertEqual(r.status_code, 201)
        self.assertIn('Asignalo desde la ficha', r.get_json()['mensaje'])
        idp = r.get_json()['paciente']['id']
        d = self.llamar('laura', 'get', f'/api/pacientes/{idp}/asignaciones').get_json()
        self.assertEqual(d['vigentes'], 0)


if __name__ == '__main__':
    unittest.main()

"""
tests/nube/test_usabilidad_ola3.py — correcciones de la tercera ola de pruebas
de usabilidad (personas con mucho conocimiento): corregir o quitar una
calificacion con el registro abierto, no mover al futuro una sesion ya
registrada, no reutilizar la contrasena actual. Control positivo junto a cada
rechazo. seed.sql: paciente 1 -> Laura.
"""
import datetime as dt
import unittest

from _base import BaseApi, hoy

HORA = '00:20:00'


class CorregirCalificacion(BaseApi):
    def setUp(self):
        self._limpiar()
        self.sql(f"INSERT INTO sesiones (id_terapeuta, id_paciente, fecha, hora_inicio, hora_fin, estado) "
                 f"VALUES (1, 1, CURDATE(), '{HORA}', '00:50:00', 'incompleta')")
        self.id_sesion = self.sql(f"SELECT id FROM sesiones WHERE id_paciente = 1 AND fecha = CURDATE() AND hora_inicio = '{HORA}'")[0][0]
        self.id_objetivo = self.sql('SELECT id FROM objetivos_terapeuticos WHERE id_paciente = 1 AND activo = TRUE ORDER BY id LIMIT 1')[0][0]
        r = self.llamar('laura', 'post', '/api/evoluciones',
                        json={'id_sesion': self.id_sesion, 'id_objetivo': self.id_objetivo, 'valor': 5})
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        self.id_evolucion = r.get_json()['evolucion']['id']

    def tearDown(self):
        self._limpiar()

    def _limpiar(self):
        self.sql(f"DELETE FROM evoluciones WHERE id_sesion IN (SELECT id FROM (SELECT id FROM sesiones WHERE id_paciente = 1 AND hora_inicio = '{HORA}') x)")
        self.sql(f"DELETE FROM sesiones WHERE id_paciente = 1 AND hora_inicio = '{HORA}'")

    def _valor(self):
        filas = self.sql(f'SELECT valor FROM evoluciones WHERE id = {self.id_evolucion}')
        return filas[0][0] if filas else None

    def test_el_terapeuta_corrige_con_el_registro_abierto(self):
        r = self.llamar('laura', 'put', f'/api/evoluciones/{self.id_evolucion}', json={'valor': 1, 'observaciones': 'Corregida'})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(r.get_json()['mensaje'], 'Calificación corregida')
        self.assertEqual(self._valor(), 1)

    def test_otro_terapeuta_no_corrige(self):
        r = self.llamar('diego', 'put', f'/api/evoluciones/{self.id_evolucion}', json={'valor': 1})
        self.assertEqual(r.status_code, 403, r.get_data(as_text=True))
        self.assertEqual(self._valor(), 5)

    def test_con_la_sesion_terminada_hay_que_reabrir(self):
        self.sql(f"UPDATE sesiones SET estado = 'completa' WHERE id = {self.id_sesion}")
        r = self.llamar('laura', 'put', f'/api/evoluciones/{self.id_evolucion}', json={'valor': 1})
        self.assertEqual(r.status_code, 400)
        self.assertIn('reabra el registro', r.get_json()['mensaje'])
        self.assertEqual(self._valor(), 5)
        # control: reabierta, se corrige
        self.sql(f"UPDATE sesiones SET estado = 'incompleta' WHERE id = {self.id_sesion}")
        self.assertEqual(self.llamar('laura', 'put', f'/api/evoluciones/{self.id_evolucion}', json={'valor': 1}).status_code, 200)

    def test_valor_fuera_de_escala_y_evolucion_inexistente(self):
        r = self.llamar('laura', 'put', f'/api/evoluciones/{self.id_evolucion}', json={'valor': 9})
        self.assertEqual((r.status_code, r.get_json().get('campo')), (400, 'valor'))
        self.assertEqual(self.llamar('laura', 'put', '/api/evoluciones/999999', json={'valor': 2}).status_code, 404)

    def test_quitar_deja_el_objetivo_sin_calificar(self):
        r = self.llamar('laura', 'delete', f'/api/evoluciones/{self.id_evolucion}')
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertIsNone(self._valor())

    def test_una_sesion_registrada_no_se_mueve_al_futuro(self):
        futuro = (hoy() + dt.timedelta(days=60)).isoformat()
        cuerpo = {'estado': 'incompleta', 'ausencia_de': None, 'notas': None, 'fecha': futuro,
                  'hora_inicio': '00:20', 'hora_fin': '00:50'}
        r = self.llamar('laura', 'put', f'/api/sesiones/{self.id_sesion}', json=cuerpo)
        self.assertEqual(r.status_code, 400, r.get_data(as_text=True))
        self.assertEqual(r.get_json().get('campo'), 'fecha')
        self.assertEqual(self.sql(f'SELECT fecha FROM sesiones WHERE id = {self.id_sesion}')[0][0], hoy())
        # control: sin calificaciones, una sesion sin cerrar si se reprograma
        self.llamar('laura', 'delete', f'/api/evoluciones/{self.id_evolucion}')
        r = self.llamar('laura', 'put', f'/api/sesiones/{self.id_sesion}', json=cuerpo)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))


class ContrasenaRepetida(BaseApi):
    def test_restablecer_no_acepta_la_contrasena_actual(self):
        from _base import CONTRASENA, EMAILS
        r = self.client.post('/api/auth/recuperar', json={'email': EMAILS['jorge']})
        token = r.get_json().get('token_desarrollo')
        self.assertTrue(token, r.get_data(as_text=True))
        r = self.client.post('/api/auth/restablecer', json={'token': token, 'contrasena_nueva': CONTRASENA})
        self.assertEqual(r.status_code, 400, r.get_data(as_text=True))
        self.assertIn('distinta de la actual', r.get_json()['mensaje'])
        # control: una clave nueva se acepta; se vuelve a la de siempre por la base
        r = self.client.post('/api/auth/restablecer', json={'token': token, 'contrasena_nueva': 'Otraclave77'})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        import bcrypt
        hash_ = bcrypt.hashpw(CONTRASENA.encode(), bcrypt.gensalt(rounds=4)).decode()
        self.sql(f"UPDATE usuarios SET contrasena_hash = '{hash_}' WHERE email = '{EMAILS['jorge']}'")


if __name__ == '__main__':
    unittest.main()

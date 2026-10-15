"""
tests/nube/test_seguridad_api.py — bloqueo por intentos fallidos (bloque 3) y
recuperacion de contrasena (bloque 2), con control positivo junto a cada rechazo.
"""
import unittest

from sqlalchemy import text

from _base import BaseApi, CONTRASENA, EMAILS, db

URL = '/api/auth/login'


class SeguridadApi(BaseApi):
    def setUp(self):
        self.cliente = self.app.test_client()
        # Estas pruebas cambian claves, bloqueos y altas: se guarda el estado
        # y se restaura al final para no ensuciar a las otras suites.
        self._guardado = self.sql(
            "SELECT id, contrasena_hash, activo FROM usuarios")
        self.sql("UPDATE usuarios SET intentos_fallidos=0, bloqueado_hasta=NULL, "
                 "token_recuperacion=NULL, token_expira=NULL")

    def tearDown(self):
        for id_, hash_, activo in self._guardado:
            self.sql("UPDATE usuarios SET contrasena_hash=:h, activo=:a, intentos_fallidos=0, "
                     "bloqueado_hasta=NULL, token_recuperacion=NULL, token_expira=NULL WHERE id=:i",
                     h=hash_, a=activo, i=id_)

    def _login(self, quien, clave):
        return self.cliente.post(URL, json={'email': EMAILS[quien], 'contrasena': clave})

    def _estado(self, quien):
        with self.app.app_context():
            r = db.session.execute(text(
                "SELECT intentos_fallidos, bloqueado_hasta IS NOT NULL FROM usuarios WHERE email=:e"),
                {'e': EMAILS[quien]}).first()
            db.session.rollback()
        return tuple(r)

    def test_bloqueo_tras_cinco_fallos_y_rechaza_la_clave_correcta(self):
        for i in range(4):
            r = self._login('diego', 'mala')
            self.assertEqual(r.status_code, 401, i)
        self.assertEqual(self._estado('diego'), (4, 0))
        r = self._login('diego', 'mala')            # quinto: bloquea
        self.assertEqual(r.status_code, 429)
        self.assertIn('Demasiados intentos', r.get_json()['mensaje'])
        # con la cuenta bloqueada, ni la clave correcta entra
        r = self._login('diego', CONTRASENA)
        self.assertEqual(r.status_code, 429)
        # el bloqueo es solo de esa cuenta (control positivo)
        self.assertEqual(self._login('laura', CONTRASENA).status_code, 200)

    def test_acierto_reinicia_el_contador(self):
        for _ in range(3):
            self._login('diego', 'mala')
        self.assertEqual(self._estado('diego'), (3, 0))
        self.assertEqual(self._login('diego', CONTRASENA).status_code, 200)
        self.assertEqual(self._estado('diego'), (0, 0))

    def test_bloqueo_vencido_empieza_de_cero(self):
        for _ in range(5):
            self._login('diego', 'mala')
        with self.app.app_context():
            db.session.execute(text(
                "UPDATE usuarios SET bloqueado_hasta = NOW() - INTERVAL 1 MINUTE WHERE email=:e"),
                {'e': EMAILS['diego']})
            db.session.commit()
        r = self._login('diego', 'mala')            # primer fallo de la nueva tanda
        self.assertEqual(r.status_code, 401)
        self.assertEqual(self._estado('diego'), (1, 0))
        self.assertEqual(self._login('diego', CONTRASENA).status_code, 200)

    def test_email_inexistente_no_bloquea_ni_cambia_el_mensaje(self):
        for _ in range(7):
            r = self.cliente.post(URL, json={'email': 'nadie@asisto.local', 'contrasena': 'x'})
            self.assertEqual(r.status_code, 401)
            self.assertEqual(r.get_json()['mensaje'], 'Email o contrasena incorrectos.')

    # --- recuperacion -----------------------------------------------------
    def _pedir(self, email):
        return self.cliente.post('/api/auth/recuperar', json={'email': email})

    def test_recuperar_misma_respuesta_exista_o_no(self):
        a = self._pedir(EMAILS['laura'])
        b = self._pedir('nadie@asisto.local')
        self.assertEqual((a.status_code, b.status_code), (200, 200))
        self.assertEqual(a.get_json()['mensaje'], b.get_json()['mensaje'])
        self.assertIn('token_desarrollo', a.get_json())      # solo en modo desarrollo
        self.assertNotIn('token_desarrollo', b.get_json())   # no delata la cuenta
        self.assertEqual(self._pedir('').status_code, 400)

    def test_restablecer_flujo_completo_y_un_solo_uso(self):
        token = self._pedir(EMAILS['diego']).get_json()['token_desarrollo']
        # el token no se guarda en claro
        with self.app.app_context():
            guardado = db.session.execute(text(
                "SELECT token_recuperacion FROM usuarios WHERE email=:e"), {'e': EMAILS['diego']}).scalar()
            db.session.rollback()
        self.assertNotEqual(guardado, token)
        self.assertEqual(len(guardado), 64)
        # rechazos de la clave nueva (campo) y token invalido
        r = self.cliente.post('/api/auth/restablecer', json={'token': token, 'contrasena_nueva': 'corta1'})
        self.assertEqual((r.status_code, r.get_json()['campo']), (400, 'contrasena_nueva'))
        r = self.cliente.post('/api/auth/restablecer', json={'token': token, 'contrasena_nueva': 'soloLetrasAqui'})
        self.assertEqual((r.status_code, r.get_json()['campo']), (400, 'contrasena_nueva'))
        r = self.cliente.post('/api/auth/restablecer', json={'token': 'inventado', 'contrasena_nueva': 'NuevaClave2026'})
        self.assertEqual((r.status_code, r.get_json()['campo']), (400, 'token'))
        # control positivo: el mismo token, con una clave valida, funciona
        r = self.cliente.post('/api/auth/restablecer', json={'token': token, 'contrasena_nueva': 'NuevaClave2026'})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(self._login('diego', 'NuevaClave2026').status_code, 200)
        self.assertEqual(self._login('diego', CONTRASENA).status_code, 401)
        # un solo uso
        r = self.cliente.post('/api/auth/restablecer', json={'token': token, 'contrasena_nueva': 'OtraClave2026'})
        self.assertEqual(r.status_code, 400)

    def test_token_vencido_y_pedido_nuevo_invalida_el_anterior(self):
        t1 = self._pedir(EMAILS['laura']).get_json()['token_desarrollo']
        t2 = self._pedir(EMAILS['laura']).get_json()['token_desarrollo']
        r = self.cliente.post('/api/auth/restablecer', json={'token': t1, 'contrasena_nueva': 'NuevaClave2026'})
        self.assertEqual(r.status_code, 400)             # el primero quedo invalidado
        with self.app.app_context():
            db.session.execute(text("UPDATE usuarios SET token_expira = NOW() - INTERVAL 1 MINUTE WHERE email=:e"),
                               {'e': EMAILS['laura']})
            db.session.commit()
        r = self.cliente.post('/api/auth/restablecer', json={'token': t2, 'contrasena_nueva': 'NuevaClave2026'})
        self.assertEqual(r.status_code, 400)             # vencido

    def test_restablecer_levanta_el_bloqueo(self):
        for _ in range(5):
            self._login('diego', 'mala')
        self.assertEqual(self._login('diego', CONTRASENA).status_code, 429)
        token = self._pedir(EMAILS['diego']).get_json()['token_desarrollo']
        self.assertEqual(self.cliente.post('/api/auth/restablecer',
                         json={'token': token, 'contrasena_nueva': 'NuevaClave2026'}).status_code, 200)
        self.assertEqual(self._login('diego', 'NuevaClave2026').status_code, 200)

    def test_cuenta_inactiva_no_recibe_enlace(self):
        with self.app.app_context():
            db.session.execute(text("UPDATE usuarios SET activo=FALSE WHERE email=:e"), {'e': EMAILS['familiar']})
            db.session.commit()
        self.assertNotIn('token_desarrollo', self._pedir(EMAILS['familiar']).get_json())


if __name__ == '__main__':
    unittest.main()

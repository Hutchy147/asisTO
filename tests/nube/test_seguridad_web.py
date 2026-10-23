"""
tests/nube/test_seguridad_web.py — endurecimiento web (auditoria de seguridad
de la V6): sesion en cookie HttpOnly con defensa CSRF, revocacion de sesiones,
cabeceras, limites por IP, politica de contrasenas y configuracion insegura.
Control positivo junto a cada rechazo.
"""
import unittest

from _base import BaseApi, CONTRASENA, EMAILS


class SesionEnCookie(BaseApi):
    def _navegador(self):
        """Cliente CON cookies, como un navegador."""
        return self.app.test_client()

    def _entrar(self, cliente, quien='laura'):
        r = cliente.post('/api/auth/login', json={'email': EMAILS[quien], 'contrasena': CONTRASENA})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        return r

    def test_la_cookie_es_httponly_strict_y_solo_para_la_api(self):
        r = self._entrar(self._navegador())
        cookie = r.headers.get('Set-Cookie', '')
        self.assertIn('asisto_sesion=', cookie)
        for atributo in ('HttpOnly', 'SameSite=Strict', 'Path=/api'):
            self.assertIn(atributo, cookie)

    def test_la_cookie_autentica_y_exige_la_cabecera_del_cliente_para_escribir(self):
        nav = self._navegador()
        self._entrar(nav)
        # lectura con la cookie sola: anda
        self.assertEqual(nav.get('/api/auth/me').status_code, 200)
        # escritura sin la cabecera X-AsisTO: CSRF, rechazada
        cuerpo = {'id_paciente': 1, 'descripcion': 'objetivo csrf de prueba'}
        r = nav.post('/api/objetivos', json=cuerpo)
        self.assertEqual((r.status_code, r.get_json()['codigo']), (403, 'solicitud_no_confiable'))
        self.assertEqual(self.sql("SELECT COUNT(*) FROM objetivos_terapeuticos WHERE descripcion = 'objetivo csrf de prueba'")[0][0], 0)
        # control positivo: con la cabecera, el pedido llega a la regla de negocio
        r = nav.post('/api/objetivos', json=cuerpo, headers={'X-AsisTO': '1'})
        self.assertNotEqual(r.status_code, 403, r.get_data(as_text=True))
        self.sql("DELETE FROM objetivos_terapeuticos WHERE descripcion = 'objetivo csrf de prueba'")

    def test_cerrar_sesion_revoca_los_tokens_emitidos(self):
        nav = self._navegador()
        token = self._entrar(nav, 'diego').get_json()['token']
        self.assertEqual(self.client.get('/api/auth/me', headers={'Authorization': f'Bearer {token}'}).status_code, 200)
        r = nav.post('/api/auth/logout', headers={'X-AsisTO': '1'})
        self.assertEqual(r.status_code, 200)
        self.assertIn('asisto_sesion=;', r.headers.get('Set-Cookie', ''))
        # el token copiado antes del logout ya no sirve, tampoco la cookie
        r = self.client.get('/api/auth/me', headers={'Authorization': f'Bearer {token}'})
        self.assertEqual(r.status_code, 401, r.get_data(as_text=True))
        self.assertEqual(nav.get('/api/auth/me').status_code, 401)
        # control positivo: un login nuevo vuelve a entrar
        token2 = self._entrar(self._navegador(), 'diego').get_json()['token']
        self.assertEqual(self.client.get('/api/auth/me', headers={'Authorization': f'Bearer {token2}'}).status_code, 200)
        self._tokens.pop('diego', None)

    def test_el_ingreso_avisa_los_intentos_fallidos_desde_el_anterior(self):
        email = EMAILS['rrhh']
        # ingreso de referencia: a partir de aca se cuenta
        self.assertEqual(self._entrar(self._navegador(), 'rrhh').get_json()['intentos_fallidos'] >= 0, True)
        for _ in range(2):
            r = self.client.post('/api/auth/login', json={'email': email, 'contrasena': 'equivocada123'})
            self.assertEqual(r.status_code, 401)
        self.assertEqual(self._entrar(self._navegador(), 'rrhh').get_json()['intentos_fallidos'], 2)
        # control: el siguiente ingreso ya no los repite
        self.assertEqual(self._entrar(self._navegador(), 'rrhh').get_json()['intentos_fallidos'], 0)

    def test_restablecer_la_contrasena_revoca_las_sesiones(self):
        token = self._entrar(self._navegador(), 'rrhh').get_json()['token']
        enlace = self.client.post('/api/auth/recuperar', json={'email': EMAILS['rrhh']}).get_json().get('token_desarrollo')
        if not enlace:
            self.skipTest('RECUPERACION_MOSTRAR_TOKEN apagado en este entorno')
        r = self.client.post('/api/auth/restablecer', json={'token': enlace, 'contrasena_nueva': CONTRASENA})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(self.client.get('/api/auth/me', headers={'Authorization': f'Bearer {token}'}).status_code, 401)
        self._tokens.pop('rrhh', None)


class Cabeceras(BaseApi):
    def test_cabeceras_de_endurecimiento(self):
        for r in (self.client.get('/api/health'), self.llamar('laura', 'get', '/api/pacientes'),
                  self.client.get('/api/no-existe')):
            h = r.headers
            self.assertEqual(h.get('X-Content-Type-Options'), 'nosniff')
            self.assertEqual(h.get('X-Frame-Options'), 'DENY')
            self.assertIn("frame-ancestors 'none'", h.get('Content-Security-Policy', ''))
            self.assertEqual(h.get('Referrer-Policy'), 'no-referrer')
            self.assertEqual(h.get('Cache-Control'), 'no-store')

    def test_cuerpo_demasiado_grande(self):
        r = self.client.post('/api/auth/login', data='x' * (2 * 1024 * 1024), content_type='application/json')
        self.assertEqual(r.status_code, 413)
        # control positivo: un cuerpo normal sigue andando
        self.assertEqual(self.client.post('/api/auth/login', json={'email': 'a@b.c', 'contrasena': 'x'}).status_code, 401)


class LimitesPorIp(BaseApi):
    def setUp(self):
        from app.utils import limites
        limites.reiniciar()
        self._previo = dict(self.app.config['LIMITES_POR_IP'])
        self.app.config['LIMITES_POR_IP'] = {'login_fallido': (3, 15), 'recuperar': (2, 15), 'restablecer': (2, 15)}

    def tearDown(self):
        from app.utils import limites
        limites.reiniciar()
        self.app.config['LIMITES_POR_IP'] = self._previo

    def test_password_spraying_desde_una_ip_se_corta(self):
        # tres emails DISTINTOS (ninguno llega a su bloqueo por cuenta)
        for i in range(3):
            r = self.client.post('/api/auth/login', json={'email': f'spray{i}@asisto.local', 'contrasena': 'Primavera2026'})
            self.assertEqual(r.status_code, 401)
        r = self.client.post('/api/auth/login', json={'email': 'spray9@asisto.local', 'contrasena': 'Primavera2026'})
        self.assertEqual(r.status_code, 429)
        self.assertTrue(r.headers.get('Retry-After'))
        # mientras dura, ni la clave correcta entra desde esa IP
        r = self.client.post('/api/auth/login', json={'email': EMAILS['laura'], 'contrasena': CONTRASENA})
        self.assertEqual(r.status_code, 429)

    def test_los_logins_correctos_no_cuentan(self):
        for _ in range(5):
            r = self.client.post('/api/auth/login', json={'email': EMAILS['laura'], 'contrasena': CONTRASENA})
            self.assertEqual(r.status_code, 200)

    def test_recuperar_y_restablecer_tienen_tope(self):
        for _ in range(2):
            self.assertEqual(self.client.post('/api/auth/recuperar', json={'email': 'x@asisto.local'}).status_code, 200)
        self.assertEqual(self.client.post('/api/auth/recuperar', json={'email': 'x@asisto.local'}).status_code, 429)
        for _ in range(2):
            self.client.post('/api/auth/restablecer/verificar', json={'token': 'adivinado'})
        self.assertEqual(self.client.post('/api/auth/restablecer/verificar', json={'token': 'adivinado'}).status_code, 429)


class PoliticaYConfiguracion(BaseApi):
    def test_contrasena_comun_o_con_el_email_se_rechaza(self):
        enlace = self.client.post('/api/auth/recuperar', json={'email': EMAILS['paciente']}).get_json().get('token_desarrollo')
        if not enlace:
            self.skipTest('RECUPERACION_MOSTRAR_TOKEN apagado en este entorno')
        for clave, fragmento in (('password123', 'común'), ('camila.rios99', 'email')):
            r = self.client.post('/api/auth/restablecer', json={'token': enlace, 'contrasena_nueva': clave})
            self.assertEqual(r.status_code, 400, clave)
            self.assertIn(fragmento, r.get_json()['mensaje'])
        # control positivo: el enlace sigue vigente y una clave razonable entra
        r = self.client.post('/api/auth/restablecer', json={'token': enlace, 'contrasena_nueva': CONTRASENA})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self._tokens.pop('paciente', None)

    def test_configuracion_insegura_no_arranca(self):
        from config import Config, ConfigInvalida

        def con(**valores):
            return type('C', (Config,), valores)

        largo = 'x' * 40
        with self.assertRaises(ConfigInvalida):
            con(SECRET_KEY='corto', JWT_SECRET_KEY=largo).validar()
        with self.assertRaises(ConfigInvalida):
            con(SECRET_KEY=largo, JWT_SECRET_KEY=largo).validar()
        with self.assertRaises(ConfigInvalida):
            con(SECRET_KEY=largo, JWT_SECRET_KEY='y' * 40, DEBUG=False, RECUPERACION_MOSTRAR_TOKEN=True).validar()
        con(SECRET_KEY=largo, JWT_SECRET_KEY='y' * 40, DEBUG=False, RECUPERACION_MOSTRAR_TOKEN=False).validar()

    def test_contrasena_temporal_sin_caracteres_ambiguos(self):
        from app.services.familiares_service import generar_contrasena_temporal
        claves = ''.join(generar_contrasena_temporal() for _ in range(300))
        self.assertFalse(set(claves) & set('IlO01'))


if __name__ == '__main__':
    unittest.main()

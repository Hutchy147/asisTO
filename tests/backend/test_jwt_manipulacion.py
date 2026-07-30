"""
tests/backend/test_jwt_manipulacion.py

Ataques directos contra el JWT: firma alterada, claims modificados sin
poder re-firmar, algoritmo 'none', expirado. Todos deben terminar en 401
con CODIGO_TOKEN_INVALIDO o CODIGO_TOKEN_EXPIRADO segun corresponda, nunca
en un 200 ni en un 500.

Se prueba contra /auth/me, el unico endpoint protegido real que existe hoy
(no hay endpoints de negocio todavia). Ver test_rbac_mecanismo.py para la
verificacion de roles con rutas de prueba.

Requiere la base de pruebas asisto_test_backend con hashes bcrypt reales
ya aplicados (ver _entorno.py).
"""

import unittest

import _entorno as e


class TestManipulacionJWT(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.id_usuario, cls.rol, cls.activo = e.obtener_usuario_por_email(e.EMAILS_SEED['terapeuta'])
        cls.email = e.EMAILS_SEED['terapeuta']

    def setUp(self):
        self.cliente = e.cliente()

    def test_token_valido_funciona(self):
        """Control: confirma que el resto de los tests compara contra algo que si funciona."""
        token = e.token_valido(self.id_usuario, self.rol, self.email)
        resp = self.cliente.get('/api/auth/me', headers=e.encabezado_auth(token))
        self.assertEqual(resp.status_code, 200, resp.get_json())

    def test_firma_alterada_rechazada(self):
        token = e.token_firma_alterada(self.id_usuario, self.rol, self.email)
        resp = self.cliente.get('/api/auth/me', headers=e.encabezado_auth(token))
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.get_json().get('codigo'), 'token_invalido')

    def test_claims_modificados_sin_resfirmar_rechazado(self):
        """
        El ataque relevante: interceptar un token real y subirse el rol a
        mano. Como no se conoce JWT_SECRET_KEY, la firma queda invalida.
        """
        token_original = e.token_valido(self.id_usuario, self.rol, self.email)
        token_forjado = e.token_claims_modificados_sin_resfirmar(
            token_original, {'rol': 'rrhh', 'sub': str(self.id_usuario)}
        )
        resp = self.cliente.get('/api/auth/me', headers=e.encabezado_auth(token_forjado))
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.get_json().get('codigo'), 'token_invalido')

    def test_algoritmo_none_rechazado(self):
        """
        Ataque clasico de confusion de algoritmo: token sin firma que
        declara alg=none. decodificar_token fija algorithms=['HS256']
        explicitamente, asi que PyJWT debe rechazarlo igual.
        """
        token = e.token_alg_none(self.id_usuario, self.rol, self.email)
        resp = self.cliente.get('/api/auth/me', headers=e.encabezado_auth(token))
        self.assertEqual(resp.status_code, 401)
        self.assertIn(resp.get_json().get('codigo'), ('token_invalido', 'token_faltante'))

    def test_firmado_con_otro_secreto_rechazado(self):
        """Un atacante que arma su propio token con una clave inventada."""
        token = e.token_firmado_con_otro_secreto(self.id_usuario, self.rol, self.email)
        resp = self.cliente.get('/api/auth/me', headers=e.encabezado_auth(token))
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.get_json().get('codigo'), 'token_invalido')

    def test_expirado_rechazado_con_codigo_propio(self):
        token = e.token_expirado(self.id_usuario, self.rol, self.email)
        resp = self.cliente.get('/api/auth/me', headers=e.encabezado_auth(token))
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.get_json().get('codigo'), 'token_expirado')

    def test_sin_token_es_401_token_faltante(self):
        resp = self.cliente.get('/api/auth/me')
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.get_json().get('codigo'), 'token_faltante')

    def test_header_sin_bearer_es_token_faltante(self):
        resp = self.cliente.get('/api/auth/me', headers={'Authorization': 'Token abc.def.ghi'})
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.get_json().get('codigo'), 'token_faltante')

    def test_token_vacio_tras_bearer_es_token_faltante(self):
        resp = self.cliente.get('/api/auth/me', headers={'Authorization': 'Bearer '})
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.get_json().get('codigo'), 'token_faltante')

    def test_token_con_sub_no_numerico_no_rompe_con_500(self):
        """
        db_obtener_usuario hace int(id_usuario): un 'sub' no numerico no
        deberia tirar un error sin capturar.
        """
        token = e.token_valido('no-es-un-id', self.rol, self.email)
        resp = self.cliente.get('/api/auth/me', headers=e.encabezado_auth(token))
        self.assertIn(resp.status_code, (401,))
        self.assertNotEqual(resp.status_code, 500)

    def test_token_de_usuario_inexistente_no_rompe_con_500(self):
        token = e.token_valido(999999999, 'terapeuta', 'nadie@asisto.local')
        resp = self.cliente.get('/api/auth/me', headers=e.encabezado_auth(token))
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.get_json().get('codigo'), 'usuario_inactivo')


if __name__ == '__main__':
    unittest.main()

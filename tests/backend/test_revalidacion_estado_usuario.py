"""
tests/backend/test_revalidacion_estado_usuario.py

La pregunta central de esta ronda: si el rol viaja en el token, ¿se confia
en el claim o se revalida contra la base en cada request? Y si un usuario
se da de baja despues de emitido el token, ¿el token viejo sigue sirviendo
hasta que expira?

Estos tests ESCRIBEN sobre la base de pruebas (activo/rol de un usuario) y
lo restauran en tearDown, para no dejar la base de pruebas en un estado
raro para el resto de los tests del modulo.
"""

import unittest

import _entorno as e


class TestRevalidacionEstadoUsuario(unittest.TestCase):

    def setUp(self):
        self.cliente = e.cliente()
        self.id_usuario, self.rol_original, self.activo_original = e.obtener_usuario_por_email(
            e.EMAILS_SEED['terapeuta']
        )
        self.email = e.EMAILS_SEED['terapeuta']

    def tearDown(self):
        e.restaurar_usuario(self.id_usuario, activo=self.activo_original, rol=self.rol_original)

    def test_dar_de_baja_despues_de_emitir_el_token_corta_el_acceso_de_inmediato(self):
        """
        El escenario exacto que pidio Terminal 2 auditar: token emitido
        mientras el usuario estaba activo, usuario dado de baja DESPUES,
        token usado DESPUES de la baja pero ANTES de que expire.
        """
        token = e.token_valido(self.id_usuario, self.rol_original, self.email)

        # Confirmar que el token funciona ANTES de la baja
        resp_antes = self.cliente.get('/api/auth/me', headers=e.encabezado_auth(token))
        self.assertEqual(resp_antes.status_code, 200, resp_antes.get_json())

        e.establecer_activo(self.id_usuario, False)

        resp_despues = self.cliente.get('/api/auth/me', headers=e.encabezado_auth(token))
        self.assertEqual(
            resp_despues.status_code, 401,
            'El token siguio sirviendo despues de dar de baja al usuario: '
            'se estaria confiando en el token en vez de revalidar contra la base.'
        )
        self.assertEqual(resp_despues.get_json().get('codigo'), 'usuario_inactivo')

    def test_cambiar_el_rol_despues_de_emitir_el_token_se_refleja_de_inmediato(self):
        """
        Token emitido con rol='terapeuta' en el claim. Se cambia el rol
        REAL del usuario en la base a 'rrhh' DESPUES de emitido el token,
        sin emitir uno nuevo. Una ruta que exige 'terapeuta' debe rechazar
        ese token ahora (el rol viejo del claim no debe alcanzar), y una
        ruta que exige 'rrhh' debe aceptarlo (el rol nuevo de la base es
        el que cuenta).
        """
        token_viejo = e.token_valido(self.id_usuario, 'terapeuta', self.email)  # claim dice 'terapeuta'
        e.establecer_rol(self.id_usuario, 'rrhh')  # la base ahora dice 'rrhh'

        # Rutas de prueba ya registradas por _entorno.obtener_app() al
        # crearse la app (una sola vez, antes del primer request: Flask no
        # permite agregar rutas nuevas despues).
        resp_terapeuta = self.cliente.get(e.RUTA_SOLO_TERAPEUTA, headers=e.encabezado_auth(token_viejo))
        resp_rrhh = self.cliente.get(e.RUTA_SOLO_RRHH, headers=e.encabezado_auth(token_viejo))

        self.assertEqual(
            resp_terapeuta.status_code, 403,
            'El token viejo (claim rol=terapeuta) siguio entrando a una ruta de '
            'terapeuta despues de que el usuario paso a ser rrhh en la base: '
            'el rol del CLAIM se esta usando para autorizar en vez del rol de la base.'
        )
        self.assertEqual(
            resp_rrhh.status_code, 200,
            'El mismo token, ahora con el rol real (rrhh) en la base, deberia entrar '
            'a la ruta de rrhh: si no entra, algo distinto del rol de la base se esta '
            'usando para decidir.'
        )

    def test_token_reutilizado_despues_del_logout_sigue_sirviendo_documentado(self):
        """
        NO es un hallazgo nuevo: es la decision 9 de ESTADO.md, confirmada
        aca para dejar constancia de que el comportamiento actual coincide
        con lo documentado. El JWT no tiene estado en el servidor, asi que
        logout no lo revoca: un token copiado antes del logout sigue
        sirviendo hasta que expira. Limitacion conocida y aceptada.
        """
        token = e.token_valido(self.id_usuario, self.rol_original, self.email)

        resp_logout = self.cliente.post('/api/auth/logout', headers=e.encabezado_auth(token))
        self.assertEqual(resp_logout.status_code, 200)

        resp_reuso = self.cliente.get('/api/auth/me', headers=e.encabezado_auth(token))
        self.assertEqual(
            resp_reuso.status_code, 200,
            'El token dejo de servir despues del logout: si esto cambio, hay que '
            'actualizar la decision 9 de ESTADO.md (ya no seria una limitacion conocida).'
        )


if __name__ == '__main__':
    unittest.main()

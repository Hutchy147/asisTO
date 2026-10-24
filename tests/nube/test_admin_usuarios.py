"""
tests/nube/test_admin_usuarios.py — el administrador da de alta cuentas con
correo y clave, las habilita o deshabilita y restablece claves. Control
positivo junto a cada rechazo. Solo el administrador.
"""
import unittest

from _base import BaseApi, EMAILS

CLAVE = 'Entrada2026x'
NUEVO = 'nueva.persona@asisto.local'


class AdminUsuarios(BaseApi):
    def setUp(self):
        self._limpiar()

    def tearDown(self):
        self._limpiar()

    def _limpiar(self):
        for tabla in ('terapeutas', 'rrhh', 'familiares'):
            self.sql(f"DELETE FROM {tabla} WHERE id_usuario IN (SELECT id FROM usuarios WHERE email LIKE 'nueva.%@asisto.local')")
        self.sql("DELETE FROM auditoria_accesos WHERE email LIKE 'nueva.%@asisto.local'")
        self.sql("DELETE FROM usuarios WHERE email LIKE 'nueva.%@asisto.local'")

    def _alta(self, **extra):
        cuerpo = {'rol': 'terapeuta', 'nombre': 'Nora', 'apellido': 'Pérez', 'email': NUEVO,
                  'contrasena': CLAVE, 'matricula': 'MP-9001'}
        cuerpo.update(extra)
        return self.llamar('admin', 'post', '/api/admin/usuarios', json=cuerpo)

    def _login(self, email, clave=CLAVE):
        return self.client.post('/api/auth/login', json={'email': email, 'contrasena': clave})

    def test_solo_el_administrador(self):
        for quien in ('laura', 'rrhh', 'familiar', 'paciente'):
            self.assertEqual(self.llamar(quien, 'get', '/api/admin/usuarios').status_code, 403, quien)
            self.assertEqual(self._alta_de(quien).status_code, 403, quien)
        self.assertEqual(self.llamar('admin', 'get', '/api/admin/usuarios').status_code, 200)

    def _alta_de(self, quien):
        return self.llamar(quien, 'post', '/api/admin/usuarios', json={'rol': 'admin'})

    def test_el_correo_nuevo_entra_con_la_clave_cargada(self):
        r = self._alta()
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        self.assertNotIn('contrasena_hash', r.get_data(as_text=True))
        r = self._login(NUEVO)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(r.get_json()['usuario']['rol'], 'terapeuta')
        # control: con otra clave no entra
        self.assertEqual(self._login(NUEVO, 'Otraclave99').status_code, 401)

    def test_cada_rol_crea_su_perfil(self):
        casos = (
            ('terapeuta', {'matricula': 'MP-9002'}, 'terapeutas'),
            ('rrhh', {'nro_legajo': 'LEG-9002'}, 'rrhh'),
            ('familiar', {'parentesco': 'Tío'}, 'familiares'),
            ('admin', {}, None),
        )
        for i, (rol, extra, tabla) in enumerate(casos):
            email = f'nueva.{rol}@asisto.local'
            r = self._alta(rol=rol, email=email, **extra)
            self.assertEqual(r.status_code, 201, (rol, r.get_data(as_text=True)))
            if tabla:
                self.assertEqual(self.sql(f"SELECT COUNT(*) FROM {tabla} WHERE id_usuario = (SELECT id FROM usuarios WHERE email = '{email}')")[0][0], 1)

    def test_validaciones(self):
        casos = (
            ({'rol': 'paciente'}, 'rol'),
            ({'rol': 'otro'}, 'rol'),
            ({'email': 'sin-arroba'}, 'email'),
            ({'nombre': ' '}, 'nombre'),
            ({'contrasena': 'corta1'}, 'contrasena'),
            ({'contrasena': 'sololetrasaqui'}, 'contrasena'),
            ({'contrasena': 'password123'}, 'contrasena'),
            ({'matricula': ''}, 'matricula'),
        )
        for extra, campo in casos:
            r = self._alta(**extra)
            self.assertEqual((r.status_code, r.get_json().get('campo')), (400, campo), (extra, r.get_data(as_text=True)))
        self.assertEqual(self.sql("SELECT COUNT(*) FROM usuarios WHERE email LIKE 'nueva.%'")[0][0], 0)
        self.assertEqual(self._alta().status_code, 201)

    def test_correo_y_matricula_repetidos(self):
        self.assertEqual(self._alta().status_code, 201)
        r = self._alta(matricula='MP-9100', email=NUEVO.upper())
        self.assertEqual((r.status_code, r.get_json()['campo']), (409, 'email'))
        r = self._alta(matricula='MP-9001', email='nueva.otra@asisto.local')
        self.assertEqual((r.status_code, r.get_json()['campo']), (409, 'matricula'))
        # control: no quedó una cuenta a medias
        self.assertEqual(self.sql("SELECT COUNT(*) FROM usuarios WHERE email = 'nueva.otra@asisto.local'")[0][0], 0)

    def test_deshabilitar_corta_la_sesion_y_habilitar_la_devuelve(self):
        id_nuevo = self._alta().get_json()['usuario']['id']
        token = self._login(NUEVO).get_json()['token']
        cab = {'Authorization': f'Bearer {token}'}
        self.assertEqual(self.client.get('/api/auth/me', headers=cab).status_code, 200)
        r = self.llamar('admin', 'put', f'/api/admin/usuarios/{id_nuevo}/estado', json={'activo': False})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(self.client.get('/api/auth/me', headers=cab).status_code, 401)
        self.assertEqual(self._login(NUEVO).status_code, 401)
        r = self.llamar('admin', 'put', f'/api/admin/usuarios/{id_nuevo}/estado', json={'activo': True})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self._login(NUEVO).status_code, 200)

    def test_no_se_puede_dejar_sin_administrador_ni_deshabilitarse(self):
        yo = self.sql(f"SELECT id FROM usuarios WHERE email = '{EMAILS['admin']}'")[0][0]
        r = self.llamar('admin', 'put', f'/api/admin/usuarios/{yo}/estado', json={'activo': False})
        self.assertEqual(r.status_code, 409, r.get_data(as_text=True))
        self.assertEqual(self.sql(f'SELECT activo FROM usuarios WHERE id = {yo}')[0][0], 1)
        self.assertEqual(self.llamar('admin', 'put', f'/api/admin/usuarios/{yo}/estado', json={'activo': 'no'}).status_code, 400)
        self.assertEqual(self.llamar('admin', 'put', '/api/admin/usuarios/999999/estado', json={'activo': False}).status_code, 404)

    def test_restablecer_la_clave_desbloquea_y_corta_sesiones(self):
        id_nuevo = self._alta().get_json()['usuario']['id']
        token = self._login(NUEVO).get_json()['token']
        for _ in range(5):
            self._login(NUEVO, 'Equivocada99')
        self.assertEqual(self._login(NUEVO).status_code, 429)
        r = self.llamar('admin', 'put', f'/api/admin/usuarios/{id_nuevo}/contrasena', json={'contrasena': 'Segunda2026y'})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(self.client.get('/api/auth/me', headers={'Authorization': f'Bearer {token}'}).status_code, 401)
        self.assertEqual(self._login(NUEVO, CLAVE).status_code, 401)
        self.assertEqual(self._login(NUEVO, 'Segunda2026y').status_code, 200)
        self.assertEqual(self.llamar('admin', 'put', f'/api/admin/usuarios/{id_nuevo}/contrasena', json={'contrasena': 'corta'}).status_code, 400)

    def test_listado_filtros_y_clave_sugerida(self):
        self._alta()
        r = self.llamar('admin', 'get', '/api/admin/usuarios?busqueda=nueva.persona')
        lista = r.get_json()['usuarios']
        self.assertEqual([u['email'] for u in lista], [NUEVO])
        self.assertEqual(lista[0]['perfil'], 'Matrícula MP-9001')
        self.assertNotIn('contrasena_hash', r.get_data(as_text=True))
        self.assertTrue(all(u['rol'] == 'rrhh' for u in self.llamar('admin', 'get', '/api/admin/usuarios?rol=rrhh').get_json()['usuarios']))
        self.assertEqual(self.llamar('admin', 'get', '/api/admin/usuarios?rol=zzz').status_code, 400)
        self.assertEqual(self.llamar('admin', 'get', '/api/admin/usuarios?busqueda=%25').get_json()['total'], 0)
        clave = self.llamar('admin', 'get', '/api/admin/usuarios/contrasena-sugerida').get_json()['contrasena']
        self.assertEqual(self.llamar('admin', 'post', '/api/admin/usuarios', json={
            'rol': 'admin', 'nombre': 'Ana', 'apellido': 'Gil', 'email': 'nueva.sug@asisto.local', 'contrasena': clave}).status_code, 201)


if __name__ == '__main__':
    unittest.main()

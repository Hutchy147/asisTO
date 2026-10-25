"""
tests/nube/test_familiares_api.py — vinculo familiar-paciente (Entrega 4).

seed.sql: familiar 1 (Marta) -> paciente 1, familiar 2 (Jorge) -> paciente 2.
Paciente 1 -> Laura, 2 -> Diego, 3 -> Laura, 4 dado de baja.
"""
import unittest

from _base import BaseApi


class FamiliaresApi(BaseApi):
    def test_listado_y_permisos(self):
        r = self.llamar('laura', 'get', '/api/pacientes/1/familiares')
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertEqual(d['total'], 1)
        self.assertEqual(d['familiares'][0]['nombre_completo'], 'Marta Ledesma')
        self.assertEqual(self.llamar('admin', 'get', '/api/pacientes/1/familiares').status_code, 200)
        # terapeuta sin asignacion vigente sobre el paciente: no gestiona su familia
        self.assertEqual(self.llamar('diego', 'get', '/api/pacientes/1/familiares').status_code, 403)
        for quien in ('rrhh', 'familiar', 'paciente'):
            self.assertEqual(self.llamar(quien, 'get', '/api/pacientes/1/familiares').status_code, 403, quien)
        self.assertEqual(self.llamar(None, 'get', '/api/pacientes/1/familiares').status_code, 401)
        self.assertEqual(self.llamar('admin', 'get', '/api/pacientes/999/familiares').status_code, 404)

    def test_vincular_existente_y_rechazos(self):
        # candidatos para el paciente 3: Marta y Jorge (ninguno vinculado)
        r = self.llamar('admin', 'get', '/api/pacientes/3/familiares/candidatos')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.get_json()['familiares']), 2)
        r = self.llamar('admin', 'get', '/api/pacientes/3/familiares/candidatos?q=Ledesma')
        self.assertEqual([f['id'] for f in r.get_json()['familiares']], [1])
        # control positivo
        r = self.llamar('admin', 'post', '/api/pacientes/3/familiares', json={'id_familiar': 1})
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        self.assertNotIn('contrasena_temporal', r.get_json())
        # ya no es candidato, y repetir da 409
        r = self.llamar('admin', 'get', '/api/pacientes/3/familiares/candidatos')
        self.assertEqual([f['id'] for f in r.get_json()['familiares']], [2])
        r = self.llamar('admin', 'post', '/api/pacientes/3/familiares', json={'id_familiar': 1})
        self.assertEqual(r.status_code, 409)
        # familiar inexistente, paciente de baja
        r = self.llamar('admin', 'post', '/api/pacientes/3/familiares', json={'id_familiar': 99})
        self.assertEqual(r.status_code, 404)
        r = self.llamar('admin', 'post', '/api/pacientes/4/familiares', json={'id_familiar': 1})
        self.assertEqual(r.status_code, 400)
        # sin asignacion o sin rol: 403
        r = self.llamar('diego', 'post', '/api/pacientes/3/familiares', json={'id_familiar': 2})
        self.assertEqual(r.status_code, 403)
        r = self.llamar('familiar', 'post', '/api/pacientes/3/familiares', json={'id_familiar': 2})
        self.assertEqual(r.status_code, 403)
        # limpieza: las pruebas comparten base, y otros modulos cuentan con que
        # Marta (familiar 1) solo tiene vinculado al paciente 1
        r = self.llamar('admin', 'post', '/api/pacientes/3/familiares/1/desvinculacion')
        self.assertEqual(r.status_code, 200)

    def test_terapeuta_no_gestiona_la_familia(self):
        # Vincular, buscar candidatos y quitar acceso es solo del administrador;
        # la terapeuta asignada puede consultar el listado y nada mas.
        antes = self.sql("SELECT COUNT(*) FROM familiares_pacientes")[0][0]
        self.assertEqual(self.llamar('laura', 'get', '/api/pacientes/1/familiares').status_code, 200)
        self.assertEqual(self.llamar('laura', 'get', '/api/pacientes/3/familiares/candidatos').status_code, 403)
        self.assertEqual(self.llamar('laura', 'post', '/api/pacientes/3/familiares', json={'id_familiar': 1}).status_code, 403)
        self.assertEqual(self.llamar('laura', 'post', '/api/pacientes/1/familiares/1/desvinculacion').status_code, 403)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM familiares_pacientes")[0][0], antes)

    def test_crear_y_vincular_con_contrasena_temporal(self):
        datos = {'nombre': 'Rosa', 'apellido': 'Paz', 'email': 'Rosa.Paz@Asisto.local',
                 'parentesco': 'Tia', 'telefono': '3815550000'}
        r = self.llamar('admin', 'post', '/api/pacientes/3/familiares', json=datos)
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        d = r.get_json()
        clave = d['contrasena_temporal']
        self.assertGreaterEqual(len(clave), 10)
        self.assertEqual(d['familiar']['email'], 'rosa.paz@asisto.local')
        # la contrasena temporal sirve para entrar, y la cuenta es de familiar
        r = self.client.post('/api/auth/login',
                             json={'email': 'rosa.paz@asisto.local', 'contrasena': clave})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()['usuario']['rol'], 'familiar')
        # correo repetido -> 409 con campo; el hash nunca se guarda en claro
        r = self.llamar('admin', 'post', '/api/pacientes/3/familiares', json=datos)
        self.assertEqual((r.status_code, r.get_json()['campo']), (409, 'email'))
        filas = self.sql("SELECT contrasena_hash FROM usuarios WHERE email = 'rosa.paz@asisto.local'")
        self.assertNotEqual(filas[0][0], clave)
        # validaciones
        for malo in ({}, {'nombre': 'A', 'apellido': 'B', 'email': 'sin-arroba'},
                     {'nombre': 'A', 'email': 'a@b.com'}):
            r = self.llamar('admin', 'post', '/api/pacientes/3/familiares', json=malo)
            self.assertEqual(r.status_code, 400, malo)
        # paciente de baja: no se crea nada
        r = self.llamar('admin', 'post', '/api/pacientes/4/familiares',
                        json={'nombre': 'X', 'apellido': 'Y', 'email': 'xy@asisto.local'})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM usuarios WHERE email = 'xy@asisto.local'")[0][0], 0)

    def test_desvincular(self):
        # Las pruebas comparten base y se corren en orden alfabetico: este caso
        # arma su propio vinculo (Jorge -> paciente 1) y no toca el de Marta.
        r = self.llamar('admin', 'post', '/api/pacientes/1/familiares', json={'id_familiar': 2})
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        # control positivo
        r = self.llamar('admin', 'post', '/api/pacientes/1/familiares/2/desvinculacion')
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        ids = [f['id'] for f in self.llamar('laura', 'get', '/api/pacientes/1/familiares').get_json()['familiares']]
        self.assertEqual(ids, [1])
        # repetir: 409; la cuenta sigue existiendo (vuelve a ser candidata)
        r = self.llamar('admin', 'post', '/api/pacientes/1/familiares/2/desvinculacion')
        self.assertEqual(r.status_code, 409)
        r = self.llamar('admin', 'get', '/api/pacientes/1/familiares/candidatos')
        self.assertIn(2, [f['id'] for f in r.get_json()['familiares']])
        # sin permiso
        self.assertEqual(self.llamar('diego', 'post', '/api/pacientes/1/familiares/1/desvinculacion').status_code, 403)
        self.assertEqual(self.llamar('familiar', 'post', '/api/pacientes/1/familiares/1/desvinculacion').status_code, 403)

    def test_procedimientos_directos_orden_de_error(self):
        with self.app.app_context():
            from sqlalchemy import text
            from app import db
            db.session.execute(text('CALL p_vincular_familiar(1, 999, @ok, @m)'))
            r = db.session.execute(text('SELECT @ok, @m')).first()
            db.session.commit()
        self.assertEqual((r[0], r[1]), (0, 'El paciente indicado no existe'))


if __name__ == '__main__':
    unittest.main()

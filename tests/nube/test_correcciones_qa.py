"""
tests/nube/test_correcciones_qa.py — regresiones de la ronda de QA de la V6.

Cubre: permisos de escritura del terapeuta no asignado, pacientes pausados,
aviso al cerrar la sesion, asignacion anterior al ingreso, tildes en los
mensajes y desvinculacion de familiares por quien fue responsable.
seed.sql: paciente 1 y 3 -> Laura, 2 -> Diego, 4 de baja.
"""
import unittest

from _base import BaseApi, dia_habil_pasado


class CorreccionesQa(BaseApi):
    # ---- terapeuta que no es el responsable ----
    def test_no_responsable_no_edita_ni_pausa_ni_crea_objetivos(self):
        ficha = {'nombre': 'Tomas', 'apellido': 'Aguirre', 'nro_historia': 'HC-0001',
                 'fecha_nacimiento': '2015-03-12'}
        r = self.llamar('diego', 'put', '/api/pacientes/1', json=ficha)
        self.assertEqual(r.status_code, 403, r.get_data(as_text=True))
        self.assertIn('no está asignado a usted', r.get_json()['mensaje'])
        r = self.llamar('diego', 'post', '/api/pacientes/1/baja', json={'tipo': 'pausa', 'motivo': 'x'})
        self.assertEqual(r.status_code, 403)
        r = self.llamar('diego', 'post', '/api/pacientes/1/baja', json={'tipo': 'alta'})
        self.assertEqual(r.status_code, 403)
        r = self.llamar('diego', 'post', '/api/pacientes/1/reactivacion')
        self.assertEqual(r.status_code, 403)
        r = self.llamar('diego', 'post', '/api/objetivos', json={'id_paciente': 1, 'descripcion': 'Ajeno'})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.sql('SELECT activo FROM pacientes WHERE id=1')[0][0], 1)
        # control positivo: la responsable edita sin problema
        r = self.llamar('laura', 'put', '/api/pacientes/1', json=ficha)
        self.assertIn(r.status_code, (200, 400), r.get_data(as_text=True))
        self.assertNotEqual(r.status_code, 403)

    # ---- paciente pausado: objetivos solo lectura ----
    def test_paciente_pausado_no_edita_objetivos(self):
        obj = self.sql('SELECT id FROM objetivos_terapeuticos WHERE id_paciente=3 AND activo=TRUE ORDER BY id')[0][0]
        r = self.llamar('laura', 'post', '/api/pacientes/3/baja', json={'tipo': 'pausa', 'motivo': 'Viaje'})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        try:
            r = self.llamar('laura', 'put', f'/api/objetivos/{obj}', json={'descripcion': 'Texto nuevo'})
            self.assertEqual(r.status_code, 409, r.get_data(as_text=True))
            self.assertIn('solo para lectura', r.get_json()['mensaje'])
            r = self.llamar('laura', 'delete', f'/api/objetivos/{obj}')
            self.assertEqual(r.status_code, 409)
        finally:
            self.llamar('laura', 'post', '/api/pacientes/3/reactivacion')
        r = self.llamar('laura', 'put', f'/api/objetivos/{obj}', json={'descripcion': 'Texto vigente'})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))

    # ---- aviso al cerrar la sesion ----
    def _avisos(self):
        return self.llamar('familiar', 'get', '/api/familiar/notificaciones').get_json()['total']

    def test_cerrar_sesion_avisa_una_sola_vez(self):
        r = self.llamar('laura', 'post', '/api/sesiones',
                        json={'id_paciente': 1, 'fecha': dia_habil_pasado(47), 'hora_inicio': '08:00',
                              'estado': 'incompleta'})
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        id_s = r.get_json()['sesion']['id']
        base = self._avisos()
        edicion = {'fecha': dia_habil_pasado(47), 'hora_inicio': '08:00'}
        r = self.llamar('laura', 'put', f'/api/sesiones/{id_s}', json={**edicion, 'estado': 'completa'})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(self._avisos(), base + 1)
        # reabrir y volver a cerrar no repite el aviso
        self.llamar('laura', 'put', f'/api/sesiones/{id_s}', json={**edicion, 'estado': 'incompleta'})
        self.llamar('laura', 'put', f'/api/sesiones/{id_s}', json={**edicion, 'estado': 'completa'})
        self.assertEqual(self._avisos(), base + 1)

    # ---- asignacion anterior al ingreso ----
    def test_asignacion_no_puede_empezar_antes_del_ingreso(self):
        self.sql("INSERT INTO pacientes (nombre, apellido, fecha_nacimiento, nro_historia, activo, fecha_alta) "
                 "VALUES ('Prueba','Ingreso','2016-01-01','HC-QA01',TRUE,CURDATE())")
        pid = self.sql("SELECT id FROM pacientes WHERE nro_historia='HC-QA01'")[0][0]
        try:
            r = self.llamar('admin', 'post', f'/api/pacientes/{pid}/asignaciones',
                            json={'id_terapeuta': 1, 'fecha_desde': dia_habil_pasado(20)})
            self.assertEqual(r.status_code, 400, r.get_data(as_text=True))
            self.assertIn('antes del ingreso', r.get_json()['mensaje'])
            r = self.llamar('admin', 'post', f'/api/pacientes/{pid}/asignaciones', json={'id_terapeuta': 1})
            self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        finally:
            self.sql('DELETE FROM asignaciones WHERE id_paciente=:p', p=pid)
            self.sql('DELETE FROM pacientes WHERE id=:p', p=pid)

    # ---- tildes ----
    def test_mensajes_con_tildes(self):
        r = self.llamar(None, 'post', '/api/auth/login',
                        json={'email': 'tildes.qa@asisto.local', 'contrasena': 'mala'})
        self.assertEqual(r.get_json()['mensaje'], 'Email o contraseña incorrectos.')
        self.sql("DELETE FROM auditoria_accesos WHERE id_usuario IS NULL")
        r = self.llamar('rrhh', 'get', '/api/pacientes/1/familiares')
        self.assertEqual(r.status_code, 403)

    # ---- familiares: quien fue responsable puede quitar acceso tras el alta ----
    def test_ex_responsable_quita_acceso_en_paciente_de_baja(self):
        ex = self.sql('SELECT t.id FROM asignaciones a JOIN terapeutas t ON t.id=a.id_terapeuta '
                      'WHERE a.id_paciente=4 LIMIT 1')
        if not ex:
            self.skipTest('el paciente 4 no tiene historial de asignacion en el seed')
        quien = 'laura' if ex[0][0] == 1 else 'diego'
        otro = 'diego' if quien == 'laura' else 'laura'
        r = self.llamar(quien, 'get', '/api/pacientes/4/familiares')
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(self.llamar(otro, 'get', '/api/pacientes/4/familiares').status_code, 403)
        # vincular sigue vedado en un paciente de baja
        r = self.llamar(quien, 'post', '/api/pacientes/4/familiares', json={'id_familiar': 1})
        self.assertIn(r.status_code, (400, 403))

    def test_candidatos_trata_los_comodines_como_texto(self):
        r = self.llamar('admin', 'get', '/api/pacientes/3/familiares/candidatos?q=%25')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()['familiares'], [])


    # ---- cuerpos mal formados: 400, nunca 500 ----
    def test_cuerpos_mal_formados_dan_400(self):
        for cuerpo in ([], 'texto', 5, [{'a': 1}]):
            for quien, ruta in (('laura', '/api/objetivos'), ('laura', '/api/sesiones'),
                                ('laura', '/api/pacientes/1/informes'), ('admin', '/api/pacientes/3/asignaciones'),
                                (None, '/api/auth/recuperar')):
                r = self.llamar(quien, 'post', ruta, json=cuerpo)
                self.assertEqual(r.status_code, 400, (ruta, cuerpo, r.get_data(as_text=True)))
        for valor in (123, [], {'a': 1}, True):
            r = self.llamar('laura', 'post', '/api/objetivos', json={'id_paciente': 1, 'descripcion': valor})
            self.assertEqual(r.status_code, 400, (valor, r.get_data(as_text=True)))
            r = self.llamar('laura', 'post', '/api/pacientes/1/informes', json={'tipo': valor, 'periodo': valor})
            self.assertEqual(r.status_code, 400, (valor, r.get_data(as_text=True)))
        r = self.llamar(None, 'post', '/api/auth/recuperar', json={'email': ['a@b.c']})
        self.assertEqual(r.status_code, 400)


if __name__ == '__main__':
    unittest.main()

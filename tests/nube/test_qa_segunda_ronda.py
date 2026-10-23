"""
tests/nube/test_qa_segunda_ronda.py — correcciones de la segunda ronda del QA
de la V6 (Leandro H*, Tomás T*, Franco F*). Control positivo junto a cada
rechazo. seed.sql: paciente 1 -> Laura (familiar Marta), 4 de baja.
"""
import datetime as dt
import unittest

from _base import BaseApi, hoy


class RangosDeHistorial(BaseApi):
    def test_solo_desde_llega_hasta_hoy(self):
        # H21: con solo "desde", hasta hoy (antes eran 7 dias)
        desde = (hoy() - dt.timedelta(days=40)).isoformat()
        r = self.llamar('laura', 'get', f'/api/sesiones/registradas?desde={desde}')
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual((r.get_json()['desde'], r.get_json()['hasta']), (desde, hoy().isoformat()))
        r = self.llamar('familiar', 'get', f'/api/familiar/pacientes/1/evolucion?desde={desde}')
        self.assertEqual(r.get_json()['periodo']['hasta'], hoy().isoformat())

    def test_solo_hasta_arranca_en_el_ingreso(self):
        hasta = (hoy() - dt.timedelta(days=2)).isoformat()
        r = self.llamar('familiar', 'get', f'/api/familiar/pacientes/1/evolucion?hasta={hasta}')
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        alta = self.sql('SELECT fecha_alta FROM pacientes WHERE id = 1')[0][0].isoformat()
        self.assertEqual(r.get_json()['periodo']['desde'], max(alta, (hoy() - dt.timedelta(days=367)).isoformat()))

    def test_periodo_futuro_es_400_y_hasta_futuro_se_recorta(self):
        # H22: antes devolvia un periodo invertido ("del 01/12 al 22/10")
        futuro = (hoy() + dt.timedelta(days=30)).isoformat()
        for quien, ruta in (('familiar', '/api/familiar/pacientes/1/evolucion'),
                            ('laura', '/api/sesiones/registradas'),
                            ('paciente', '/api/paciente/mi-progreso')):
            r = self.llamar(quien, 'get', f'{ruta}?desde={futuro}&hasta={futuro}')
            self.assertEqual(r.status_code, 400, ruta)
            self.assertEqual(r.get_json()['campo'], 'desde')
        r = self.llamar('laura', 'get', f'/api/sesiones/registradas?hasta={futuro}')
        self.assertEqual(r.get_json()['hasta'], hoy().isoformat())

    def test_fecha_inexistente_dice_que_no_existe(self):
        # H34: el formato es correcto, el dia no existe
        r = self.llamar('familiar', 'get', '/api/familiar/pacientes/1/evolucion?desde=2026-02-30')
        self.assertEqual(r.status_code, 400)
        self.assertIn('no existe en el calendario', r.get_json()['mensaje'])
        r = self.llamar('familiar', 'get', '/api/familiar/pacientes/1/evolucion?desde=30-02-2026')
        self.assertIn('formato', r.get_json()['mensaje'])


class AvisosDelFamiliar(BaseApi):
    def test_filtros_invalidos_y_paciente_no_vinculado(self):
        # H26
        for consulta, campo in (('leida=2', 'leida'), ('limite=0', 'limite'),
                                ('limite=101', 'limite'), ('desplazamiento=-1', 'desplazamiento')):
            r = self.llamar('familiar', 'get', f'/api/familiar/notificaciones?{consulta}')
            self.assertEqual((r.status_code, r.get_json().get('campo')), (400, campo), consulta)
        self.assertEqual(self.llamar('familiar', 'get', '/api/familiar/notificaciones?id_paciente=2').status_code, 403)
        # control positivo
        self.assertEqual(self.llamar('familiar', 'get', '/api/familiar/notificaciones?leida=0&limite=100&id_paciente=1').status_code, 200)

    def test_avisos_de_un_paciente_desvinculado_dejan_de_verse(self):
        self.sql("INSERT INTO notificaciones (id_familiar, id_paciente, tipo, mensaje) "
                 "VALUES (1, 2, 'nueva_sesion', 'aviso huerfano de prueba')")
        try:
            r = self.llamar('familiar', 'get', '/api/familiar/notificaciones?limite=100')
            self.assertNotIn('aviso huerfano de prueba', [n['mensaje'] for n in r.get_json()['notificaciones']])
            id_aviso = self.sql("SELECT id FROM notificaciones WHERE mensaje = 'aviso huerfano de prueba'")[0][0]
            r = self.llamar('familiar', 'post', f'/api/familiar/notificaciones/{id_aviso}/lectura', json={'leida': True})
            self.assertEqual(r.status_code, 404)
        finally:
            self.sql("DELETE FROM notificaciones WHERE mensaje = 'aviso huerfano de prueba'")


class PacientesYRecuperacion(BaseApi):
    def test_listado_de_inactivos_y_sugerencia_de_historia(self):
        # F5.3 y F4.4
        r = self.llamar('laura', 'get', '/api/pacientes?estado=inactivos')
        self.assertEqual(r.status_code, 200)
        self.assertIn(4, [p['id'] for p in r.get_json()['pacientes']])
        self.assertTrue(all(not p['activo'] for p in r.get_json()['pacientes']))
        activos = self.llamar('laura', 'get', '/api/pacientes').get_json()
        self.assertNotIn(4, [p['id'] for p in activos['pacientes']])
        usados = {f[0] for f in self.sql('SELECT nro_historia FROM pacientes')}
        self.assertNotIn(activos['siguiente_nro_historia'], usados)
        self.assertEqual(self.llamar('laura', 'get', '/api/pacientes?estado=otro').status_code, 400)

    def test_verificar_enlace_y_auditoria_de_recuperacion(self):
        # F1.3: el enlace se verifica al abrir la pantalla
        r = self.client.post('/api/auth/restablecer/verificar', json={'token': 'no-existe'})
        self.assertEqual(r.get_json(), {'vigente': False})
        r = self.client.post('/api/auth/recuperar', json={'email': 'diego.moyano@asisto.local'})
        token = r.get_json().get('token_desarrollo')
        if token is None:
            self.skipTest('RECUPERACION_MOSTRAR_TOKEN apagado en este entorno')
        self.assertEqual(self.client.post('/api/auth/restablecer/verificar', json={'token': token}).get_json(), {'vigente': True})
        # auditoria: el pedido queda registrado
        self.assertGreaterEqual(self.sql(
            "SELECT COUNT(*) FROM auditoria_accesos WHERE email = 'diego.moyano@asisto.local' AND resultado = 'recuperacion'"
        )[0][0], 1)


class ControlDeInformes(BaseApi):
    def test_el_semestral_no_corresponde_fuera_de_junio_y_diciembre(self):
        # T7.2: un S1 publicado no figura en mayo
        r = self.llamar('laura', 'get', '/api/informes/control?mes=2026-05')
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertTrue(all(f['semestral']['estado'] == 'no_corresponde' for f in r.get_json()['pacientes']))


if __name__ == '__main__':
    unittest.main()

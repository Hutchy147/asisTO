"""
tests/nube/test_notificaciones_api.py — avisos del tratamiento (Entrega 4).

seed.sql: familiar 1 (Marta) -> paciente 1; familiar 2 (Jorge) -> paciente 2.
Paciente 1 -> Laura, 2 -> Diego. Cada prueba cuenta avisos nuevos en lugar de
asumir un total, porque las pruebas comparten base.
"""
import datetime as dt
import unittest

from _base import BaseApi, dia_habil_pasado, dias


def lunes_futuro(desde=20):
    d = dt.date.today() + dt.timedelta(days=desde)
    while d.weekday() != 0:
        d += dt.timedelta(days=1)
    return d.isoformat()


class NotificacionesApi(BaseApi):
    def _lista(self, quien='familiar', consulta=''):
        r = self.llamar(quien, 'get', '/api/familiar/notificaciones' + consulta)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        return r.get_json()

    def _total(self, quien='familiar'):
        return self._lista(quien)['total']

    def _preferencia(self, quien, tipo, valor):
        r = self.llamar(quien, 'put', f'/api/familiar/notificaciones/preferencias/{tipo}', json={'habilitada': valor})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))

    def test_solo_familiar(self):
        for quien in ('laura', 'rrhh', 'admin', 'paciente'):
            self.assertEqual(self.llamar(quien, 'get', '/api/familiar/notificaciones').status_code, 403, quien)
        self.assertEqual(self.llamar(None, 'get', '/api/familiar/notificaciones').status_code, 401)

    def test_sesion_realizada_avisa_y_la_agendada_no(self):
        antes = self._total()
        # sesion futura (agenda): no avisa
        r = self.llamar('laura', 'post', '/api/sesiones',
                        json={'id_paciente': 1, 'fecha': lunes_futuro(), 'hora_inicio': '15:00', 'estado': 'incompleta'})
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        self.assertEqual(self._total(), antes)
        # control positivo: sesion ya ocurrida -> un aviso de nueva_sesion
        r = self.llamar('laura', 'post', '/api/sesiones',
                        json={'id_paciente': 1, 'fecha': dia_habil_pasado(3), 'hora_inicio': '16:00', 'estado': 'completa'})
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        d = self._lista()
        self.assertEqual(d['total'], antes + 1)
        n = d['notificaciones'][0]
        self.assertEqual(n['tipo'], 'nueva_sesion')
        self.assertIn('Se registró la sesión del', n['mensaje'])
        self.assertFalse(n['leida'])
        # el aviso es del paciente vinculado: filtrar por uno no vinculado es 403 (H26)
        self.assertEqual(self.llamar('familiar', 'get', '/api/familiar/notificaciones?id_paciente=2').status_code, 403)
        self.assertNotIn(1, {x['id_paciente'] for x in self._lista('jorge')['notificaciones']})

    def test_ausencia_no_dice_quien_falto(self):
        r = self.llamar('laura', 'post', '/api/sesiones',
                        json={'id_paciente': 1, 'fecha': dia_habil_pasado(4), 'hora_inicio': '17:00',
                              'estado': 'ausencia', 'ausencia_de': 'paciente'})
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        n = self._lista()['notificaciones'][0]
        self.assertIn('ausencia', n['mensaje'])
        self.assertNotIn('paciente', n['mensaje'].split('de ')[0].lower().replace('sesión', ''))

    def test_cambios_de_objetivo_avisan(self):
        antes = self._total()
        # paciente 3 no tiene familiares vinculados: no genera avisos a Marta
        self.llamar('laura', 'delete', '/api/objetivos/%d' % self.llamar(
            'laura', 'get', '/api/objetivos/paciente/3').get_json()['activos'][0]['id'])
        r = self.llamar('laura', 'post', '/api/objetivos', json={'id_paciente': 3, 'descripcion': 'Objetivo sin familia vinculada'})
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        self.assertEqual(self._total(), antes)
        # paciente 1 (Marta): editar avisa 'cambio_objetivo'
        activos = self.llamar('laura', 'get', '/api/objetivos/paciente/1').get_json()['activos']
        id_obj = activos[0]['id']
        texto = 'Descripcion editada para probar el aviso ' + dias(0)
        r = self.llamar('laura', 'put', f'/api/objetivos/{id_obj}', json={'descripcion': texto})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        n = self._lista()['notificaciones'][0]
        self.assertEqual(n['tipo'], 'cambio_objetivo')
        self.assertIn('Se modificó un objetivo', n['mensaje'])
        # una edicion sin cambios no avisa
        total = self._total()
        self.llamar('laura', 'put', f'/api/objetivos/{id_obj}', json={'descripcion': texto})
        self.assertEqual(self._total(), total)
        # archivar y crear avisan. El cupo es de 3 a 4 activos: si hay 4 se
        # archiva primero, si hay 3 se crea primero.
        def crear():
            r = self.llamar('laura', 'post', '/api/objetivos', json={'id_paciente': 1, 'descripcion': 'Objetivo nuevo con aviso ' + dias(0)})
            self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
            self.assertIn('Se agregó un objetivo', self._lista()['notificaciones'][0]['mensaje'])

        def archivar():
            r = self.llamar('laura', 'delete', f'/api/objetivos/{id_obj}')
            self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
            self.assertIn('Se archivó un objetivo', self._lista()['notificaciones'][0]['mensaje'])

        if len(activos) >= 4:
            archivar(); crear()
        else:
            crear(); archivar()
        self.assertEqual(self._total(), total + 2)

    def test_preferencias_apagan_el_tipo(self):
        prefs = self.llamar('familiar', 'get', '/api/familiar/notificaciones/preferencias').get_json()['preferencias']
        self.assertEqual([p['tipo'] for p in prefs], ['nueva_sesion', 'informe_generado', 'cambio_objetivo'])
        try:
            self._preferencia('familiar', 'nueva_sesion', False)
            antes = self._total()
            r = self.llamar('laura', 'post', '/api/sesiones',
                            json={'id_paciente': 1, 'fecha': dia_habil_pasado(5), 'hora_inicio': '18:00', 'estado': 'completa'})
            self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
            self.assertEqual(self._total(), antes)          # apagado: no llega
        finally:
            self._preferencia('familiar', 'nueva_sesion', True)
        # control positivo: encendido otra vez, vuelve a llegar
        antes = self._total()
        r = self.llamar('laura', 'post', '/api/sesiones',
                        json={'id_paciente': 1, 'fecha': dia_habil_pasado(6), 'hora_inicio': '19:00', 'estado': 'completa'})
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        self.assertEqual(self._total(), antes + 1)
        # validaciones
        self.assertEqual(self.llamar('familiar', 'put', '/api/familiar/notificaciones/preferencias/otro', json={'habilitada': True}).status_code, 404)
        self.assertEqual(self.llamar('familiar', 'put', '/api/familiar/notificaciones/preferencias/nueva_sesion', json={'habilitada': 'si'}).status_code, 400)

    def test_leer_y_filtrar(self):
        d = self._lista()
        self.assertGreater(d['no_leidas'], 0)
        n = next(x for x in d['notificaciones'] if not x['leida'])
        r = self.llamar('familiar', 'post', f"/api/familiar/notificaciones/{n['id']}/lectura", json={'leida': True})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.get_json()['notificacion']['leida'])
        r = self.llamar('familiar', 'post', f"/api/familiar/notificaciones/{n['id']}/lectura", json={'leida': False})
        self.assertFalse(r.get_json()['notificacion']['leida'])
        # filtros
        solo = self._lista('familiar', '?tipo=nueva_sesion')['notificaciones']
        self.assertTrue(solo and all(x['tipo'] == 'nueva_sesion' for x in solo))
        self.assertEqual(self.llamar('familiar', 'get', '/api/familiar/notificaciones?tipo=otro').status_code, 400)
        # el aviso de otro familiar no existe para Marta
        otro = self._lista('familiar')['notificaciones'][0]['id']
        self.assertEqual(self.llamar('familiar', 'post', '/api/familiar/notificaciones/99999/lectura', json={}).status_code, 404)
        # lectura masiva
        r = self.llamar('familiar', 'post', '/api/familiar/notificaciones/lectura-masiva')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.llamar('familiar', 'get', '/api/familiar/notificaciones/no-leidas').get_json()['no_leidas'], 0)

    def test_procedimiento_directo(self):
        from sqlalchemy import text
        from app import db
        with self.app.app_context():
            db.session.execute(text("CALL p_notificar_paciente(1, 'nada', 'x', @e, @m)"))
            malo = db.session.execute(text('SELECT @e, @m')).first()
            db.session.execute(text("CALL p_notificar_paciente(999, 'nueva_sesion', 'x', @e, @m)"))
            inexistente = db.session.execute(text('SELECT @e, @m')).first()
            db.session.commit()
        self.assertEqual(tuple(malo), (0, 'El tipo de aviso indicado no es valido'))
        self.assertEqual(tuple(inexistente), (0, 'El paciente indicado no existe'))


if __name__ == '__main__':
    unittest.main()

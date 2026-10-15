"""
tests/nube/test_agenda_api.py — norma de agenda de la Entrega 3: sesiones de
lunes a viernes y de 45 minutos por defecto. Control positivo junto a cada rechazo.
seed.sql: paciente 1 -> Laura (vigente), 3 -> Laura.
"""
import datetime as dt
import unittest

from _base import BaseApi, hoy


def proximo_dia(weekday, desde_dias=10):
    """Fecha ISO futura (>= desde_dias) que cae en `weekday` (0 = lunes ... 5 = sabado)."""
    d = hoy() + dt.timedelta(days=desde_dias)
    while d.weekday() != weekday:
        d += dt.timedelta(days=1)
    return d.isoformat()


class AgendaApi(BaseApi):
    def _sesion(self, **extra):
        cuerpo = {'id_paciente': 1, 'fecha': proximo_dia(1), 'hora_inicio': '09:00',
                  'estado': 'incompleta'}
        cuerpo.update(extra)
        return self.llamar('laura', 'post', '/api/sesiones', json=cuerpo)

    def test_fin_de_semana_rechazado_y_dia_habil_acepta(self):
        r = self._sesion(fecha=proximo_dia(5))             # sabado
        self.assertEqual((r.status_code, r.get_json()['campo']), (400, 'fecha'), r.get_data(as_text=True))
        self.assertIn('lunes a viernes', r.get_json()['mensaje'])
        r = self._sesion(fecha=proximo_dia(6))             # domingo
        self.assertEqual((r.status_code, r.get_json()['campo']), (400, 'fecha'))
        # control positivo: el mismo cuerpo en un viernes entra
        r = self._sesion(fecha=proximo_dia(4))
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))

    def test_hora_fin_por_defecto_son_45_minutos(self):
        r = self._sesion(fecha=proximo_dia(0), hora_inicio='10:00')
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        self.assertEqual(r.get_json()['sesion']['hora_fin'], '10:45:00')
        # una hora de fin explicita se respeta (hora completa, por ejemplo)
        r = self._sesion(fecha=proximo_dia(0), hora_inicio='15:00', hora_fin='16:00')
        self.assertEqual(r.get_json()['sesion']['hora_fin'], '16:00:00')

    def test_45_minutos_permiten_dos_sesiones_seguidas(self):
        # 10:00-10:45 y 10:45-11:30 no se pisan; con el viejo default de una
        # hora la segunda habria sido rechazada.
        fecha = proximo_dia(2)
        self.assertEqual(self._sesion(fecha=fecha, hora_inicio='10:00').status_code, 201)
        self.assertEqual(self._sesion(fecha=fecha, hora_inicio='10:45', id_paciente=3).status_code, 201)
        # y una que realmente se pisa sigue rechazada
        self.assertEqual(self._sesion(fecha=fecha, hora_inicio='10:30', id_paciente=3).status_code, 400)

    def test_hora_de_inicio_invalida(self):
        r = self._sesion(hora_inicio='no-es-hora')
        self.assertEqual((r.status_code, r.get_json()['campo']), (400, 'hora_inicio'))

    def test_mover_a_fin_de_semana_rechazado_pero_editar_una_vieja_de_sabado_si(self):
        r = self._sesion(fecha=proximo_dia(3), hora_inicio='14:00')
        id_s = r.get_json()['sesion']['id']
        edicion = {'estado': 'incompleta', 'fecha': proximo_dia(5), 'hora_inicio': '14:00'}
        r = self.llamar('laura', 'put', f'/api/sesiones/{id_s}', json=edicion)
        self.assertEqual((r.status_code, r.get_json()['campo']), (400, 'fecha'), r.get_data(as_text=True))
        # control positivo: moverla a otro dia habil funciona
        edicion['fecha'] = proximo_dia(4)
        self.assertEqual(self.llamar('laura', 'put', f'/api/sesiones/{id_s}', json=edicion).status_code, 200)
        # una sesion ya guardada en sabado (viene de antes de la norma) se edita sin moverla
        sabado = proximo_dia(5, 30)
        self.sql("INSERT INTO sesiones (id_terapeuta, id_paciente, fecha, hora_inicio, hora_fin, estado) "
                 "VALUES (1, 3, :f, '09:00:00', '09:45:00', 'incompleta')", f=sabado)
        id_sab = self.sql("SELECT id FROM sesiones WHERE fecha=:f AND id_paciente=3", f=sabado)[0][0]
        r = self.llamar('laura', 'put', f'/api/sesiones/{id_sab}',
                        json={'estado': 'incompleta', 'fecha': sabado, 'hora_inicio': '09:15', 'notas': 'se corrio'})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        # y sigue visible en el listado de la semana
        r = self.llamar('laura', 'get', f'/api/sesiones?desde={sabado}&hasta={sabado}')
        self.assertEqual(r.get_json()['total'], 1)


if __name__ == '__main__':
    unittest.main()

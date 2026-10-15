"""
tests/nube/test_agenda_recurrente_api.py — agenda semanal recurrente (Entrega 3).
seed.sql: paciente 1 y 3 -> Laura (vigente), paciente 2 -> Diego, paciente 4 de baja.
"""
import datetime as dt
import unittest

from _base import BaseApi, hoy


def primera_fecha(weekday):
    """Primera fecha desde hoy (inclusive) que cae en `weekday` (0 = lunes)."""
    d = hoy()
    while d.weekday() != weekday:
        d += dt.timedelta(days=1)
    return d


class AgendaRecurrenteApi(BaseApi):
    def _turno(self, quien='laura', **extra):
        cuerpo = {'id_paciente': 1, 'dia_semana': 1, 'hora_inicio': '07:00'}
        cuerpo.update(extra)
        return self.llamar(quien, 'post', '/api/agenda-recurrente', json=cuerpo)

    def _limpiar(self):
        self.sql('UPDATE agenda_recurrente SET activo = FALSE')

    def setUp(self):
        self._limpiar()

    def test_crear_y_listar_con_45_minutos_por_defecto(self):
        r = self._turno()
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        t = r.get_json()['turno']
        self.assertEqual((t['dia'], t['hora_inicio'], t['hora_fin']), ('Lunes', '07:00:00', '07:45:00'))
        lista = self.llamar('laura', 'get', '/api/agenda-recurrente').get_json()
        self.assertEqual(lista['total'], 1)
        # cada terapeuta ve solo la suya
        self.assertEqual(self.llamar('diego', 'get', '/api/agenda-recurrente').get_json()['total'], 0)

    def test_validaciones_con_control_positivo(self):
        for cuerpo, campo in (
            ({'dia_semana': 6}, 'dia_semana'),                       # sabado
            ({'dia_semana': 0}, 'dia_semana'),
            ({'hora_inicio': 'x'}, 'hora_inicio'),
            ({'hora_inicio': '09:00', 'hora_fin': '09:00'}, 'hora_fin'),
            ({'id_paciente': 2}, 'id_paciente'),                     # asignado a Diego
            ({'id_paciente': 4}, 'id_paciente'),                     # de baja
            ({'id_paciente': 999}, 'id_paciente'),
        ):
            r = self._turno(**cuerpo)
            self.assertEqual((r.status_code in (400, 404), r.get_json().get('campo')), (True, campo), (cuerpo, r.get_data(as_text=True)))
        self.assertEqual(self._turno().status_code, 201)             # el mismo pedido valido entra

    def test_solape_entre_turnos_de_la_misma_terapeuta(self):
        self.assertEqual(self._turno(hora_inicio='09:00').status_code, 201)
        r = self._turno(id_paciente=3, hora_inicio='09:30')
        self.assertEqual((r.status_code, r.get_json()['campo']), (400, 'hora_inicio'))
        self.assertEqual(self._turno(id_paciente=3, hora_inicio='09:45').status_code, 201)  # pegado, no pisa
        self.assertEqual(self._turno(id_paciente=3, hora_inicio='09:30', dia_semana=2).status_code, 201)  # otro dia

    def test_generar_crea_sesiones_habiles_y_es_idempotente(self):
        self._turno(dia_semana=1, hora_inicio='06:00')
        self._turno(id_paciente=3, dia_semana=5, hora_inicio='06:00')
        r = self.llamar('laura', 'post', '/api/agenda-recurrente/generar', json={'semanas': 2})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        g = r.get_json()
        self.assertEqual((g['creadas'], g['existentes'], g['omitidas']), (4, 0, []))   # 2 lunes + 2 viernes
        filas = self.sql("""SELECT fecha, estado, hora_fin FROM sesiones
                            WHERE hora_inicio = '06:00:00' AND fecha >= :d ORDER BY fecha""", d=hoy().isoformat())
        self.assertEqual(len(filas), 4)
        self.assertTrue(all(f[0].weekday() in (0, 4) and f[1] == 'incompleta' for f in filas))
        self.assertTrue(all(str(f[2]) == '6:45:00' for f in filas))
        # segunda vez: no duplica
        g2 = self.llamar('laura', 'post', '/api/agenda-recurrente/generar', json={'semanas': 2}).get_json()
        self.assertEqual((g2['creadas'], g2['existentes']), (0, 4))

    def test_generar_informa_lo_que_no_pudo_agendar(self):
        self._turno(dia_semana=3, hora_inicio='05:00')          # miercoles
        miercoles = primera_fecha(2)
        # Laura ya tiene al paciente 3 a esa hora ese dia: la primera ocurrencia se pisa
        r = self.llamar('laura', 'post', '/api/sesiones', json={
            'id_paciente': 3, 'fecha': miercoles.isoformat(), 'hora_inicio': '05:00', 'estado': 'incompleta'})
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        g = self.llamar('laura', 'post', '/api/agenda-recurrente/generar', json={'semanas': 2}).get_json()
        self.assertEqual((g['creadas'], len(g['omitidas'])), (1, 1), g)
        self.assertEqual(g['omitidas'][0]['fecha'], miercoles.isoformat())
        self.assertIn('superpon', g['omitidas'][0]['motivo'].lower())

    def test_generar_validaciones(self):
        r = self.llamar('laura', 'post', '/api/agenda-recurrente/generar', json={})
        self.assertEqual(r.status_code, 409)                    # sin turnos cargados
        self._turno()
        for semanas in (0, 9, 'x', True):
            r = self.llamar('laura', 'post', '/api/agenda-recurrente/generar', json={'semanas': semanas})
            self.assertEqual((r.status_code, r.get_json()['campo']), (400, 'semanas'), semanas)
        self.assertEqual(self.llamar('laura', 'post', '/api/agenda-recurrente/generar', json={}).status_code, 200)

    def test_quitar_desactiva_y_no_borra_sesiones(self):
        id_t = self._turno(hora_inicio='04:00').get_json()['turno']['id']
        self.llamar('laura', 'post', '/api/agenda-recurrente/generar', json={'semanas': 1})
        antes = self.sql("SELECT COUNT(*) FROM sesiones WHERE hora_inicio='04:00:00'")[0][0]
        self.assertEqual(self.llamar('diego', 'delete', f'/api/agenda-recurrente/{id_t}').status_code, 403)
        self.assertEqual(self.llamar('laura', 'delete', f'/api/agenda-recurrente/{id_t}').status_code, 200)
        self.assertEqual(self.llamar('laura', 'delete', f'/api/agenda-recurrente/{id_t}').status_code, 404)
        self.assertEqual(self.llamar('laura', 'get', '/api/agenda-recurrente').get_json()['total'], 0)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM sesiones WHERE hora_inicio='04:00:00'")[0][0], antes)

    def test_solo_terapeutas(self):
        for quien in ('rrhh', 'familiar', 'paciente'):
            self.assertEqual(self.llamar(quien, 'get', '/api/agenda-recurrente').status_code, 403, quien)
        self.assertEqual(self.llamar(None, 'get', '/api/agenda-recurrente').status_code, 401)


if __name__ == '__main__':
    unittest.main()

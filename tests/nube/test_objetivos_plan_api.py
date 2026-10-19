"""
tests/nube/test_objetivos_plan_api.py — objetivos a trabajar en la sesion
(Entrega 3): el plan se arma eligiendo objetivos del paciente.
seed.sql: pacientes 1 y 3 -> Laura; 2 -> Diego; objetivos de cada paciente propios.
"""
import unittest

from _base import BaseApi, dia_habil_pasado
from test_agenda_api import proximo_dia


class ObjetivosPlanApi(BaseApi):
    HORAS = __import__('itertools').cycle(f'{h:02d}:00' for h in range(0, 7))

    def tearDown(self):
        self.sql("DELETE FROM sesiones WHERE hora_inicio < '07:00:00' AND estado='incompleta'")

    def _sesion(self, paciente=1, fecha=None, hora=None, quien='laura'):
        hora = hora or next(self.HORAS)
        r = self.llamar(quien, 'post', '/api/sesiones', json={
            'id_paciente': paciente, 'fecha': fecha or proximo_dia(2, 25),
            'hora_inicio': hora, 'estado': 'incompleta'})
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        return r.get_json()['sesion']['id']

    def _objetivos(self, paciente):
        return [o[0] for o in self.sql(
            'SELECT id FROM objetivos_terapeuticos WHERE id_paciente=:p AND activo=TRUE ORDER BY id', p=paciente)]

    def _marcar(self, sesion, objetivo, marcado=None, quien='laura'):
        cuerpo = {'id_objetivo': objetivo}
        if marcado is not None:
            cuerpo['marcado'] = marcado
        return self.llamar(quien, 'post', f'/api/sesiones/{sesion}/objetivos', json=cuerpo)

    def _plan(self, sesion):
        return self.llamar('laura', 'get', f'/api/sesiones/{sesion}/renglones').get_json()['objetivos_plan']

    def test_marcar_y_desmarcar_es_idempotente(self):
        s = self._sesion()
        o1, o2 = self._objetivos(1)[:2]
        self.assertEqual(self._plan(s), [])
        self.assertEqual(self._marcar(s, o1).status_code, 200)
        self.assertEqual(self._marcar(s, o1).status_code, 200)       # repetir no duplica
        self.assertEqual(self._marcar(s, o2).status_code, 200)
        self.assertEqual(self._plan(s), sorted([o1, o2]))
        self.assertEqual(self._marcar(s, o1, False).status_code, 200)
        self.assertEqual(self._marcar(s, o1, False).status_code, 200)  # desmarcar lo no marcado
        self.assertEqual(self._plan(s), [o2])

    def test_rechazos_con_control_positivo(self):
        s = self._sesion()
        ajeno = self._objetivos(3)[0]
        r = self._marcar(s, ajeno)
        self.assertEqual((r.status_code, r.get_json()['campo']), (400, 'id_objetivo'))  # de otro paciente
        self.assertEqual(self._marcar(s, 999999).status_code, 404)                       # no existe
        self.assertEqual(self._marcar(s, self._objetivos(1)[0], quien='diego').status_code, 403)  # sesion ajena
        r = self.llamar('laura', 'post', f'/api/sesiones/{s}/objetivos', json={})
        self.assertEqual((r.status_code, r.get_json()['campo']), (400, 'id_objetivo'))
        r = self.llamar('laura', 'post', f'/api/sesiones/{s}/objetivos', json={'id_objetivo': 1, 'marcado': 'si'})
        self.assertEqual((r.status_code, r.get_json()['campo']), (400, 'marcado'))
        self.assertEqual(self.llamar('laura', 'post', '/api/sesiones/999999/objetivos', json={'id_objetivo': 1}).status_code, 404)
        self.assertEqual(self._marcar(s, self._objetivos(1)[0]).status_code, 200)        # el pedido valido entra
        self.assertEqual(self.llamar(None, 'post', f'/api/sesiones/{s}/objetivos', json={'id_objetivo': 1}).status_code, 401)

    def test_no_se_planea_un_objetivo_archivado_pero_el_plan_conserva_la_historia(self):
        s = self._sesion()
        ids = self._objetivos(1)
        extra = self.llamar('laura', 'post', '/api/objetivos',
                            json={'id_paciente': 1, 'descripcion': 'Objetivo temporal del plan'})
        if extra.status_code == 201:
            ids.append(extra.get_json()['objetivo']['id'])
        viejo = ids[-1]
        self.assertEqual(self._marcar(s, viejo).status_code, 200)
        try:
            self.sql('UPDATE objetivos_terapeuticos SET activo=FALSE, fecha_archivado=NOW() WHERE id=:i', i=viejo)
            self.assertIn(viejo, self._plan(s))                       # queda la historia
            r = self._marcar(self._sesion(), viejo)
            self.assertEqual(r.status_code, 400)                      # pero no se puede planear de nuevo
            self.assertIn('archivado', r.get_json()['mensaje'])
            self.assertEqual(self._marcar(s, viejo, False).status_code, 200)  # y se puede sacar
        finally:
            self.sql('UPDATE objetivos_terapeuticos SET activo=TRUE, fecha_archivado=NULL WHERE id=:i', i=viejo)

    def test_borrar_la_sesion_borra_su_plan_pero_no_el_objetivo(self):
        s = self._sesion()
        o = self._objetivos(1)[0]
        self._marcar(s, o)
        self.sql('DELETE FROM sesiones WHERE id=:i', i=s)
        self.assertEqual(self.sql('SELECT COUNT(*) FROM sesion_objetivos WHERE id_sesion=:i', i=s)[0][0], 0)
        self.assertEqual(self.sql('SELECT COUNT(*) FROM objetivos_terapeuticos WHERE id=:i', i=o)[0][0], 1)

    def test_el_plan_tambien_se_arma_en_una_sesion_pasada(self):
        s = self._sesion(fecha=dia_habil_pasado(4))
        self.assertEqual(self._marcar(s, self._objetivos(1)[0]).status_code, 200)


if __name__ == '__main__':
    unittest.main()

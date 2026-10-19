"""
tests/nube/test_portal_familiar_api.py — portal del familiar (Entrega 4).

seed.sql: familiar 1 (Marta) -> paciente 1; familiar 2 (Jorge) -> paciente 2.
Las sesiones del seed son de junio de 2026 (pasadas).
"""
import datetime as dt
import json
import unittest

from _base import BaseApi, hoy


def proximo_lunes(desde_dias=14):
    d = hoy() + dt.timedelta(days=desde_dias)
    while d.weekday() != 0:
        d += dt.timedelta(days=1)
    return d.isoformat()


PROHIBIDAS = ('diagnostico', 'observaciones', 'terapeuta', 'motivo_baja',
              'nro_historia', 'obra_social', 'notas')


class PortalFamiliarApi(BaseApi):
    def test_solo_rol_familiar(self):
        for quien in ('laura', 'rrhh', 'admin', 'paciente'):
            self.assertEqual(self.llamar(quien, 'get', '/api/familiar/pacientes').status_code, 403, quien)
            self.assertEqual(self.llamar(quien, 'get', '/api/familiar/pacientes/1/evolucion').status_code, 403, quien)
        self.assertEqual(self.llamar(None, 'get', '/api/familiar/pacientes').status_code, 401)

    def test_pacientes_vinculados(self):
        r = self.llamar('familiar', 'get', '/api/familiar/pacientes')
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertEqual([p['id'] for p in d['pacientes']], [1])
        self.assertEqual(d['pacientes'][0]['estado'], 'en_tratamiento')

    def test_evolucion_reducida(self):
        r = self.llamar('familiar', 'get', '/api/familiar/pacientes/1/evolucion')
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        d = r.get_json()
        self.assertGreater(len(d['objetivos']), 0)
        self.assertGreater(d['total_calificados'], 0)
        self.assertGreater(d['total_sesiones'], 0)
        # nada clinico por fuera de lo acordado, en ningun nivel del JSON
        texto = json.dumps(d)
        for clave in PROHIBIDAS:
            self.assertNotIn(f'"{clave}"', texto, clave)
        # cada objetivo trae su resumen y cada sesion sus valores
        o = d['objetivos'][0]
        self.assertIn('ultimo', o['resumen'])
        self.assertNotIn('promedio', o['resumen'])  # la escala se comunica en palabras, no en numeros
        self.assertTrue(all('valor' in p for p in o['puntos']))

    def test_paciente_ajeno_o_inexistente(self):
        # Marta no ve al paciente 2 (vinculado a Jorge) ni uno inexistente
        self.assertEqual(self.llamar('familiar', 'get', '/api/familiar/pacientes/2/evolucion').status_code, 403)
        self.assertEqual(self.llamar('familiar', 'get', '/api/familiar/pacientes/999/evolucion').status_code, 403)

    def test_filtro_por_fecha(self):
        todo = self.llamar('familiar', 'get', '/api/familiar/pacientes/1/evolucion').get_json()
        r = self.llamar('familiar', 'get', '/api/familiar/pacientes/1/evolucion?desde=2026-06-09&hasta=2026-06-16')
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        fechas = {s['fecha'] for s in d['sesiones']}
        self.assertTrue(fechas <= {'2026-06-09', '2026-06-16'}, fechas)
        self.assertLess(d['total_sesiones'], todo['total_sesiones'])
        # rango invertido: error, no lista vacia
        r = self.llamar('familiar', 'get', '/api/familiar/pacientes/1/evolucion?desde=2026-06-16&hasta=2026-06-09')
        self.assertEqual(r.status_code, 400)

    def test_sesiones_futuras_no_se_muestran(self):
        fecha = proximo_lunes()
        r = self.llamar('laura', 'post', '/api/sesiones',
                        json={'id_paciente': 1, 'fecha': fecha, 'hora_inicio': '09:00', 'estado': 'incompleta'})
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        d = self.llamar('familiar', 'get', '/api/familiar/pacientes/1/evolucion').get_json()
        self.assertNotIn(fecha, {s['fecha'] for s in d['sesiones']})
        self.assertTrue(all(p['fecha'] <= hoy().isoformat() for o in d['objetivos'] for p in o['puntos']))
        self.assertLessEqual(d['periodo']['hasta'], hoy().isoformat())
        # control positivo: la terapeuta SI la ve en su version completa
        c = self.llamar('laura', 'get', '/api/pacientes/1/evolucion').get_json()
        self.assertIn(fecha, {p['fecha'] for o in c['objetivos'] for p in o['puntos']})

    def test_desvincular_corta_el_acceso(self):
        self.assertEqual(self.llamar('laura', 'post', '/api/pacientes/3/familiares', json={'id_familiar': 1}).status_code, 201)
        self.assertEqual(self.llamar('familiar', 'get', '/api/familiar/pacientes/3/evolucion').status_code, 200)
        self.assertEqual(self.llamar('laura', 'post', '/api/pacientes/3/familiares/1/desvinculacion').status_code, 200)
        self.assertEqual(self.llamar('familiar', 'get', '/api/familiar/pacientes/3/evolucion').status_code, 403)


if __name__ == '__main__':
    unittest.main()

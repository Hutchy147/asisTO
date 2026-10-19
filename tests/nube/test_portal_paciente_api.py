"""
tests/nube/test_portal_paciente_api.py — portal del paciente (Entrega 6, HDU 10).

seed.sql: usuario `camila.rios` (rol paciente) -> ficha 3. El paciente ve SUS
objetivos y su progreso, en solo lectura, con la misma vista reducida que el
familiar. No recibe informes.
"""
import json
import unittest

from _base import BaseApi, CONTRASENA

PROHIBIDAS = ('diagnostico', 'observaciones', 'terapeuta', 'motivo_baja',
              'nro_historia', 'obra_social', 'notas', 'autor', 'contenido')


class PortalPacienteApi(BaseApi):
    def test_solo_rol_paciente(self):
        for quien in ('laura', 'rrhh', 'admin', 'familiar'):
            self.assertEqual(self.llamar(quien, 'get', '/api/paciente/mi-progreso').status_code, 403, quien)
        self.assertEqual(self.llamar(None, 'get', '/api/paciente/mi-progreso').status_code, 401)

    def test_mi_progreso_es_el_propio(self):
        r = self.llamar('paciente', 'get', '/api/paciente/mi-progreso')
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        d = r.get_json()
        self.assertEqual(d['paciente']['id'], 3)
        self.assertEqual(d['paciente']['nombre_completo'], 'Camila Rios')
        self.assertGreater(len(d['objetivos']), 0)
        for o in d['objetivos']:
            self.assertIn('puntos', o)
            self.assertIn('ultimo', o['resumen'])
            self.assertNotIn('promedio', o['resumen'])
        # los objetivos son los de la ficha 3 y de nadie mas
        ids = {o['id'] for o in d['objetivos']}
        propios = {f[0] for f in self.sql('SELECT id FROM objetivos_terapeuticos WHERE id_paciente = 3')}
        self.assertTrue(ids)
        self.assertTrue(ids <= propios)
        # detalle de sesiones: es del portal familiar, no de este
        self.assertNotIn('sesiones', d)

    def test_vista_reducida_sin_contenido_clinico(self):
        d = self.llamar('paciente', 'get', '/api/paciente/mi-progreso').get_json()
        texto = json.dumps(d)
        for clave in PROHIBIDAS:
            self.assertNotIn(f'"{clave}"', texto, clave)

    def test_el_endpoint_ignora_cualquier_id_ajeno(self):
        # no existe ruta con id de paciente
        self.assertEqual(self.llamar('paciente', 'get', '/api/paciente/2/mi-progreso').status_code, 404)
        a = self.llamar('paciente', 'get', '/api/paciente/mi-progreso?id_paciente=1&id=1').get_json()
        self.assertEqual(a['paciente']['id'], 3)

    def test_filtro_de_fechas(self):
        r = self.llamar('paciente', 'get', '/api/paciente/mi-progreso?desde=2026-06-01&hasta=2026-06-10')
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        for o in r.get_json()['objetivos']:
            for p in o['puntos']:
                self.assertTrue('2026-06-01' <= p['fecha'] <= '2026-06-10', p)
        self.assertEqual(self.llamar('paciente', 'get', '/api/paciente/mi-progreso?desde=2026-06-10&hasta=2026-06-01').status_code, 400)
        self.assertEqual(self.llamar('paciente', 'get', '/api/paciente/mi-progreso?desde=hoy').status_code, 400)

    def test_el_paciente_no_accede_al_resto_de_la_api(self):
        for ruta in ('/api/pacientes/3', '/api/pacientes/3/evolucion', '/api/pacientes/3/informes',
                     '/api/informes/1', '/api/familiar/pacientes', '/api/familiar/pacientes/3/informes'):
            self.assertEqual(self.llamar('paciente', 'get', ruta).status_code, 403, ruta)

    def test_cuenta_de_paciente_sin_ficha(self):
        from sqlalchemy import text
        from app import db
        from app.utils.security import hashear_contrasena
        email = 'sin.ficha@asisto.local'
        with self.app.app_context():
            db.session.execute(text(
                "INSERT INTO usuarios (nombre, apellido, email, contrasena_hash, rol) "
                "VALUES ('Sin', 'Ficha', :e, :h, 'paciente')"), {'e': email, 'h': hashear_contrasena(CONTRASENA)})
            db.session.commit()
        try:
            r = self.client.post('/api/auth/login', json={'email': email, 'contrasena': CONTRASENA})
            self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
            token = r.get_json()['token']
            r = self.client.get('/api/paciente/mi-progreso', headers={'Authorization': f'Bearer {token}'})
            self.assertEqual(r.status_code, 409, r.get_data(as_text=True))
            self.assertIn('ficha de paciente', r.get_json()['mensaje'])
        finally:
            self.sql('DELETE FROM usuarios WHERE email = :e', e=email)


if __name__ == '__main__':
    unittest.main()

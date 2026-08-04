"""
tests/backend/test_autoria_evolucion_api.py

Pregunta especifica de esta ronda de auditoria: "¿puede un terapeuta
cargar evolucion sobre una sesion que no atendio manipulando la
peticion?" -- via la API real (no SQL directo, que ya se prueba en
tests/db/autorizacion/), con dos terapeutas reales del seed.

Tambien confirma que un terapeuta no puede hacerse pasar por otro al
REGISTRAR una sesion (decision 17: id_terapeuta del cuerpo se ignora).
"""

import unittest

import _entorno as e


class TestAutoriaEvolucionAPI(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.laura_id, cls.laura_rol, _ = e.obtener_usuario_por_email(e.EMAILS_SEED['terapeuta'])
        cls.diego_id, cls.diego_rol, _ = e.obtener_usuario_por_email(e.EMAILS_SEED['terapeuta2'])
        cls.tok_laura = e.token_valido(cls.laura_id, cls.laura_rol, e.EMAILS_SEED['terapeuta'])
        cls.tok_diego = e.token_valido(cls.diego_id, cls.diego_rol, e.EMAILS_SEED['terapeuta2'])

    def setUp(self):
        self.cliente = e.cliente()

    def _sesion_de_laura(self):
        """Sesion 1 del seed es del terapeuta 1 (Laura), paciente 1, completa."""
        return 1

    def test_terapeuta_ajeno_no_puede_cargar_evolucion_403(self):
        resp = self.cliente.post(
            '/api/evoluciones',
            headers=e.encabezado_auth(self.tok_diego),
            json={'id_sesion': self._sesion_de_laura(), 'id_objetivo': 3, 'valor': 4},
        )
        self.assertEqual(resp.status_code, 403, resp.get_json())
        cuerpo = resp.get_json()
        self.assertEqual(
            cuerpo['mensaje'],
            'Solo el terapeuta que atendio la sesion puede cargarle evolucion.',
        )
        # El 403 no debe filtrar de quien SI es la sesion (no dice "es de Laura")
        self.assertNotIn('laura', cuerpo['mensaje'].lower())
        self.assertNotIn('fernandez', cuerpo['mensaje'].lower())

    def test_terapeuta_ajeno_no_inserta_nada(self):
        with e.obtener_app().app_context():
            from app import db
            antes = db.session.execute(
                db.text('SELECT COUNT(*) FROM evoluciones WHERE id_sesion=1 AND id_objetivo=3')
            ).scalar()

        self.cliente.post(
            '/api/evoluciones',
            headers=e.encabezado_auth(self.tok_diego),
            json={'id_sesion': self._sesion_de_laura(), 'id_objetivo': 3, 'valor': 4},
        )

        with e.obtener_app().app_context():
            from app import db
            despues = db.session.execute(
                db.text('SELECT COUNT(*) FROM evoluciones WHERE id_sesion=1 AND id_objetivo=3')
            ).scalar()

        self.assertEqual(antes, despues, 'El intento rechazado no deberia insertar nada')

    def test_dueño_de_la_sesion_si_puede_cargar_evolucion(self):
        """Control: confirma que el 403 es por autoria, no por otra cosa."""
        resp = self.cliente.post(
            '/api/evoluciones',
            headers=e.encabezado_auth(self.tok_laura),
            json={'id_sesion': self._sesion_de_laura(), 'id_objetivo': 3, 'valor': 4},
        )
        self.assertEqual(resp.status_code, 201, resp.get_json())

    def test_lectura_de_sesion_ajena_sigue_abierta_es_propia_false(self):
        """Decision 16: lectura abierta, escritura restringida."""
        resp = self.cliente.get(f'/api/sesiones/{self._sesion_de_laura()}', headers=e.encabezado_auth(self.tok_diego))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.get_json()['sesion']['es_propia'])

    def test_registrar_sesion_ignora_id_terapeuta_del_cuerpo(self):
        """Decision 17: no se puede llenar la agenda de otro terapeuta."""
        resp = self.cliente.post(
            '/api/sesiones',
            headers=e.encabezado_auth(self.tok_diego),
            json={
                'id_terapeuta': self.laura_id,  # intento de spoof: el id de USUARIO de Laura
                'id_paciente': 2,
                'fecha': '2026-10-20',
                'hora_inicio': '11:00:00',
                'estado': 'incompleta',
            },
        )
        self.assertEqual(resp.status_code, 201, resp.get_json())
        # id_terapeuta en la sesion creada tiene que ser el de Diego (terapeutas.id),
        # nunca el de Laura ni el usuarios.id que se mando en el cuerpo.
        with e.obtener_app().app_context():
            from app import db
            id_terapeuta_diego = db.session.execute(
                db.text('SELECT id FROM terapeutas WHERE id_usuario = :u'), {'u': self.diego_id}
            ).scalar()
        self.assertEqual(resp.get_json()['sesion']['id_terapeuta'], id_terapeuta_diego)


if __name__ == '__main__':
    unittest.main()

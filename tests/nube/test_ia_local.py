"""
tests/nube/test_ia_local.py

La IA local (Ollama) de los informes: el proveedor habla el formato de Ollama
y registra los tiempos, lo que viaja a la IA va compacto y una respuesta que
mezcla otro alfabeto se descarta. No necesita base ni Ollama real: usa un
servidor falso en el puerto 11997.
"""
import json
import os
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
sys.path.insert(0, BACKEND)

from flask import Flask  # noqa: E402

from app.services import informes_generador as g  # noqa: E402

PEDIDOS = []
RESPUESTA = {'texto': '## Evolución\n- Avanzó con apoyo.'}


class FalsoOllama(BaseHTTPRequestHandler):
    def do_POST(self):
        cuerpo = json.loads(self.rfile.read(int(self.headers['content-length'])))
        PEDIDOS.append((self.path, cuerpo))
        salida = json.dumps({
            'message': {'content': RESPUESTA['texto']},
            'total_duration': 12_000_000_000, 'load_duration': 2_000_000_000,
            'prompt_eval_count': 1000, 'prompt_eval_duration': 4_000_000_000,
            'eval_count': 200, 'eval_duration': 10_000_000_000,
        }).encode()
        self.send_response(200)
        self.send_header('content-type', 'application/json')
        self.end_headers()
        self.wfile.write(salida)

    def log_message(self, *args):
        pass


class IaLocalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.servidor = HTTPServer(('127.0.0.1', 11997), FalsoOllama)
        threading.Thread(target=cls.servidor.serve_forever, daemon=True).start()
        cls.app = Flask(__name__)
        cls.app.config.update(
            INFORMES_IA_PROVEEDOR='ollama', INFORMES_IA_MODELO='llama3.2:3b',
            INFORMES_IA_URL='http://127.0.0.1:11997', INFORMES_IA_TIMEOUT=10,
            INFORMES_IA_CTX=4096, INFORMES_IA_KEEP_ALIVE='30m',
        )

    @classmethod
    def tearDownClass(cls):
        cls.servidor.shutdown()

    def test_el_proveedor_local_se_detecta_y_no_sale_a_internet(self):
        with self.app.app_context():
            self.assertTrue(g.ia_disponible())
            self.assertTrue(g.ia_local())

    def test_sin_modelo_la_ia_queda_apagada(self):
        otra = Flask(__name__)
        otra.config.update(INFORMES_IA_PROVEEDOR='ollama', INFORMES_IA_MODELO='')
        with otra.app_context():
            self.assertFalse(g.ia_disponible())

    def test_el_pedido_usa_el_formato_de_ollama_y_mide_tiempos(self):
        PEDIDOS.clear()
        with self.app.app_context():
            proveedor = g.obtener_proveedor()
            texto = proveedor.redactar('instrucciones', '{}')
        ruta, cuerpo = PEDIDOS[0]
        self.assertEqual(ruta, '/api/chat')
        self.assertIs(cuerpo['stream'], False)
        self.assertEqual(cuerpo['keep_alive'], '30m')
        self.assertEqual(cuerpo['options']['num_ctx'], 4096)
        self.assertEqual(cuerpo['messages'][0]['role'], 'system')
        self.assertIn('Avanzó', texto)
        self.assertEqual(proveedor.ultima_medicion['tokens_por_s'], 20.0)
        self.assertEqual(proveedor.ultima_medicion['entrada_tokens'], 1000)

    def test_una_respuesta_con_otro_alfabeto_se_descarta(self):
        RESPUESTA['texto'] = '## Evolución\n- Avanzó y干预中 mejoró.'
        try:
            with self.app.app_context():
                with self.assertRaises(ValueError):
                    g._redactar_con_ia(g.obtener_proveedor(), {
                        'tipo': 'mensual', 'paciente': {'nombre': 'Ana', 'apellido': 'Paz', 'edad': '9 años'},
                        'periodo': {'desde': __import__('datetime').date(2026, 9, 1), 'hasta': __import__('datetime').date(2026, 9, 30)},
                        'asistencia': {}, 'objetivos': [], 'diarios': [], 'pti': None,
                    }, '# Encabezado')
        finally:
            RESPUESTA['texto'] = '## Evolución\n- Avanzó con apoyo.'

    def test_el_texto_en_espanol_con_tildes_y_enie_no_se_descarta(self):
        self.assertIsNone(g._OTRO_ALFABETO.search('Evolución: ñandú, acompañamiento, ¿cómo?'))

    def test_lo_que_viaja_a_la_ia_va_compacto_y_sin_ids(self):
        datos = {
            'tipo': 'mensual',
            'paciente': {'nombre': 'Lucía', 'apellido': 'Molina', 'edad': '9 años'},
            'periodo': {'desde': __import__('datetime').date(2026, 9, 1), 'hasta': __import__('datetime').date(2026, 9, 30)},
            'asistencia': {'sesiones': 4, 'ausencias': 0, 'sin_registrar': 0},
            'objetivos': [{'id': 7, 'descripcion': 'Escribir su nombre', 'activo': True, 'calificaciones': 2,
                           'nivel': 'Inicial', 'calificaciones_anterior': 0, 'nivel_anterior': None,
                           'tendencia': 'sin_datos', 'cambio': 'sin_datos'}],
            'diarios': [{'id_sesion': 3, 'fecha': '2026-09-02', 'hora_inicio': '10:00', 'estado': 'completa',
                         'nota': 'Lucía trabajó bien.', 'plan': [], 'registro': [],
                         'objetivos': [{'id_objetivo': 7, 'objetivo': 'Escribir su nombre', 'valor': 'Inicial',
                                        'observaciones': None}]}],
            'pti': None,
        }
        with self.app.app_context():
            enviado = g.datos_para_ia(datos)
        texto = json.dumps(enviado, ensure_ascii=False)
        for sobra in ('id_sesion', 'id_objetivo', 'hora_inicio', 'sin_datos', 'plan', 'registro', 'ingreso'):
            self.assertNotIn(sobra, texto)
        self.assertNotIn('Lucía', texto)            # el nombre sigue sin viajar
        self.assertIn('el paciente trabajó bien', texto)
        self.assertEqual(enviado['asistencia']['ausencias'], 0)   # un cero real no se pierde

    def test_el_markdown_de_los_modelos_se_normaliza(self):
        sucio = ('Aquí está el informe:\n### Evolución del período:\n**El paciente** trabajó con *apoyo*.\n'
                 '* Escribió su nombre\n#### Diarios de Sesiones\n- **2026-10-01**: Sesión trabajada.\n')
        limpio = g._limpiar_formato(sucio)
        for sobra in ('**', '###', '####', '`', '* '):
            self.assertNotIn(sobra, limpio)
        self.assertIn('## Evolución del período', limpio)
        self.assertIn('El paciente trabajó con apoyo.', limpio)
        self.assertIn('- Escribió su nombre', limpio)

    def test_las_secciones_que_arma_el_sistema_no_se_repiten(self):
        cuerpo = g._limpiar_formato('## Asistencia\nAsistió.\n\n## Diarios de Sesiones\n- 2026-10-01\n\n'
                                    '## Evolución del período\nMejoró.\n\n## Cierre y próximos pasos\n[COMPLETAR: pasos]')
        resto = g._sin_secciones_del_sistema(cuerpo)
        self.assertNotIn('Asistencia', resto)
        self.assertNotIn('Diarios', resto)
        self.assertIn('## Evolución del período', resto)
        self.assertIn('## Cierre y próximos pasos', resto)

    def test_el_informe_con_ia_combina_hechos_del_codigo_y_prosa_del_modelo(self):
        import datetime as dt
        RESPUESTA['texto'] = '### Evolución del período\n**El paciente** avanzó con apoyo.\n## Cierre y próximos pasos\n[COMPLETAR: pasos]'
        datos = {
            'tipo': 'mensual', 'clave': '2026-09',
            'paciente': {'nombre': 'Ana', 'apellido': 'Paz', 'nombre_completo': 'Ana Paz', 'edad': '9 años',
                         'fecha_nacimiento': dt.date(2017, 1, 1)},
            'periodo': {'desde': dt.date(2026, 9, 1), 'hasta': dt.date(2026, 9, 30)},
            'asistencia': {'sesiones': 4, 'ausencias': 1, 'sin_registrar': 0},
            'objetivos': [{'id': 7, 'descripcion': 'Escribir su nombre', 'activo': True, 'calificaciones': 2,
                           'nivel': 'Inicial', 'calificaciones_anterior': 0, 'nivel_anterior': None,
                           'tendencia': 'mejora', 'cambio': 'sin_datos'}],
            'diarios': [], 'pti': None,
        }
        try:
            with self.app.app_context():
                texto = g._redactar_con_ia(g.obtener_proveedor(), datos, '## Datos del paciente\nAna Paz.\n')
        finally:
            RESPUESTA['texto'] = '## Evolución\n- Avanzó con apoyo.'
        orden = [texto.index(t) for t in ('## Datos del paciente', '## Asistencia', '## Objetivos trabajados',
                                          '## Evolución del período', '## Cierre y próximos pasos')]
        self.assertEqual(orden, sorted(orden))
        self.assertIn('asistió a 4 sesiones y faltó a 1', texto)
        self.assertIn('Escribir su nombre: Inicial', texto)
        self.assertNotIn('**', texto)
        self.assertNotIn('###', texto)


if __name__ == '__main__':
    unittest.main()

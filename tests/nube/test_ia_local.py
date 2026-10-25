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
        texto = RESPUESTA['cola'].pop(0) if RESPUESTA.get('cola') else RESPUESTA['texto']
        salida = json.dumps({
            'message': {'content': texto},
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
                           'tendencia': 'mejora', 'cambio': 'sin_datos'}],
            'diarios': [{'id_sesion': 3, 'fecha': '2026-09-02', 'hora_inicio': '10:00', 'estado': 'completa',
                         'nota': 'Lucía trabajó bien.', 'plan': [], 'registro': [],
                         'objetivos': [{'id_objetivo': 7, 'objetivo': 'Escribir su nombre', 'valor': 'Inicial',
                                        'observaciones': None}]}],
            'pti': None,
        }
        with self.app.app_context():
            enviado = g.datos_para_ia(datos)
        texto = json.dumps(enviado, ensure_ascii=False)
        for sobra in ('id_sesion', 'id_objetivo', 'hora_inicio', 'sin_datos', 'plan', 'registro', 'ingreso',
                      'asistencia', '2026-09', 'Inicial', 'completa'):
            self.assertNotIn(sobra, texto)   # sin fechas, niveles, conteos ni ids: eso lo muestra el sistema
        self.assertNotIn('Lucía', texto)            # el nombre sigue sin viajar
        self.assertIn('el paciente trabajó bien', texto)
        self.assertEqual(enviado['objetivos'][0]['tendencia'], 'tendencia de mejora')

    def test_el_pti_conserva_los_ceros_reales_al_compactar(self):
        datos = {
            'tipo': 'pti',
            'paciente': {'nombre': 'Lucía', 'apellido': 'Molina', 'edad': '9 años'},
            'periodo': {'desde': __import__('datetime').date(2026, 9, 1), 'hasta': __import__('datetime').date(2026, 9, 30)},
            'asistencia': {'sesiones': 4, 'ausencias': 0, 'sin_registrar': 0},
            'objetivos': [], 'diarios': [], 'pti': {'etapas': []},
        }
        with self.app.app_context():
            enviado = g.datos_para_ia(datos)
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
        self.assertNotIn('Cierre', resto)   # el cierre lo agrega el sistema, no el modelo

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
        self.assertEqual(texto.count('## Cierre y próximos pasos'), 1)
        self.assertTrue(texto.rstrip().endswith(']'))   # termina con la marca [COMPLETAR]

    # --- parametros y retroalimentacion ---------------------------------
    def _datos_mensual(self):
        import datetime as dt
        return {
            'tipo': 'mensual', 'clave': '2026-09',
            'paciente': {'nombre': 'Ana', 'apellido': 'Paz', 'nombre_completo': 'Ana Paz', 'edad': '9 años',
                         'fecha_nacimiento': dt.date(2017, 1, 1)},
            'periodo': {'desde': dt.date(2026, 9, 1), 'hasta': dt.date(2026, 9, 30)},
            'asistencia': {'sesiones': 4, 'ausencias': 0, 'sin_registrar': 0},
            'objetivos': [], 'diarios': [], 'pti': None,
        }

    BUENO = ('## Evolución del período\nDurante el mes el paciente participó de las propuestas de motricidad fina.\n\n'
             'Requirió indicaciones verbales en la segunda parte de algunas actividades.\n\n'
             'La tolerancia a estímulos sensoriales nuevos muestra una tendencia favorable.')

    def test_los_parametros_de_generacion_viajan_a_ollama(self):
        PEDIDOS.clear()
        with self.app.app_context():
            g.obtener_proveedor().redactar('i', '{}', max_tokens=700)
        opciones = PEDIDOS[0][1]['options']
        self.assertEqual(opciones['temperature'], 0.1)
        self.assertEqual(opciones['repeat_penalty'], 1.15)
        self.assertEqual(opciones['seed'], 7)
        self.assertEqual(opciones['num_predict'], 700)

    def test_el_env_cambia_los_parametros_y_la_semilla_cero_la_quita(self):
        otra = Flask(__name__)
        otra.config.update(INFORMES_IA_PROVEEDOR='ollama', INFORMES_IA_MODELO='m', INFORMES_IA_TEMPERATURA=0.4,
                           INFORMES_IA_REPETICION=1.3, INFORMES_IA_SEMILLA=0)
        with otra.app_context():
            opciones = g.obtener_proveedor().opciones
        self.assertEqual(opciones['temperature'], 0.4)
        self.assertEqual(opciones['repeat_penalty'], 1.3)
        self.assertNotIn('seed', opciones)

    def test_la_revision_detecta_lo_que_los_datos_no_respaldan(self):
        ok = g.verificar_evolucion(self.BUENO, 'mensual')
        self.assertEqual(ok, [])
        casos = {
            'números': '## Evolución del período\nAsistió a 12 sesiones.',
            'niveles': '## Evolución del período\nEl paciente llegó a "Avanzado" en la tarea.',
            'causas': '## Evolución del período\nLa sesión se cortó debido a la fatiga.',
            'pasos': '## Evolución del período\nSe recomienda practicar en casa.',
            'párrafos': '## Evolución del período\nUno.\n\nDos.\n\nTres.\n\nCuatro.',
            'repite': '## Evolución del período\nEl paciente trabajó con buena disposición en la mesa.\n\n'
                      'El paciente trabajó con buena disposición en la mesa.',
        }
        for nombre, texto in casos.items():
            self.assertTrue(g.verificar_evolucion(texto, 'mensual'), nombre)
        copia = '## Evolución del período\n' + '\n\n'.join(g._EJEMPLO_ESTILO)
        self.assertTrue(any('ejemplo' in p for p in g.verificar_evolucion(copia, 'mensual')))
        # una marca [COMPLETAR] con números no cuenta como número escrito por el modelo
        self.assertEqual(g.verificar_evolucion('## Evolución del período\n[COMPLETAR: 3 sesiones]', 'mensual'), [])

    def test_si_el_texto_tiene_problemas_el_modelo_lo_corrige_una_vez(self):
        PEDIDOS.clear()
        RESPUESTA['cola'] = ['## Evolución del período\nAsistió a 12 sesiones debido a la fatiga.', self.BUENO]
        try:
            with self.app.app_context():
                proveedor = g.obtener_proveedor()
                texto = g._redactar_con_ia(proveedor, self._datos_mensual(), '## Datos del paciente\nAna Paz.\n')
        finally:
            RESPUESTA['cola'] = []
        self.assertEqual(len(PEDIDOS), 2)
        segundo = PEDIDOS[1][1]['messages']
        self.assertEqual([m['role'] for m in segundo], ['system', 'user', 'assistant', 'user'])
        self.assertIn('problemas', segundo[3]['content'])
        self.assertIn('motricidad fina', texto)
        self.assertNotIn('12 sesiones debido', texto)
        self.assertEqual(proveedor.reintentos, 1)
        self.assertEqual(proveedor.problemas, ())

    def test_si_la_correccion_no_mejora_se_avisa_y_se_conserva_el_mejor(self):
        malo = '## Evolución del período\nAsistió a 12 sesiones debido a la fatiga.'
        RESPUESTA['cola'] = [malo, malo]
        try:
            with self.app.app_context():
                proveedor = g.obtener_proveedor()
                g._redactar_con_ia(proveedor, self._datos_mensual(), '## Datos del paciente\nAna Paz.\n')
        finally:
            RESPUESTA['cola'] = []
        self.assertEqual(proveedor.reintentos, 1)
        self.assertTrue(proveedor.problemas)

    def test_un_texto_correcto_no_pide_segunda_pasada(self):
        PEDIDOS.clear()
        RESPUESTA['cola'] = [self.BUENO]
        try:
            with self.app.app_context():
                proveedor = g.obtener_proveedor()
                g._redactar_con_ia(proveedor, self._datos_mensual(), '## Datos del paciente\nAna Paz.\n')
        finally:
            RESPUESTA['cola'] = []
        self.assertEqual(len(PEDIDOS), 1)
        self.assertEqual(proveedor.reintentos, 0)


if __name__ == '__main__':
    unittest.main()

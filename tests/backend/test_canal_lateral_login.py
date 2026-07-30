"""
tests/backend/test_canal_lateral_login.py

El mensaje de /auth/login ya es identico para email inexistente, contrasena
incorrecta y cuenta inactiva (confirmado por Terminal 1 e igual aca abajo).
Lo que se pide en esta ronda es ir mas alla del texto: ¿hay otro canal --
tiempo de respuesta, codigo HTTP, forma de la respuesta, headers -- que
permita distinguir un email registrado de uno que no lo esta?

Encontrado: el canal de TIEMPO es real y esta cuantificado abajo. auth_service.py
documenta la decision de no cerrarlo ("excede el alcance del proyecto"), pero
el mensaje de esta ronda de auditoria dice que "ya esta decidido cerrarlo con
un hash dummy". Son dos cosas distintas: el codigo actual NO implementa un
hash dummy. Ver AUDITORIA.md, seccion "Para la otra terminal", para la
contradiccion completa -- no se resuelve aca, se deja documentada y medida.

Los otros canales (status code, forma de la respuesta, headers) se miden
tambien: si alguno difiere, este test lo va a mostrar como FAIL con el
detalle de que headers/campos cambiaron.
"""

import statistics
import time
import unittest

import _entorno as e

REPETICIONES = 60  # suficientes para una mediana estable sin que el test tarde demasiado


def _medir_login(cliente, email, contrasena):
    inicio = time.perf_counter()
    resp = cliente.post('/api/auth/login', json={'email': email, 'contrasena': contrasena})
    duracion = time.perf_counter() - inicio
    return duracion, resp


class TestCanalLateralLogin(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.id_usuario, cls.rol, cls.activo_original = e.obtener_usuario_por_email(e.EMAILS_SEED['terapeuta'])
        cls.email = e.EMAILS_SEED['terapeuta']

    def setUp(self):
        self.cliente = e.cliente()

    def tearDown(self):
        e.establecer_activo(self.id_usuario, self.activo_original)

    def test_mensaje_identico_en_los_tres_casos(self):
        """Regresion de lo que Terminal 1 ya verifico: se repite aca por si algo cambio."""
        e.establecer_activo(self.id_usuario, False)
        resp_inactivo = self.cliente.post(
            '/api/auth/login', json={'email': self.email, 'contrasena': e.CONTRASENA_SEED}
        )
        e.establecer_activo(self.id_usuario, True)

        resp_email_inexistente = self.cliente.post(
            '/api/auth/login', json={'email': 'no-existe-nadie@asisto.local', 'contrasena': 'lo que sea'}
        )
        resp_contrasena_mala = self.cliente.post(
            '/api/auth/login', json={'email': self.email, 'contrasena': 'contrasena-incorrecta'}
        )

        mensajes = {
            resp_email_inexistente.get_json()['mensaje'],
            resp_contrasena_mala.get_json()['mensaje'],
            resp_inactivo.get_json()['mensaje'],
        }
        self.assertEqual(len(mensajes), 1, f'Los mensajes difieren: {mensajes}')

        codigos = {
            resp_email_inexistente.get_json()['codigo'],
            resp_contrasena_mala.get_json()['codigo'],
            resp_inactivo.get_json()['codigo'],
        }
        self.assertEqual(len(codigos), 1, f'Los codigos difieren: {codigos}')

        status = {resp_email_inexistente.status_code, resp_contrasena_mala.status_code, resp_inactivo.status_code}
        self.assertEqual(status, {401}, f'Los status code difieren: {status}')

    def test_forma_y_headers_de_la_respuesta_identicos(self):
        """
        Mas alla del mensaje: mismo set de claves JSON, mismo Content-Type,
        mismo Content-Length (ya que el JSON es identico, deberia serlo).
        """
        resp_a = self.cliente.post(
            '/api/auth/login', json={'email': 'no-existe-nadie@asisto.local', 'contrasena': 'x'}
        )
        resp_b = self.cliente.post(
            '/api/auth/login', json={'email': self.email, 'contrasena': 'contrasena-incorrecta'}
        )

        self.assertEqual(set(resp_a.get_json().keys()), set(resp_b.get_json().keys()))
        self.assertEqual(resp_a.content_type, resp_b.content_type)
        self.assertEqual(resp_a.content_length, resp_b.content_length)

        # Headers de respuesta: se excluyen los que varian por diseño (fecha,
        # y cualquier identificador de request) y se compara el resto.
        excluidos = {'Date', 'Server'}
        headers_a = {k: v for k, v in resp_a.headers.items() if k not in excluidos}
        headers_b = {k: v for k, v in resp_b.headers.items() if k not in excluidos}
        self.assertEqual(headers_a, headers_b)

    def test_canal_de_temporizacion_email_inexistente_vs_existente(self):
        """
        Mide N repeticiones intercaladas (no en bloque, para promediar
        ruido del sistema por igual en los dos grupos) de:
          A) email que no existe -> nunca corre bcrypt
          B) email que existe, contrasena incorrecta -> corre bcrypt.checkpw
             una vez y falla

        Umbral: la diferencia de medianas deberia ser una fraccion chica
        del costo de UNA corrida de bcrypt (que se mide en el mismo test),
        no una fraccion comparable. Hoy se espera que ESTE test falle: el
        canal existe y esta documentado como abierto (ver docstring del
        modulo). Cuando se implemente el hash dummy, deberia pasar a PASS
        sin tocar el test.
        """
        tiempos_inexistente = []
        tiempos_existente = []

        for _ in range(REPETICIONES):
            d1, _ = _medir_login(self.cliente, 'no-existe-nadie@asisto.local', 'cualquier-cosa')
            tiempos_inexistente.append(d1)
            d2, _ = _medir_login(self.cliente, self.email, 'contrasena-incorrecta')
            tiempos_existente.append(d2)

        mediana_inexistente = statistics.median(tiempos_inexistente)
        mediana_existente = statistics.median(tiempos_existente)
        diferencia = mediana_existente - mediana_inexistente

        # Umbral relativo al costo real de bcrypt medido en esta misma
        # corrida, no un numero de milisegundos fijo que dependa del
        # hardware: 15% del costo de una corrida de bcrypt.
        umbral = max(0.005, mediana_existente * 0.15)

        detalle = (
            f'mediana email inexistente: {mediana_inexistente*1000:.2f} ms | '
            f'mediana email existente (bcrypt corre): {mediana_existente*1000:.2f} ms | '
            f'diferencia: {diferencia*1000:.2f} ms | umbral aceptado: {umbral*1000:.2f} ms'
        )
        print(f'\n[canal de temporizacion] {detalle}')

        self.assertLess(
            diferencia, umbral,
            'Canal lateral de temporizacion real y medible: cuando el email no '
            f'existe, la respuesta llega notablemente mas rapido ({detalle}). '
            'Permite distinguir un email registrado de uno que no lo esta sin '
            'leer el mensaje. auth_service.py documenta esto como fuera de '
            'alcance; si se decidio cerrar con un hash dummy, todavia no esta '
            'implementado.'
        )


if __name__ == '__main__':
    unittest.main()

"""
tests/backend/test_manejo_errores_backend.py

Confirma el criterio general de errores del backend (ver decision 6 de
ESTADO.md y app/utils/errors.py): ningun texto crudo de MySQL ni ninguna
traza de Python llega al cliente, en NINGUN camino, incluido el manejador
global de Exception. La unica excepcion deliberada es el errno 1644 (nuestros
propios SIGNAL, ya en castellano).

Dos niveles de prueba, por una limitacion real de lo que existe hoy:

1. A traves de HTTP de verdad (/auth/login), para lo que SI se puede
   disparar sin escribir codigo de aplicacion: un error no controlado de
   Python (no un error de base). No hay endpoint de negocio que escriba en
   la base todavia, asi que un error de MySQL real (FK, deadlock, SIGNAL de
   trigger) no se puede disparar de punta a punta por HTTP con lo que existe.

2. Unitariamente, contra traducir_error_db() / obtener_errno() /
   obtener_texto_signal() directamente, con excepciones de SQLAlchemy
   sinteticas que imitan lo que SQLAlchemy envuelve para un error de MySQL
   real (mismo shape: error.orig.args = (numero, texto)). Esto SI es la
   funcion de produccion real, ejercitada con datos fabricados en vez de
   una conexion real -- no es una reimplementacion propia del criterio.
"""

import unittest

from sqlalchemy.exc import IntegrityError, OperationalError

import _entorno as e
from app.utils.errors import MENSAJE_GENERICO, traducir_error_db


def _excepcion_sintetica(clase_sqlalchemy, numero_errno, texto_original):
    """
    Fabrica una excepcion de SQLAlchemy cuyo .orig.args tiene la forma que
    PyMySQL produce de verdad: (numero, texto). No abre ninguna conexion.
    """
    class _ErrorOriginalFalso(Exception):
        def __init__(self):
            super().__init__(numero_errno, texto_original)
            self.args = (numero_errno, texto_original)

    return clase_sqlalchemy('SELECT 1', {}, _ErrorOriginalFalso())


class TestManejoErroresHTTP(unittest.TestCase):
    """Nivel 1: a traves de la app real, via /auth/login."""

    def setUp(self):
        self.cliente = e.cliente()

    def test_error_no_controlado_de_python_no_filtra_traza(self):
        """
        email como entero rompe email.strip() dentro de autenticar() con un
        AttributeError -- una excepcion NO contemplada por ErrorAplicacion
        ni por SQLAlchemyError. Tiene que caer en el manejador global de
        Exception y volver saneado.
        """
        resp = self.cliente.post('/api/auth/login', json={'email': 12345, 'contrasena': 'x'})

        self.assertEqual(resp.status_code, 500)
        cuerpo = resp.get_json()
        self.assertEqual(cuerpo.get('codigo'), 'error_interno')

        texto_completo = str(cuerpo)
        for fuga in ('AttributeError', 'Traceback', "'int' object", '.py", line', 'strip'):
            self.assertNotIn(fuga, texto_completo, f'La respuesta filtra "{fuga}": {cuerpo}')

    def test_error_no_controlado_con_email_lista_tampoco_filtra(self):
        resp = self.cliente.post('/api/auth/login', json={'email': ['a', 'b'], 'contrasena': 'x'})
        self.assertEqual(resp.status_code, 500)
        self.assertEqual(resp.get_json().get('codigo'), 'error_interno')

    def test_json_malformado_no_rompe_con_500(self):
        """Content-Type json pero cuerpo invalido: get_json(silent=True) -> None, manejado limpio."""
        resp = self.cliente.post(
            '/api/auth/login', data='esto no es json{{{', content_type='application/json'
        )
        self.assertIn(resp.status_code, (400, 401))
        self.assertNotEqual(resp.status_code, 500)

    def test_ruta_inexistente_da_404_propio(self):
        resp = self.cliente.get('/api/esta_ruta_no_existe')
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.get_json().get('codigo'), 'no_encontrado')

    def test_metodo_no_permitido_da_405_propio(self):
        resp = self.cliente.get('/api/auth/login')  # login es solo POST
        self.assertEqual(resp.status_code, 405)
        self.assertEqual(resp.get_json().get('codigo'), 'metodo_no_permitido')


class TestTraducirErrorDB(unittest.TestCase):
    """Nivel 2: la funcion de traduccion, con excepciones de MySQL sinteticas."""

    def test_fk_violation_no_filtra_estructura(self):
        error = _excepcion_sintetica(
            IntegrityError, 1452,
            "Cannot add or update a child row: a foreign key constraint fails "
            "(`asisto_test_backend`.`pacientes`, CONSTRAINT `fk_pacientes_usuario` "
            "FOREIGN KEY (`id_usuario`) REFERENCES `usuarios` (`id`))",
        )
        mensaje = traducir_error_db(error)
        for fuga in ('asisto_test_backend', 'CONSTRAINT', 'fk_pacientes_usuario', 'FOREIGN KEY'):
            self.assertNotIn(fuga, mensaje)
        self.assertNotEqual(mensaje, MENSAJE_GENERICO)  # tiene traduccion especifica (ERRNO_FK)

    def test_duplicado_no_filtra_nombre_de_indice(self):
        error = _excepcion_sintetica(
            IntegrityError, 1062,
            "Duplicate entry 'HC-0001' for key 'pacientes.uq_pacientes_nro_historia'",
        )
        mensaje = traducir_error_db(error)
        self.assertNotIn('uq_pacientes_nro_historia', mensaje)
        self.assertNotIn('pacientes.', mensaje)

    def test_deadlock_no_filtra_y_da_mensaje_reintentable(self):
        error = _excepcion_sintetica(OperationalError, 1213, 'Deadlock found when trying to get lock')
        mensaje = traducir_error_db(error)
        self.assertNotIn('Deadlock found', mensaje)
        self.assertIn('mismo tiempo', mensaje.lower())

    def test_errno_1644_propaga_el_signal_tal_cual(self):
        """
        UNICA excepcion deliberada del criterio: nuestros propios SIGNAL,
        ya en castellano. Confirma que el texto SI se propaga sin cambios.
        """
        texto_signal = 'El paciente ya tiene 4 objetivos activos. Archive uno antes de crear otro'
        error = _excepcion_sintetica(OperationalError, 1644, texto_signal)
        mensaje = traducir_error_db(error)
        self.assertEqual(mensaje, texto_signal)

    def test_errno_desconocido_cae_al_mensaje_generico(self):
        error = _excepcion_sintetica(OperationalError, 9999, 'Algun error interno de MySQL nunca visto')
        mensaje = traducir_error_db(error)
        self.assertEqual(mensaje, MENSAJE_GENERICO)
        self.assertNotIn('Algun error interno', mensaje)


if __name__ == '__main__':
    unittest.main()

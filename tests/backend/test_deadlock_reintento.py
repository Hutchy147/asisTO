"""
tests/backend/test_deadlock_reintento.py

La deuda mas vieja del proyecto: el test automatizado de
@reintentar_en_deadlock (decision 12 de ESTADO.md / HISTORIAL.md).

POR QUE ESTE TEST ES DELICADO. Ya hubo dos versiones que pasaron en verde
sin haber probado nada: el atacante tomaba un lock compartido por la FK y
respetaba el orden canonico sin querer, y cuando eso se arreglo, InnoDB
elegia como victima al propio atacante por ser la transaccion mas liviana.
En los dos casos la operacion terminaba bien y el test daba PASS sin que
hubiera existido ningun deadlock.

Por eso aca NO alcanza con afirmar que la operacion termino bien. Cada
corrida verifica las TRES cosas juntas:

  1. que hubo un deadlock NUEVO   -> el contador lock_deadlocks de InnoDB
                                     subio durante la ventana del ataque
  2. que el decorador REINTENTO   -> su propio logger emitio el WARNING
                                     'Deadlock en <funcion> (intento N...)'
  3. que la operacion se completo -> y dejo EXACTAMENTE una fila, no dos

Si el punto 1 falla, el ataque no reprodujo nada y el resto no significa
nada. Si el 2 falla, la operacion anduvo por otro motivo y el decorador no
tuvo nada que ver.

LAS DOS CONDICIONES DEL ATAQUE, que tienen que cumplirse juntas:

  a) Orden invertido con lectura CON LOCK. El atacante toma
     objetivos_terapeuticos ANTES que pacientes, al reves del orden
     canonico (pacientes -> terapeutas -> sesiones -> objetivos ->
     evoluciones). Y usa SELECT ... FOR UPDATE, no UPDATE: un UPDATE toma
     de paso un lock compartido sobre la fila padre por la FK y termina
     respetando el orden sin querer, que es como una de las dos versiones
     falsas pasaba en verde.
  b) El atacante tiene que ser MAS PESADO que la victima. InnoDB elige
     como victima a la transaccion con menos trabajo hecho. La victima
     llega con cero filas modificadas (el trigger corre BEFORE INSERT),
     asi que el atacante se carga con FILAS_DE_LASTRE filas modificadas
     antes de pedir el primer lock. Sin ese lastre, InnoDB mata al
     atacante y la victima nunca reintenta.

EL ATACANTE VA POR EL CLIENTE mysql CON --login-path=asisto, no por la
conexion de la app: el usuario de la app (asisto_app) no tiene privilegio
PROCESS, y sin PROCESS no se puede leer information_schema.INNODB_METRICS
-- medido: da 1227. El contador de deadlocks, que es la evidencia del
punto 1, solo se puede leer con el login privilegiado.

SINCRONIZACION SIN DORMIR A CIEGAS. El test no asume cuanto tarda el
atacante en tomar su primer lock: lo comprueba con un SELECT ... FOR
UPDATE NOWAIT desde la conexion de la app, que falla con 3572 mientras el
atacante lo tenga. Recien cuando eso falla se dispara la victima.

Uso: se corre con el resto de tests/backend.
    .\\run_backend_tests.ps1
"""

import logging
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest

import _entorno as e
from app import db
from app.services.objetivos_service import crear_objetivo
from app.utils.errors import ERRNO_DEADLOCK, obtener_errno
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, OperationalError

# Paciente 3 del seed tiene 1 objetivo activo: hay lugar para crear otro
# sin chocar con el limite de 4 de la regla 1.
PACIENTE = 3

# Sesion 1 y objetivo 2 son la combinacion valida del seed (sesion del
# terapeuta 1, paciente 1, sin evolucion sobre el objetivo 2 todavia).
SESION_EVOL = 1
OBJETIVO_EVOL = 2

# Cuantas filas modifica el atacante para pesar mas que la victima.
FILAS_DE_LASTRE = 200

# Cuanto retiene el atacante su primer lock antes de pedir el segundo. Solo
# tiene que alcanzar para que la victima quede bloqueada; la victima llega
# en decenas de milisegundos desde que se la dispara.
SEGUNDOS_DE_RETENCION = 3

MARCA_OBJETIVO = 'TEST deadlock reintento'
MARCA_LASTRE = 'lastre-deadlock-test'


def _buscar_mysql():
    """Mismo criterio que tests/db/lib/TestHelpers.ps1."""
    ruta_env = os.environ.get('ASISTO_MYSQL_EXE')
    if ruta_env and os.path.exists(ruta_env):
        return ruta_env
    candidatos = [
        r"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe",
        r"C:\Program Files\MySQL\MySQL Server 8.4\bin\mysql.exe",
        r"C:\Program Files\MySQL\MySQL Server 9.0\bin\mysql.exe",
        r"C:\Program Files\MySQL\MySQL Server 9.1\bin\mysql.exe",
        r"C:\xampp\mysql\bin\mysql.exe",
    ]
    for c in candidatos:
        if os.path.exists(c):
            return c
    return None


MYSQL_EXE = _buscar_mysql()


class CapturaDeLog(logging.Handler):
    """Escucha al logger del decorador. Es la evidencia del punto 2."""

    def __init__(self):
        super().__init__()
        self.registros = []

    def emit(self, record):
        self.registros.append(record)

    def reintentos_de(self, nombre_funcion):
        return [
            r for r in self.registros
            if r.levelno == logging.WARNING
            and 'Deadlock en' in r.getMessage()
            and nombre_funcion in r.getMessage()
        ]


@unittest.skipIf(MYSQL_EXE is None,
                 'No se encontro mysql.exe: el atacante necesita el cliente con '
                 '--login-path=asisto. Definir ASISTO_MYSQL_EXE.')
class TestDeadlockReintento(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = e.obtener_app()
        cls.db_name = e.NOMBRE_DB_TEST
        cls.laura_id, cls.laura_rol, _ = e.obtener_usuario_por_email(
            e.EMAILS_SEED['terapeuta'])
        cls.tok_laura = e.token_valido(
            cls.laura_id, cls.laura_rol, e.EMAILS_SEED['terapeuta'])

    def setUp(self):
        self._limpiar()
        self.captura = CapturaDeLog()
        self.logger_decorador = logging.getLogger('app.utils.db')
        self.logger_decorador.addHandler(self.captura)

    def tearDown(self):
        self.logger_decorador.removeHandler(self.captura)
        self._limpiar()

    # --- utilidades -----------------------------------------------------

    def _mysql_privilegiado(self, sql):
        """Corre SQL con --login-path=asisto (root). Devuelve el proceso."""
        with tempfile.NamedTemporaryFile('w', suffix='.sql', delete=False,
                                         encoding='utf-8') as archivo:
            archivo.write(sql)
            ruta = archivo.name
        try:
            with open(ruta, 'r', encoding='utf-8') as entrada:
                return subprocess.run(
                    [MYSQL_EXE, '--login-path=asisto', self.db_name],
                    stdin=entrada, capture_output=True, text=True)
        finally:
            os.unlink(ruta)

    def _contador_de_deadlocks(self):
        """
        Contador de deadlocks de InnoDB. Es GLOBAL del servidor: si algo mas
        estuviera provocando deadlocks en la misma maquina, el delta podria
        contar de mas, nunca de menos. Por eso la afirmacion es >= 1.
        """
        proceso = self._mysql_privilegiado(
            "SELECT COUNT FROM information_schema.INNODB_METRICS "
            "WHERE NAME='lock_deadlocks';")
        lineas = [l for l in proceso.stdout.splitlines() if l.strip()]
        if len(lineas) < 2:
            self.fail(
                'No se pudo leer el contador lock_deadlocks con '
                f'--login-path=asisto. stdout={proceso.stdout!r} '
                f'stderr={proceso.stderr!r}. Sin este contador el test no '
                'puede afirmar que hubo un deadlock, y sin eso no prueba nada.')
        return int(lineas[-1])

    def _limpiar(self):
        with self.app.app_context():
            db.session.rollback()
            db.session.execute(text(
                'DELETE FROM objetivos_terapeuticos WHERE descripcion LIKE :d'),
                {'d': MARCA_OBJETIVO + '%'})
            db.session.execute(text(
                'DELETE FROM evoluciones WHERE id_sesion = :s AND id_objetivo = :o'),
                {'s': SESION_EVOL, 'o': OBJETIVO_EVOL})
            db.session.execute(text(
                'DELETE FROM auditoria_accesos WHERE email LIKE :m'),
                {'m': MARCA_LASTRE + '%'})
            db.session.commit()

    def _sql_del_atacante(self, tabla_primero, tabla_despues):
        lastre = ','.join(
            f"(NULL,'{MARCA_LASTRE}-{i}','fallido')" for i in range(FILAS_DE_LASTRE))
        return f"""
START TRANSACTION;
INSERT INTO auditoria_accesos (id_usuario,email,resultado) VALUES {lastre};
{tabla_primero}
SELECT SLEEP({SEGUNDOS_DE_RETENCION});
{tabla_despues}
COMMIT;
"""

    def _lanzar_atacante(self, sql):
        resultado = {}

        def correr():
            resultado['proceso'] = self._mysql_privilegiado(sql)

        hilo = threading.Thread(target=correr, daemon=True)
        hilo.start()
        return hilo, resultado

    def _esperar_a_que_el_atacante_tenga_el_lock(self, sql_sonda, timeout=25):
        """
        Espera activa con NOWAIT en vez de dormir un rato fijo.

        Mientras el atacante retenga el lock, la sonda falla con 3572. Si en
        cambio la sonda pasa, el atacante todavia no lo tomo y hay que
        reintentar: disparar la victima antes de eso es una de las formas de
        que no se forme el ciclo y el test pase en verde sin probar nada.
        """
        inicio = time.time()
        with self.app.app_context():
            while time.time() - inicio < timeout:
                try:
                    db.session.execute(text(sql_sonda))
                    db.session.rollback()
                    time.sleep(0.2)
                except (OperationalError, DBAPIError):
                    db.session.rollback()
                    return True
        return False

    # --- 1. el test principal -------------------------------------------

    def test_deadlock_real_dispara_el_reintento_y_la_operacion_se_completa(self):
        """
        Camino ORM (crear_objetivo): el 1213 llega a Python y el decorador
        puede verlo.

        Victima:  trigger de objetivos -> pacientes FOR UPDATE, despues
                  objetivos_terapeuticos FOR SHARE.
        Atacante: objetivos_terapeuticos FOR UPDATE primero, pacientes
                  despues. Orden invertido.
        """
        sql = self._sql_del_atacante(
            f"SELECT id FROM objetivos_terapeuticos WHERE id_paciente={PACIENTE} FOR UPDATE;",
            f"SELECT id FROM pacientes WHERE id={PACIENTE} FOR UPDATE;")

        antes = self._contador_de_deadlocks()
        hilo, resultado = self._lanzar_atacante(sql)

        listo = self._esperar_a_que_el_atacante_tenga_el_lock(
            f"SELECT id FROM objetivos_terapeuticos WHERE id_paciente={PACIENTE} FOR UPDATE NOWAIT")
        self.assertTrue(
            listo,
            'El atacante nunca llego a retener el lock de objetivos_terapeuticos. '
            'Sin eso no hay orden invertido y el ciclo no se forma.')

        with self.app.app_context():
            objetivo = crear_objetivo({
                'id_paciente': PACIENTE,
                'descripcion': f'{MARCA_OBJETIVO} camino ORM',
            })
            id_creado = objetivo.id

        hilo.join(timeout=30)
        self.assertEqual(resultado['proceso'].returncode, 0,
                         f"El atacante fallo: {resultado['proceso'].stderr!r}")

        despues = self._contador_de_deadlocks()

        # 1. hubo un deadlock NUEVO
        self.assertGreaterEqual(
            despues - antes, 1,
            f'El contador lock_deadlocks de InnoDB no se movio ({antes} -> {despues}). '
            'No hubo ningun deadlock: el ataque no reprodujo la condicion y lo que '
            'siga no prueba nada.')

        # 2. el decorador REINTENTO
        reintentos = self.captura.reintentos_de('crear_objetivo')
        self.assertGreaterEqual(
            len(reintentos), 1,
            'Hubo un deadlock pero @reintentar_en_deadlock no registro ningun '
            'reintento. La operacion termino bien por otro motivo, no por el '
            f'decorador. Registros vistos: {[r.getMessage() for r in self.captura.registros]}')

        # 3. la operacion se completo, y una sola vez
        with self.app.app_context():
            filas = db.session.execute(text(
                'SELECT COUNT(*) FROM objetivos_terapeuticos WHERE descripcion LIKE :d'),
                {'d': MARCA_OBJETIVO + '%'}).scalar()
            db.session.rollback()
        self.assertEqual(
            filas, 1,
            f'Se esperaba exactamente 1 objetivo creado y hay {filas}. Si hay 2, el '
            'reintento repitio una operacion que ya habia quedado escrita.')
        self.assertIsNotNone(id_creado)

    # --- 2. la falsacion, dentro del propio test -------------------------

    def test_sin_el_decorador_el_mismo_ataque_propaga_el_1213(self):
        """
        Control de que el escenario ES el que dice ser.

        Corre EXACTAMENTE el mismo ataque contra la funcion SIN decorar
        (__wrapped__, que expone functools.wraps) y afirma que ahi si estalla
        con errno 1213. Si este test pasara sin excepcion, el escenario no
        estaria produciendo ningun deadlock en la victima y el test principal
        estaria dando PASS por casualidad.
        """
        sin_decorar = getattr(crear_objetivo, '__wrapped__', None)
        self.assertIsNotNone(
            sin_decorar,
            'crear_objetivo no expone __wrapped__: sin eso no se puede correr '
            'el control sin decorador.')

        sql = self._sql_del_atacante(
            f"SELECT id FROM objetivos_terapeuticos WHERE id_paciente={PACIENTE} FOR UPDATE;",
            f"SELECT id FROM pacientes WHERE id={PACIENTE} FOR UPDATE;")

        hilo, resultado = self._lanzar_atacante(sql)
        listo = self._esperar_a_que_el_atacante_tenga_el_lock(
            f"SELECT id FROM objetivos_terapeuticos WHERE id_paciente={PACIENTE} FOR UPDATE NOWAIT")
        self.assertTrue(listo, 'El atacante nunca retuvo el lock.')

        error = None
        with self.app.app_context():
            try:
                sin_decorar({
                    'id_paciente': PACIENTE,
                    'descripcion': f'{MARCA_OBJETIVO} sin decorador',
                })
            except (OperationalError, DBAPIError) as capturado:
                error = capturado
            finally:
                db.session.rollback()

        hilo.join(timeout=30)

        self.assertIsNotNone(
            error,
            'Sin el decorador la operacion NO fallo. Entonces el escenario no '
            'produce un deadlock en la victima, y el test principal esta '
            'pasando por casualidad.')
        self.assertEqual(
            obtener_errno(error), ERRNO_DEADLOCK,
            f'Fallo, pero no con 1213 sino con {obtener_errno(error)}: {error}')

        with self.app.app_context():
            filas = db.session.execute(text(
                'SELECT COUNT(*) FROM objetivos_terapeuticos WHERE descripcion LIKE :d'),
                {'d': MARCA_OBJETIVO + '%'}).scalar()
            db.session.rollback()
        self.assertEqual(filas, 0,
                         'La transaccion abortada por deadlock dejo filas escritas.')

    # --- 3. el hallazgo --------------------------------------------------

    def test_hallazgo_el_procedimiento_se_traga_el_deadlock_y_el_decorador_no_lo_ve(self):
        """
        HALLAZGO ABIERTO. Fija el comportamiento de hoy, no el deseado.

        p_registrar_evolucion tiene DECLARE EXIT HANDLER FOR SQLEXCEPTION.
        El deadlock (SQLSTATE '40001') entra por ese handler igual que
        cualquier otro error: el procedimiento hace ROLLBACK y devuelve
        p_mensaje = 'No se pudo registrar la evolucion por un error interno'
        con p_id_evolucion = NULL, y el CALL termina con exito.

        Consecuencia: por este camino Python NUNCA recibe un OperationalError
        1213, asi que @reintentar_en_deadlock no puede dispararse y el usuario
        ve un "error interno" ante una condicion transitoria que se resolvia
        sola con reintentar.

        Lo grave es cual es este camino: es el escenario CONCRETO de la
        decision 12 (sesiones <-> objetivos_terapeuticos via el trigger de
        evoluciones), el unico deadlock reproducible que el proyecto tiene
        documentado. El decorador esta puesto justo donde no puede funcionar.

        ESTE TEST VA A FALLAR CUANDO SE ARREGLE, y esta bien que asi sea: esa
        falla es la señal de que el procedimiento dejo de tragarse el 1213.
        """
        sql = self._sql_del_atacante(
            f"SELECT id FROM objetivos_terapeuticos WHERE id={OBJETIVO_EVOL} FOR UPDATE;",
            f"SELECT id FROM sesiones WHERE id={SESION_EVOL} FOR UPDATE;")

        antes = self._contador_de_deadlocks()
        hilo, resultado = self._lanzar_atacante(sql)

        listo = self._esperar_a_que_el_atacante_tenga_el_lock(
            f"SELECT id FROM objetivos_terapeuticos WHERE id={OBJETIVO_EVOL} FOR UPDATE NOWAIT")
        self.assertTrue(listo, 'El atacante nunca retuvo el lock del objetivo.')

        cliente = e.cliente()
        respuesta = cliente.post(
            '/api/evoluciones',
            headers=e.encabezado_auth(self.tok_laura),
            json={'id_sesion': SESION_EVOL, 'id_objetivo': OBJETIVO_EVOL, 'valor': 3},
        )

        hilo.join(timeout=30)
        despues = self._contador_de_deadlocks()

        # El deadlock ocurrio de verdad: eso no esta en duda.
        self.assertGreaterEqual(
            despues - antes, 1,
            f'El contador lock_deadlocks no se movio ({antes} -> {despues}): el '
            'ataque sobre el camino de evoluciones no reprodujo ningun deadlock, '
            'asi que este test no esta observando lo que dice observar.')

        # Y sin embargo el decorador no vio nada.
        reintentos = self.captura.reintentos_de('registrar_evolucion')
        self.assertEqual(
            len(reintentos), 0,
            'El decorador SI reintento en el camino de evoluciones. Si esto pasa, '
            'el hallazgo esta cerrado: p_registrar_evolucion dejo de tragarse el '
            '1213 y hay que reescribir este test en positivo.')

        cuerpo = respuesta.get_json()
        self.assertIn(
            'error interno', (cuerpo or {}).get('mensaje', '').lower(),
            f'Se esperaba el mensaje generico del EXIT HANDLER y llego: {cuerpo}')

        with self.app.app_context():
            filas = db.session.execute(text(
                'SELECT COUNT(*) FROM evoluciones WHERE id_sesion = :s AND id_objetivo = :o'),
                {'s': SESION_EVOL, 'o': OBJETIVO_EVOL}).scalar()
            db.session.rollback()
        self.assertEqual(filas, 0, 'El deadlock tragado dejo una evolucion escrita.')


if __name__ == '__main__':
    unittest.main(verbosity=2)

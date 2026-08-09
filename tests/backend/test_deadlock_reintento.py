"""
tests/backend/test_deadlock_reintento.py

Cierre de la decision 12: @reintentar_en_deadlock probado contra errores
reintentables REALES, en los cuatro caminos de escritura decorados.

HISTORIA CORTA DE POR QUE ESTO COSTO TANTO. Hubo dos versiones que pasaron
en verde sin haber probado nada (el atacante respetaba el orden de locks
sin querer; y despues InnoDB lo elegia victima a el por ser mas liviano).
Y cuando por fin el ataque funciono, aparecio que los tres procedimientos
de escritura se TRAGABAN el error: su EXIT HANDLER FOR SQLEXCEPTION
capturaba el 1213 y devolvia "error interno" con el CALL en exito, asi que
Python nunca veia nada que reintentar. Terminal 1 lo cerro agregando, en
los tres, un handler para SQLSTATE '40001' y otro para el errno 1205, los
dos con ROLLBACK + RESIGNAL (commit ff65741 y el cambio del 1205).

Este archivo verifica ese arreglo por cuenta propia y prueba el reintento
en los cuatro caminos.

QUE SE AFIRMA, Y POR QUE NO ALCANZA CON MENOS. En cada caso decorado se
verifican TRES cosas juntas; si falta cualquiera, el resto no significa
nada:

  1. hubo un error reintentable REAL   -> capa 1: el mismo escenario contra
                                          el procedimiento pelado devuelve
                                          errno 1213 / 1205 al cliente
  2. el decorador REINTENTO            -> su propio logger emitio el WARNING
  3. la operacion se completo          -> y dejo UNA fila, no dos

Afirmar solo el punto 3 es lo que tienta escribir y es exactamente lo que
pasa en verde sin probar nada.

LAS DOS CONDICIONES DEL ATAQUE DE DEADLOCK, que van juntas:
  a) Orden invertido y lectura CON LOCK. El atacante toma los recursos al
     reves del orden canonico (pacientes -> terapeutas -> sesiones ->
     objetivos -> evoluciones) con SELECT ... FOR UPDATE. Con un UPDATE no
     sirve: toma de paso un lock compartido en la fila padre por la FK y
     termina respetando el orden sin querer.
  b) El atacante es MAS PESADO. InnoDB mata a la transaccion con menos
     trabajo hecho. La victima llega con cero filas modificadas, asi que el
     atacante se carga con FILAS_DE_LASTRE filas antes de pedir su primer
     lock. Sin el lastre, InnoDB mata al atacante y no hay reintento.

EL LOCK WAIT TIMEOUT (1205) NO SE DEDUCE, SE PROVOCA. El atacante retiene
el recurso y la victima corre con innodb_lock_wait_timeout = 1.

Bajar ese valor cuesta mas de lo que parece, y las dos formas que usa este
archivo son necesarias, no redundantes:
  - Para la capa 2, que entra por HTTP, no hay manera de tocar la conexion
    que el pool le da al request: se pone un listener de 'connect' en el
    engine + dispose() del pool, para que TODA conexion nueva nazca con el
    timeout corto. Un SET SESSION suelto desde el test se aplicaria a la
    conexion del test, que no es la del request.
  - Para la capa 1 eso NO alcanzo. El listener solo cubre las conexiones
    que nacen despues del dispose(), y a esos contextos el pool les
    entregaba a veces una anterior: dos casos esperaban los 50 s por
    defecto, no expiraban nunca y el test pasaba en verde sin haber
    provocado ningun 1205. Como ahi la conexion del CALL SI es alcanzable,
    se le fija el timeout en la misma sesion, justo antes.
Los dos casos se detectaron corriendo el test, no leyendolo.

ESTRUCTURA. Dos capas por cada camino:
  capa 1 (verificacion del arreglo de Terminal 1): con el atacante puesto,
          se llama al PROCEDIMIENTO directo y se afirma el errno que llega.
          No participa el decorador. Es la medicion propia del "despues".
  capa 2 (el reintento): el mismo escenario por el servicio decorado.

EL ATACANTE VA POR EL CLIENTE mysql CON --login-path=asisto: el usuario de
la app no tiene privilegio PROCESS y sin PROCESS no se puede leer
information_schema.INNODB_METRICS -- medido, da 1227. El contador de
deadlocks es la evidencia dura del punto 1 en los casos de 1213.

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
from app.services.pacientes_service import alta_paciente
from app.utils.errors import ERRNO_DEADLOCK, ERRNO_LOCK_TIMEOUT, obtener_errno
from sqlalchemy import event, text
from sqlalchemy.exc import DBAPIError, OperationalError

# --- datos del seed que usan los escenarios -----------------------------
PACIENTE_ORM = 3        # tiene 1 objetivo activo: hay lugar para crear otro
TERAPEUTA = 1           # Laura
SESION = 1              # del terapeuta 1, paciente 1, completa
OBJETIVO = 2            # activo, del paciente 1, sin evolucion en la sesion 1
USUARIO_LIBRE = 4       # existe y no esta tomado por uq_pacientes_usuario

FILAS_DE_LASTRE = 200
SEGUNDOS_DE_RETENCION = 2
TIMEOUT_DE_LOCK = 1     # segundos, para provocar el 1205 rapido

MARCA_OBJETIVO = 'TEST deadlock objetivo'
MARCA_HISTORIA = 'HC-TEST-DL'
MARCA_NOTAS = 'TEST deadlock sesion'
MARCA_LASTRE = 'lastre-deadlock-test'

FECHA_SESION_LIBRE = '2026-12-01'   # sin sesiones del terapeuta 1 en el seed


def _buscar_mysql():
    """Mismo criterio que tests/db/lib/TestHelpers.ps1."""
    ruta_env = os.environ.get('ASISTO_MYSQL_EXE')
    if ruta_env and os.path.exists(ruta_env):
        return ruta_env
    for candidato in (
        r"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe",
        r"C:\Program Files\MySQL\MySQL Server 8.4\bin\mysql.exe",
        r"C:\Program Files\MySQL\MySQL Server 9.0\bin\mysql.exe",
        r"C:\Program Files\MySQL\MySQL Server 9.1\bin\mysql.exe",
        r"C:\xampp\mysql\bin\mysql.exe",
    ):
        if os.path.exists(candidato):
            return candidato
    return None


MYSQL_EXE = _buscar_mysql()


class CapturaDeLog(logging.Handler):
    """Escucha al logger del decorador: es la evidencia del punto 2."""

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

    def mensajes(self):
        return [r.getMessage() for r in self.registros]


@unittest.skipIf(MYSQL_EXE is None,
                 'No se encontro mysql.exe: el atacante necesita el cliente con '
                 '--login-path=asisto. Definir ASISTO_MYSQL_EXE.')
class BaseDeadlock(unittest.TestCase):
    """Andamiaje comun: atacante, sincronizacion, limpieza y contadores."""

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
        self._listener_timeout = None

    def tearDown(self):
        self.logger_decorador.removeHandler(self.captura)
        self._quitar_timeout_corto()
        self._limpiar()

    # --- infraestructura -------------------------------------------------

    def _mysql_privilegiado(self, sql):
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
        Contador de deadlocks de InnoDB. Es GLOBAL del servidor: si otra cosa
        provocara deadlocks en la misma maquina el delta contaria de mas,
        nunca de menos. Por eso se afirma >= 1.
        """
        proceso = self._mysql_privilegiado(
            "SELECT COUNT FROM information_schema.INNODB_METRICS "
            "WHERE NAME='lock_deadlocks';")
        lineas = [l for l in proceso.stdout.splitlines() if l.strip()]
        if len(lineas) < 2:
            self.fail(
                'No se pudo leer lock_deadlocks con --login-path=asisto. '
                f'stdout={proceso.stdout!r} stderr={proceso.stderr!r}. Sin ese '
                'contador el test no puede afirmar que hubo un deadlock.')
        return int(lineas[-1])

    def _limpiar(self):
        with self.app.app_context():
            db.session.rollback()
            for sentencia, parametros in (
                ('DELETE FROM objetivos_terapeuticos WHERE descripcion LIKE :m',
                 {'m': MARCA_OBJETIVO + '%'}),
                ('DELETE FROM evoluciones WHERE id_sesion = :s AND id_objetivo = :o',
                 {'s': SESION, 'o': OBJETIVO}),
                ('DELETE FROM sesiones WHERE notas LIKE :m', {'m': MARCA_NOTAS + '%'}),
                ('DELETE FROM pacientes WHERE nro_historia LIKE :m',
                 {'m': MARCA_HISTORIA + '%'}),
                ('DELETE FROM auditoria_accesos WHERE email LIKE :m',
                 {'m': MARCA_LASTRE + '%'}),
            ):
                db.session.execute(text(sentencia), parametros)
            db.session.commit()

    def _lastre(self):
        return ','.join(
            f"(NULL,'{MARCA_LASTRE}-{i}','fallido')" for i in range(FILAS_DE_LASTRE))

    def _lanzar_atacante(self, sql):
        resultado = {}

        def correr():
            resultado['proceso'] = self._mysql_privilegiado(sql)

        hilo = threading.Thread(target=correr, daemon=True)
        hilo.start()
        return hilo, resultado

    def _atacante_de_deadlock(self, primero, despues, cierre='COMMIT;'):
        """Lastre, toma un recurso, espera, y toma el segundo: orden invertido."""
        return (
            'START TRANSACTION;\n'
            f'INSERT INTO auditoria_accesos (id_usuario,email,resultado) VALUES {self._lastre()};\n'
            f'{primero}\n'
            f'SELECT SLEEP({SEGUNDOS_DE_RETENCION});\n'
            f'{despues}\n'
            f'{cierre}\n'
        )

    def _atacante_que_retiene(self, recurso):
        """Solo retiene: no pide un segundo recurso, asi no puede haber ciclo.
        Lo que provoca es espera pura, que termina en 1205."""
        return (
            'START TRANSACTION;\n'
            f'{recurso}\n'
            f'SELECT SLEEP({SEGUNDOS_DE_RETENCION});\n'
            'ROLLBACK;\n'
        )

    def _esperar_a_que_el_atacante_tenga_el_lock(self, sonda, timeout=25):
        """
        No duerme un rato fijo: comprueba. Mientras el atacante retenga el
        recurso, la sonda NOWAIT falla con 3572. Disparar la victima antes de
        eso es una de las formas de que no se forme nada y el test de verde.
        """
        inicio = time.time()
        with self.app.app_context():
            while time.time() - inicio < timeout:
                try:
                    db.session.execute(text(sonda))
                    db.session.rollback()
                    time.sleep(0.15)
                except (OperationalError, DBAPIError):
                    db.session.rollback()
                    return True
        return False

    def _poner_timeout_corto(self):
        """
        innodb_lock_wait_timeout = 1 en TODA conexion nueva del engine.

        Tiene que ser por listener + dispose(): un SET SESSION suelto desde el
        test se aplica a la conexion del test, no a la que el pool le da al
        request. Con eso la victima esperaba los 50 s por defecto, nunca
        expiraba, y el test pasaba sin haber provocado ningun 1205.
        """
        def al_conectar(conexion_dbapi, _registro):
            cursor = conexion_dbapi.cursor()
            cursor.execute(f'SET SESSION innodb_lock_wait_timeout = {TIMEOUT_DE_LOCK}')
            cursor.close()

        with self.app.app_context():
            motor = db.engine
        event.listen(motor, 'connect', al_conectar)
        motor.dispose()
        self._listener_timeout = (motor, al_conectar)

    def _quitar_timeout_corto(self):
        if not self._listener_timeout:
            return
        motor, funcion = self._listener_timeout
        event.remove(motor, 'connect', funcion)
        motor.dispose()
        self._listener_timeout = None

    def _llamar_procedimiento(self, sql, parametros, timeout_corto=False):
        """
        Llama al procedimiento pelado y devuelve la excepcion, o None.

        Con timeout_corto se fija innodb_lock_wait_timeout EN ESTA MISMA
        sesion, ademas del listener del engine. No es redundante: el listener
        solo alcanza a las conexiones que nazcan despues del dispose(), y la
        que el pool le entrega a este contexto puede ser una anterior. Con el
        listener solo, dos de estos casos esperaban los 50 s por defecto, no
        expiraban nunca y el test daba verde sin haber provocado ningun 1205.
        Aca la conexion es la misma que corre el CALL, asi que no hay duda.
        """
        with self.app.app_context():
            try:
                if timeout_corto:
                    db.session.execute(text(
                        f'SET SESSION innodb_lock_wait_timeout = {TIMEOUT_DE_LOCK}'))
                db.session.execute(text(sql), parametros)
                db.session.commit()
                return None
            except (OperationalError, DBAPIError) as error:
                return error
            finally:
                db.session.rollback()

    def _afirmar_errno(self, error, esperado, camino):
        self.assertIsNotNone(
            error,
            f'{camino}: el procedimiento NO propago ningun error. O el escenario '
            'no produjo la condicion, o el procedimiento se la volvio a tragar '
            '(que es el defecto que Terminal 1 cerro con ROLLBACK + RESIGNAL).')
        self.assertEqual(
            obtener_errno(error), esperado,
            f'{camino}: llego un error pero con errno {obtener_errno(error)} en vez '
            f'de {esperado}. Detalle: {str(error)[:200]}')


# =====================================================================
# CAPA 1 — verificacion propia del arreglo de Terminal 1
#
# Sin decorador de por medio: con el atacante puesto, se llama al
# PROCEDIMIENTO y se mira que errno llega al cliente. Antes del arreglo
# estos seis casos devolvian exito con p_mensaje de "error interno".
# =====================================================================
class TestElProcedimientoPropagaElError(BaseDeadlock):

    def test_alta_paciente_propaga_el_1213(self):
        sql = self._atacante_de_deadlock(
            f'SELECT id FROM usuarios WHERE id={USUARIO_LIBRE} FOR UPDATE;',
            'INSERT INTO pacientes (id_usuario,nombre,apellido,fecha_nacimiento,'
            f"nro_historia,activo,fecha_alta) VALUES (NULL,'Choque','Test',"
            f"'2015-01-01','{MARCA_HISTORIA}-1213',TRUE,CURRENT_DATE);",
            cierre='ROLLBACK;')
        antes = self._contador_de_deadlocks()
        hilo, _ = self._lanzar_atacante(sql)
        self.assertTrue(self._esperar_a_que_el_atacante_tenga_el_lock(
            f'SELECT id FROM usuarios WHERE id={USUARIO_LIBRE} FOR UPDATE NOWAIT'))

        error = self._llamar_procedimiento(
            'CALL p_alta_paciente(:nom,:ape,:fn,NULL,:hist,:usr,@id,@msg)',
            {'nom': 'Proto', 'ape': 'Deadlock', 'fn': '2015-01-01',
             'hist': f'{MARCA_HISTORIA}-1213', 'usr': USUARIO_LIBRE})

        hilo.join(timeout=30)
        self.assertGreaterEqual(self._contador_de_deadlocks() - antes, 1,
                                'El contador lock_deadlocks no se movio.')
        self._afirmar_errno(error, ERRNO_DEADLOCK, 'p_alta_paciente')

    def test_registrar_sesion_propaga_el_1213(self):
        sql = self._atacante_de_deadlock(
            f'SELECT id FROM sesiones WHERE id_terapeuta={TERAPEUTA} FOR UPDATE;',
            f'SELECT id FROM terapeutas WHERE id={TERAPEUTA} FOR UPDATE;')
        antes = self._contador_de_deadlocks()
        hilo, _ = self._lanzar_atacante(sql)
        self.assertTrue(self._esperar_a_que_el_atacante_tenga_el_lock(
            f'SELECT id FROM sesiones WHERE id_terapeuta={TERAPEUTA} FOR UPDATE NOWAIT'))

        error = self._llamar_procedimiento(
            'CALL p_registrar_sesion(:ter,:pac,:fecha,:hi,:hf,:est,:notas,@id,@msg)',
            {'ter': TERAPEUTA, 'pac': 1, 'fecha': FECHA_SESION_LIBRE,
             'hi': '08:00:00', 'hf': '09:00:00', 'est': 'completa',
             'notas': MARCA_NOTAS})

        hilo.join(timeout=30)
        self.assertGreaterEqual(self._contador_de_deadlocks() - antes, 1,
                                'El contador lock_deadlocks no se movio.')
        self._afirmar_errno(error, ERRNO_DEADLOCK, 'p_registrar_sesion')

    def test_registrar_evolucion_propaga_el_1213(self):
        sql = self._atacante_de_deadlock(
            f'SELECT id FROM objetivos_terapeuticos WHERE id={OBJETIVO} FOR UPDATE;',
            f'SELECT id FROM sesiones WHERE id={SESION} FOR UPDATE;')
        antes = self._contador_de_deadlocks()
        hilo, _ = self._lanzar_atacante(sql)
        self.assertTrue(self._esperar_a_que_el_atacante_tenga_el_lock(
            f'SELECT id FROM objetivos_terapeuticos WHERE id={OBJETIVO} FOR UPDATE NOWAIT'))

        error = self._llamar_procedimiento(
            'CALL p_registrar_evolucion(:ses,:obj,:val,NULL,:ter,@id,@msg)',
            {'ses': SESION, 'obj': OBJETIVO, 'val': 3, 'ter': TERAPEUTA})

        hilo.join(timeout=30)
        self.assertGreaterEqual(self._contador_de_deadlocks() - antes, 1,
                                'El contador lock_deadlocks no se movio.')
        self._afirmar_errno(error, ERRNO_DEADLOCK, 'p_registrar_evolucion')

    # --- los mismos tres, con lock wait timeout ---------------------------

    def test_alta_paciente_propaga_el_1205(self):
        self._poner_timeout_corto()
        sql = self._atacante_que_retiene(
            'INSERT INTO pacientes (id_usuario,nombre,apellido,fecha_nacimiento,'
            f"nro_historia,activo,fecha_alta) VALUES (NULL,'Retencion','Test',"
            f"'2015-01-01','{MARCA_HISTORIA}-1205',TRUE,CURRENT_DATE);")
        hilo, _ = self._lanzar_atacante(sql)
        # La sonda no puede ser un FOR UPDATE sobre una fila que todavia no
        # existe: se espera a que el INSERT del atacante este puesto mirando
        # que un INSERT igual se bloquee. Se usa el propio intento como sonda.
        time.sleep(0.4)

        error = self._llamar_procedimiento(
            'CALL p_alta_paciente(:nom,:ape,:fn,NULL,:hist,NULL,@id,@msg)',
            {'nom': 'Proto', 'ape': 'Timeout', 'fn': '2015-01-01',
             'hist': f'{MARCA_HISTORIA}-1205'}, timeout_corto=True)

        hilo.join(timeout=30)
        self._afirmar_errno(error, ERRNO_LOCK_TIMEOUT, 'p_alta_paciente (1205)')

    def test_registrar_sesion_propaga_el_1205(self):
        self._poner_timeout_corto()
        sql = self._atacante_que_retiene(
            f'SELECT id FROM terapeutas WHERE id={TERAPEUTA} FOR UPDATE;')
        hilo, _ = self._lanzar_atacante(sql)
        self.assertTrue(self._esperar_a_que_el_atacante_tenga_el_lock(
            f'SELECT id FROM terapeutas WHERE id={TERAPEUTA} FOR UPDATE NOWAIT'))

        error = self._llamar_procedimiento(
            'CALL p_registrar_sesion(:ter,:pac,:fecha,:hi,:hf,:est,:notas,@id,@msg)',
            {'ter': TERAPEUTA, 'pac': 1, 'fecha': FECHA_SESION_LIBRE,
             'hi': '10:00:00', 'hf': '11:00:00', 'est': 'completa',
             'notas': MARCA_NOTAS}, timeout_corto=True)

        hilo.join(timeout=30)
        self._afirmar_errno(error, ERRNO_LOCK_TIMEOUT, 'p_registrar_sesion (1205)')

    def test_registrar_evolucion_propaga_el_1205(self):
        self._poner_timeout_corto()
        sql = self._atacante_que_retiene(
            f'SELECT id FROM sesiones WHERE id={SESION} FOR UPDATE;')
        hilo, _ = self._lanzar_atacante(sql)
        self.assertTrue(self._esperar_a_que_el_atacante_tenga_el_lock(
            f'SELECT id FROM sesiones WHERE id={SESION} FOR UPDATE NOWAIT'))

        error = self._llamar_procedimiento(
            'CALL p_registrar_evolucion(:ses,:obj,:val,NULL,:ter,@id,@msg)',
            {'ses': SESION, 'obj': OBJETIVO, 'val': 3, 'ter': TERAPEUTA},
            timeout_corto=True)

        hilo.join(timeout=30)
        self._afirmar_errno(error, ERRNO_LOCK_TIMEOUT, 'p_registrar_evolucion (1205)')


# =====================================================================
# CAPA 2 — el decorador reintenta y la operacion se completa
# =====================================================================
class TestElDecoradorReintenta(BaseDeadlock):

    def _afirmar_reintento(self, nombre_funcion):
        reintentos = self.captura.reintentos_de(nombre_funcion)
        self.assertGreaterEqual(
            len(reintentos), 1,
            f'Hubo un error reintentable pero @reintentar_en_deadlock no registro '
            f'ningun reintento en {nombre_funcion}: la operacion termino bien por '
            f'otro motivo. Registros: {self.captura.mensajes()}')

    def _contar(self, sentencia, parametros):
        with self.app.app_context():
            valor = db.session.execute(text(sentencia), parametros).scalar()
            db.session.rollback()
            return valor

    # --- camino ORM (el unico que funcionaba antes del arreglo) -----------

    def test_objetivos_orm_deadlock_dispara_el_reintento(self):
        sql = self._atacante_de_deadlock(
            f'SELECT id FROM objetivos_terapeuticos WHERE id_paciente={PACIENTE_ORM} FOR UPDATE;',
            f'SELECT id FROM pacientes WHERE id={PACIENTE_ORM} FOR UPDATE;')
        antes = self._contador_de_deadlocks()
        hilo, _ = self._lanzar_atacante(sql)
        self.assertTrue(self._esperar_a_que_el_atacante_tenga_el_lock(
            f'SELECT id FROM objetivos_terapeuticos WHERE id_paciente={PACIENTE_ORM} '
            'FOR UPDATE NOWAIT'))

        with self.app.app_context():
            objetivo = crear_objetivo({'id_paciente': PACIENTE_ORM,
                                       'descripcion': f'{MARCA_OBJETIVO} orm'})
            self.assertIsNotNone(objetivo.id)

        hilo.join(timeout=30)
        self.assertGreaterEqual(self._contador_de_deadlocks() - antes, 1)
        self._afirmar_reintento('crear_objetivo')
        self.assertEqual(
            self._contar('SELECT COUNT(*) FROM objetivos_terapeuticos '
                         'WHERE descripcion LIKE :m', {'m': MARCA_OBJETIVO + '%'}), 1,
            'Se esperaba exactamente 1 objetivo: si hay 2, el reintento repitio '
            'una operacion que ya habia quedado escrita.')

    # --- alta_paciente ----------------------------------------------------

    def test_alta_paciente_deadlock_dispara_el_reintento(self):
        sql = self._atacante_de_deadlock(
            f'SELECT id FROM usuarios WHERE id={USUARIO_LIBRE} FOR UPDATE;',
            'INSERT INTO pacientes (id_usuario,nombre,apellido,fecha_nacimiento,'
            f"nro_historia,activo,fecha_alta) VALUES (NULL,'Choque','Test',"
            f"'2015-01-01','{MARCA_HISTORIA}-A',TRUE,CURRENT_DATE);",
            cierre='ROLLBACK;')
        antes = self._contador_de_deadlocks()
        hilo, _ = self._lanzar_atacante(sql)
        self.assertTrue(self._esperar_a_que_el_atacante_tenga_el_lock(
            f'SELECT id FROM usuarios WHERE id={USUARIO_LIBRE} FOR UPDATE NOWAIT'))

        with self.app.app_context():
            paciente, mensaje = alta_paciente({
                'nombre': 'Proto', 'apellido': 'Deadlock',
                'fecha_nacimiento': '2015-01-01',
                'nro_historia': f'{MARCA_HISTORIA}-A',
                'id_usuario': USUARIO_LIBRE,
            })
            self.assertIsNotNone(paciente.id, mensaje)

        hilo.join(timeout=30)
        self.assertGreaterEqual(self._contador_de_deadlocks() - antes, 1)
        self._afirmar_reintento('alta_paciente')
        self.assertEqual(
            self._contar('SELECT COUNT(*) FROM pacientes WHERE nro_historia = :h',
                         {'h': f'{MARCA_HISTORIA}-A'}), 1)

    def test_alta_paciente_lock_timeout_dispara_el_reintento(self):
        self._poner_timeout_corto()
        sql = self._atacante_que_retiene(
            'INSERT INTO pacientes (id_usuario,nombre,apellido,fecha_nacimiento,'
            f"nro_historia,activo,fecha_alta) VALUES (NULL,'Retencion','Test',"
            f"'2015-01-01','{MARCA_HISTORIA}-B',TRUE,CURRENT_DATE);")
        hilo, _ = self._lanzar_atacante(sql)
        time.sleep(0.4)

        with self.app.app_context():
            paciente, mensaje = alta_paciente({
                'nombre': 'Proto', 'apellido': 'Timeout',
                'fecha_nacimiento': '2015-01-01',
                'nro_historia': f'{MARCA_HISTORIA}-B',
            })
            self.assertIsNotNone(paciente.id, mensaje)

        hilo.join(timeout=30)
        self._afirmar_reintento('alta_paciente')

    # --- registrar_sesion (por HTTP: el servicio usa el terapeuta logueado)

    def test_registrar_sesion_deadlock_dispara_el_reintento(self):
        sql = self._atacante_de_deadlock(
            f'SELECT id FROM sesiones WHERE id_terapeuta={TERAPEUTA} FOR UPDATE;',
            f'SELECT id FROM terapeutas WHERE id={TERAPEUTA} FOR UPDATE;')
        antes = self._contador_de_deadlocks()
        hilo, _ = self._lanzar_atacante(sql)
        self.assertTrue(self._esperar_a_que_el_atacante_tenga_el_lock(
            f'SELECT id FROM sesiones WHERE id_terapeuta={TERAPEUTA} FOR UPDATE NOWAIT'))

        respuesta = e.cliente().post(
            '/api/sesiones', headers=e.encabezado_auth(self.tok_laura),
            json={'id_paciente': 1, 'fecha': FECHA_SESION_LIBRE,
                  'hora_inicio': '08:00:00', 'hora_fin': '09:00:00',
                  'estado': 'completa', 'notas': MARCA_NOTAS})

        hilo.join(timeout=30)
        self.assertEqual(respuesta.status_code, 201, respuesta.get_json())
        self.assertGreaterEqual(self._contador_de_deadlocks() - antes, 1)
        self._afirmar_reintento('registrar_sesion')
        self.assertEqual(
            self._contar('SELECT COUNT(*) FROM sesiones WHERE notas LIKE :m',
                         {'m': MARCA_NOTAS + '%'}), 1)

    def test_registrar_sesion_lock_timeout_dispara_el_reintento(self):
        self._poner_timeout_corto()
        sql = self._atacante_que_retiene(
            f'SELECT id FROM terapeutas WHERE id={TERAPEUTA} FOR UPDATE;')
        hilo, _ = self._lanzar_atacante(sql)
        self.assertTrue(self._esperar_a_que_el_atacante_tenga_el_lock(
            f'SELECT id FROM terapeutas WHERE id={TERAPEUTA} FOR UPDATE NOWAIT'))

        respuesta = e.cliente().post(
            '/api/sesiones', headers=e.encabezado_auth(self.tok_laura),
            json={'id_paciente': 1, 'fecha': FECHA_SESION_LIBRE,
                  'hora_inicio': '10:00:00', 'hora_fin': '11:00:00',
                  'estado': 'completa', 'notas': MARCA_NOTAS})

        hilo.join(timeout=30)
        self.assertEqual(respuesta.status_code, 201, respuesta.get_json())
        self._afirmar_reintento('registrar_sesion')

    # --- registrar_evolucion: EL cierre de la decision 12 -----------------

    def test_registrar_evolucion_deadlock_dispara_el_reintento(self):
        """
        El escenario exacto de la decision 12: sesiones <-> objetivos via el
        trigger de evoluciones. Es el unico deadlock que el proyecto tenia
        documentado y reproducible, y hasta el arreglo de Terminal 1 era
        indemostrable: el procedimiento se lo tragaba y el decorador no veia
        nada. Este test es el cierre real de esa decision.
        """
        sql = self._atacante_de_deadlock(
            f'SELECT id FROM objetivos_terapeuticos WHERE id={OBJETIVO} FOR UPDATE;',
            f'SELECT id FROM sesiones WHERE id={SESION} FOR UPDATE;')
        antes = self._contador_de_deadlocks()
        hilo, _ = self._lanzar_atacante(sql)
        self.assertTrue(self._esperar_a_que_el_atacante_tenga_el_lock(
            f'SELECT id FROM objetivos_terapeuticos WHERE id={OBJETIVO} FOR UPDATE NOWAIT'))

        respuesta = e.cliente().post(
            '/api/evoluciones', headers=e.encabezado_auth(self.tok_laura),
            json={'id_sesion': SESION, 'id_objetivo': OBJETIVO, 'valor': 3})

        hilo.join(timeout=30)
        self.assertEqual(respuesta.status_code, 201, respuesta.get_json())
        self.assertGreaterEqual(
            self._contador_de_deadlocks() - antes, 1,
            'El contador lock_deadlocks no se movio: no hubo deadlock y este test '
            'no esta observando lo que dice observar.')
        self._afirmar_reintento('registrar_evolucion')
        self.assertEqual(
            self._contar('SELECT COUNT(*) FROM evoluciones '
                         'WHERE id_sesion = :s AND id_objetivo = :o',
                         {'s': SESION, 'o': OBJETIVO}), 1,
            'Se esperaba exactamente 1 evolucion: si hay 2, el reintento repitio '
            'una operacion ya escrita.')

    def test_registrar_evolucion_lock_timeout_dispara_el_reintento(self):
        self._poner_timeout_corto()
        sql = self._atacante_que_retiene(
            f'SELECT id FROM sesiones WHERE id={SESION} FOR UPDATE;')
        hilo, _ = self._lanzar_atacante(sql)
        self.assertTrue(self._esperar_a_que_el_atacante_tenga_el_lock(
            f'SELECT id FROM sesiones WHERE id={SESION} FOR UPDATE NOWAIT'))

        respuesta = e.cliente().post(
            '/api/evoluciones', headers=e.encabezado_auth(self.tok_laura),
            json={'id_sesion': SESION, 'id_objetivo': OBJETIVO, 'valor': 3})

        hilo.join(timeout=30)
        self.assertEqual(respuesta.status_code, 201, respuesta.get_json())
        self._afirmar_reintento('registrar_evolucion')
        self.assertEqual(
            self._contar('SELECT COUNT(*) FROM evoluciones '
                         'WHERE id_sesion = :s AND id_objetivo = :o',
                         {'s': SESION, 'o': OBJETIVO}), 1)


# =====================================================================
# CAPA 3 — el control que impide que todo lo de arriba mienta
# =====================================================================
class TestControlSinDecorador(BaseDeadlock):
    """
    Sin este control, la capa 2 podria estar pasando por casualidad.

    Corre el mismo ataque contra la funcion SIN decorar (__wrapped__, que
    expone functools.wraps) y afirma que ahi si estalla con 1213 y no queda
    nada escrito. Reemplaza al ejercicio manual de desactivar el decorador:
    si alguien lo neutraliza, la capa 2 se cae; si el escenario deja de
    producir deadlocks, se cae este.
    """

    def test_sin_decorador_el_mismo_ataque_propaga_el_1213(self):
        sin_decorar = getattr(crear_objetivo, '__wrapped__', None)
        self.assertIsNotNone(
            sin_decorar, 'crear_objetivo no expone __wrapped__.')

        sql = self._atacante_de_deadlock(
            f'SELECT id FROM objetivos_terapeuticos WHERE id_paciente={PACIENTE_ORM} FOR UPDATE;',
            f'SELECT id FROM pacientes WHERE id={PACIENTE_ORM} FOR UPDATE;')
        hilo, _ = self._lanzar_atacante(sql)
        self.assertTrue(self._esperar_a_que_el_atacante_tenga_el_lock(
            f'SELECT id FROM objetivos_terapeuticos WHERE id_paciente={PACIENTE_ORM} '
            'FOR UPDATE NOWAIT'))

        error = None
        with self.app.app_context():
            try:
                sin_decorar({'id_paciente': PACIENTE_ORM,
                             'descripcion': f'{MARCA_OBJETIVO} sin decorador'})
            except (OperationalError, DBAPIError) as capturado:
                error = capturado
            finally:
                db.session.rollback()

        hilo.join(timeout=30)
        self._afirmar_errno(error, ERRNO_DEADLOCK, 'crear_objetivo sin decorador')

        with self.app.app_context():
            filas = db.session.execute(text(
                'SELECT COUNT(*) FROM objetivos_terapeuticos WHERE descripcion LIKE :m'),
                {'m': MARCA_OBJETIVO + '%'}).scalar()
            db.session.rollback()
        self.assertEqual(filas, 0,
                         'La transaccion abortada por deadlock dejo filas escritas.')


if __name__ == '__main__':
    unittest.main(verbosity=2)

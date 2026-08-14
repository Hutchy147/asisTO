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
dos con ROLLBACK + RESIGNAL (commits ff65741 y 534830f).

Este archivo verifica ese arreglo por cuenta propia y prueba el reintento
en los cuatro caminos.

QUE SE AFIRMA, Y POR QUE NO ALCANZA CON MENOS. En cada caso decorado se
verifican TRES cosas juntas; si falta cualquiera, el resto no significa
nada:

  1. hubo un error reintentable REAL   -> capa 1: el mismo escenario contra
                                          el procedimiento pelado devuelve
                                          errno 1213 / 1205 al cliente
  2. el decorador REINTENTO            -> su propio logger emitio el WARNING
  3. y despues:
     - deadlock (1213): la operacion se COMPLETA, y deja UNA fila, no dos
     - lock timeout (1205): la operacion AGOTA los tres intentos y el error
       que sobrevive es el 1205, traducido a su mensaje propio

Los dos finales del punto 3 son distintos a proposito: el final "se
completa" para el 1205 exigiria que el atacante soltara dentro de una
ventana estrecha, y esa ventana no resulto reproducible. El final "se
agota" no depende de ninguna ventana -- el atacante no suelta hasta que el
test se lo dice.

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

Bajar ese valor cuesta mas de lo que parece. Un SET SESSION suelto desde el
test no sirve para nada que entre por HTTP: la conexion que atiende el
request sale del pool y no es la del test. Y un listener de 'connect' en el
engine tampoco alcanza solo, porque cubre unicamente las conexiones que
nacen despues del dispose(). Con eso, dos tests de 1205 quedaron
INTERMITENTES: a veces al request le tocaba una conexion anterior, la
victima esperaba los 50 s por defecto, el atacante soltaba antes y la
operacion salia bien SIN reintentar.

Lo que si es determinista, y es lo que hace este archivo, son las tres
cosas juntas: GLOBAL por el cliente privilegiado, vaciado del pool
(session.remove() + dispose()) y el listener; mas una PRECONDICION que
comprueba el timeout efectivo antes de atacar y falla con un mensaje claro
si no quedo puesto. En la capa 1, ademas, se fija en la misma sesion del
CALL, que ahi si es alcanzable.

LA SINCRONIZACION VA EN LOS DOS SENTIDOS, y las dos mitades costaron una
corrida en rojo cada una:

  DE IDA -- ¿ya tiene el atacante el recurso? Se comprueba, no se supone:
  una sonda SELECT ... FOR UPDATE NOWAIT que solo cuenta como "listo" si
  falla con 3572 o 1205. Donde el atacante retiene un INSERT sin confirmar
  la fila todavia no existe y no se puede sondear asi, asi que ahi se mira
  innodb_trx hasta ver su transaccion con filas ya modificadas. Antes habia
  un sleep de 0,4 s y arrancar el proceso mysql tarda mas que eso con la
  maquina cargada.

  DE VUELTA -- ¿cuanto retiene? Hasta que el test se lo avisa, con un lock
  de usuario de MySQL que hace de pestillo. No hay sleep, asi que no hay
  margen que calcular ni constante que ajustar.

Las dos se detectaron corriendo el test, no leyendolo.

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

# NO hay constante de retencion para los casos de 1205, y es a proposito:
# el atacante retiene hasta que el test se lo avisa. Ver _atacante_que_retiene
# y _tomar_pestillo / _soltar_pestillo.
#
# La hubo, y fue una carrera. La victima necesita ~3,15 s continuos para
# agotar sus tres intentos (3 x 1 s + backoff), pero la retencion empezaba a
# contar cuando el atacante tomaba el lock, y entre eso y el disparo de la
# victima se consumen la sonda y el arranque del request. Con 5 segundos el
# margen quedaba en ~1,8 s y fallaba 1 de cada 2 o 3 corridas, un test
# distinto cada vez. Subir la constante habria hecho el flake mas raro, no
# lo habria eliminado, y un flake raro es peor: aparece cuando ya nadie
# sospecha del test.

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
        self._timeout_global_anterior = 50
        self._conexion_pestillo = None

    def tearDown(self):
        self.logger_decorador.removeHandler(self.captura)
        # Primero el pestillo: si un test se cayo antes de soltarlo, el
        # atacante sigue esperando y la limpieza se quedaria bloqueada
        # contra sus locks de fila.
        self._soltar_pestillo()
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
        """
        Retiene el recurso HASTA QUE SE LE AVISA. No hay sleep.

        No pide un segundo recurso, asi que no puede formarse un ciclo: lo
        que provoca es espera pura, que termina en 1205.

        POR QUE NO ES UN SLEEP. Lo era, y era una carrera: la retencion
        arrancaba cuando el atacante tomaba el lock, pero entre ese momento y
        el disparo de la victima se consumen la sonda y el arranque del
        request, y la victima necesita ~3,15 s continuos para agotar sus tres
        intentos. Con 5 segundos el margen quedaba en ~1,8 s y fallaba 1 de
        cada 2 o 3 corridas, siempre un test distinto.

        Subir la constante no elimina la carrera, la vuelve rara -- y un
        flake raro es peor que uno frecuente, porque aparece cuando ya nadie
        sospecha del test. Este proyecto ya tuvo cuatro tests que pasaban sin
        probar nada; no hacen falta mas.

        El pestillo es un lock de usuario de MySQL: el test lo toma ANTES de
        lanzar al atacante, el atacante se queda esperandolo con su
        transaccion abierta, y lo suelta el test cuando ya midio lo que
        queria. Sin tiempo fijo no hay margen que calcular.

        Es la sincronizacion de vuelta; la de ida ya la resolvia la sonda
        NOWAIT.
        """
        return (
            'START TRANSACTION;\n'
            f'{recurso}\n'
            # Si el test muere sin soltar, esto corta solo y la transaccion
            # se revierte: nunca queda un atacante colgado para siempre.
            f"SELECT GET_LOCK('{self._nombre_pestillo()}', 60);\n"
            'ROLLBACK;\n'
        )

    # --- el pestillo: retener hasta que se avise --------------------------

    def _nombre_pestillo(self):
        """
        Los locks de usuario de MySQL son GLOBALES del servidor, no de la
        base. Se namespacea con el nombre de la base para que dos terminales
        corriendo esta misma suite no se suelten el pestillo entre si.
        """
        return f'asisto_retencion_{self.db_name}'

    def _tomar_pestillo(self):
        """Toma el pestillo en una conexion DEDICADA del test."""
        # Dedicada y no db.session: la sesion devuelve su conexion al pool
        # entre operaciones, y el lock de usuario vive en la CONEXION. Si la
        # conexion vuelve al pool y se recicla, el pestillo se suelta solo y
        # volvemos a tener una carrera, esta vez invisible.
        with self.app.app_context():
            self._conexion_pestillo = db.engine.raw_connection()
        cursor = self._conexion_pestillo.cursor()
        cursor.execute("SELECT GET_LOCK(%s, 5)", (self._nombre_pestillo(),))
        obtenido = cursor.fetchone()[0]
        cursor.close()
        self.assertEqual(
            obtenido, 1,
            f'No se pudo tomar el pestillo {self._nombre_pestillo()!r}. Si lo '
            'tiene otra corrida, este test no puede garantizar la retencion.')

    def _soltar_pestillo(self):
        """Suelta el pestillo: el atacante se despierta y hace ROLLBACK."""
        if not getattr(self, '_conexion_pestillo', None):
            return
        try:
            cursor = self._conexion_pestillo.cursor()
            cursor.execute("SELECT RELEASE_LOCK(%s)", (self._nombre_pestillo(),))
            cursor.fetchone()
            cursor.close()
        finally:
            # Cerrar la conexion suelta el lock igual, asi que ni un fallo a
            # mitad de camino deja al atacante esperando.
            self._conexion_pestillo.close()
            self._conexion_pestillo = None

    def _esperar_a_que_el_atacante_tenga_el_lock(self, sonda, timeout=25):
        """
        No duerme un rato fijo: comprueba. Mientras el atacante retenga el
        recurso, la sonda NOWAIT falla con 3572. Disparar la victima antes de
        eso es una de las formas de que no se forme nada y el test de verde.
        """
        inicio = time.time()
        ultimo_errno = None
        with self.app.app_context():
            while time.time() - inicio < timeout:
                try:
                    db.session.execute(text(sonda))
                    db.session.rollback()
                    time.sleep(0.15)
                except (OperationalError, DBAPIError) as error:
                    db.session.rollback()
                    ultimo_errno = obtener_errno(error)
                    # SOLO estos dos significan "hay alguien reteniendo": 3572
                    # es el rechazo inmediato de NOWAIT y 1205 el timeout.
                    #
                    # Antes esto devolvia True ante CUALQUIER error, y eso hizo
                    # intermitentes a los tests de 1205: justo antes de sondear
                    # se vacia el pool, y la primera consulta contra una
                    # conexion recien cerrada falla por motivos que no tienen
                    # nada que ver con el lock. La sonda lo leia como "listo",
                    # la victima salia sin contencion y no expiraba nada.
                    if ultimo_errno in (3572, ERRNO_LOCK_TIMEOUT):
                        return True
                    time.sleep(0.15)
        if ultimo_errno is not None:
            self.fail(
                f'La sonda nunca vio el lock retenido. Ultimo error: '
                f'errno={ultimo_errno}. No es un fallo del codigo bajo prueba: '
                'es que el escenario no se armo.')
        return False

    def _poner_timeout_corto(self):
        """
        innodb_lock_wait_timeout = 1 para todo lo que corra despues.

        Hacen falta LAS TRES COSAS, y cada una tapa un agujero distinto que
        se vio fallar de verdad:

          - GLOBAL, por el cliente privilegiado: es lo unico que alcanza a
            una conexion que el pool cree despues, venga de donde venga.
          - session.remove() + dispose(): vacia el pool, para que ninguna
            conexion vieja (con los 50 s por defecto) sobreviva y le toque
            justo al request.
          - el listener de 'connect': redundante con el GLOBAL a proposito,
            porque si alguien restaura el global a mitad de camino el
            listener sigue cubriendo.

        Con solo el listener, dos tests de 1205 quedaron INTERMITENTES: a
        veces al request le tocaba una conexion anterior, la victima esperaba
        los 50 s por defecto, el atacante soltaba antes y la operacion salia
        bien SIN reintentar. Fallaban en rojo, no en falso verde, pero un
        test intermitente no lo cree nadie.
        """
        anterior = self._mysql_privilegiado(
            'SELECT @@GLOBAL.innodb_lock_wait_timeout;')
        lineas = [l for l in anterior.stdout.splitlines() if l.strip()]
        self._timeout_global_anterior = int(lineas[-1]) if len(lineas) >= 2 else 50

        self._mysql_privilegiado(
            f'SET GLOBAL innodb_lock_wait_timeout = {TIMEOUT_DE_LOCK};')

        def al_conectar(conexion_dbapi, _registro):
            cursor = conexion_dbapi.cursor()
            cursor.execute(f'SET SESSION innodb_lock_wait_timeout = {TIMEOUT_DE_LOCK}')
            cursor.close()

        with self.app.app_context():
            motor = db.engine
            db.session.remove()
        event.listen(motor, 'connect', al_conectar)
        motor.dispose()
        self._listener_timeout = (motor, al_conectar)

        # Precondicion explicita: si el timeout NO quedo puesto, este test no
        # puede provocar ningun 1205 y hay que enterarse aca, no por un
        # resultado raro tres pasos despues.
        with self.app.app_context():
            efectivo = db.session.execute(
                text('SELECT @@SESSION.innodb_lock_wait_timeout')).scalar()
            db.session.rollback()
        self.assertEqual(
            efectivo, TIMEOUT_DE_LOCK,
            f'El timeout de lock quedo en {efectivo} y no en {TIMEOUT_DE_LOCK}: '
            'la victima no va a expirar y el test no probaria nada.')

    def _quitar_timeout_corto(self):
        if not self._listener_timeout:
            return
        motor, funcion = self._listener_timeout
        event.remove(motor, 'connect', funcion)
        self._mysql_privilegiado(
            f'SET GLOBAL innodb_lock_wait_timeout = {self._timeout_global_anterior};')
        with self.app.app_context():
            db.session.remove()
        motor.dispose()
        self._listener_timeout = None

    def _esperar_transaccion_del_atacante(self, timeout=25):
        """
        Espera a que el atacante tenga una transaccion ABIERTA con filas ya
        modificadas.

        Es la sonda para los casos donde no se puede usar FOR UPDATE NOWAIT
        porque la fila todavia no existe (el atacante retiene un INSERT sin
        confirmar). Antes habia un sleep fijo de 0.4 s, y arrancar el proceso
        mysql tarda mas que eso cuando la maquina esta cargada: la victima
        salia sin contencion ninguna y el test fallaba de manera
        intermitente.
        """
        inicio = time.time()
        while time.time() - inicio < timeout:
            proceso = self._mysql_privilegiado(
                'SELECT COUNT(*) FROM information_schema.innodb_trx '
                'WHERE trx_rows_modified >= 1;')
            lineas = [l for l in proceso.stdout.splitlines() if l.strip()]
            if len(lineas) >= 2 and int(lineas[-1]) >= 1:
                return True
            time.sleep(0.1)
        return False

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
        self._tomar_pestillo()
        sql = self._atacante_que_retiene(
            'INSERT INTO pacientes (id_usuario,nombre,apellido,fecha_nacimiento,'
            f"nro_historia,activo,fecha_alta) VALUES (NULL,'Retencion','Test',"
            f"'2015-01-01','{MARCA_HISTORIA}-1205',TRUE,CURRENT_DATE);")
        hilo, _ = self._lanzar_atacante(sql)
        self.assertTrue(
            self._esperar_transaccion_del_atacante(),
            'El atacante nunca llego a tener su INSERT sin confirmar.')

        error = self._llamar_procedimiento(
            'CALL p_alta_paciente(:nom,:ape,:fn,NULL,:hist,NULL,@id,@msg)',
            {'nom': 'Proto', 'ape': 'Timeout', 'fn': '2015-01-01',
             'hist': f'{MARCA_HISTORIA}-1205'}, timeout_corto=True)

        self._soltar_pestillo()
        hilo.join(timeout=30)
        self._afirmar_errno(error, ERRNO_LOCK_TIMEOUT, 'p_alta_paciente (1205)')

    def test_registrar_sesion_propaga_el_1205(self):
        self._poner_timeout_corto()
        self._tomar_pestillo()
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

        self._soltar_pestillo()
        hilo.join(timeout=30)
        self._afirmar_errno(error, ERRNO_LOCK_TIMEOUT, 'p_registrar_sesion (1205)')

    def test_registrar_evolucion_propaga_el_1205(self):
        self._poner_timeout_corto()
        self._tomar_pestillo()
        sql = self._atacante_que_retiene(
            f'SELECT id FROM sesiones WHERE id={SESION} FOR UPDATE;')
        hilo, _ = self._lanzar_atacante(sql)
        self.assertTrue(self._esperar_a_que_el_atacante_tenga_el_lock(
            f'SELECT id FROM sesiones WHERE id={SESION} FOR UPDATE NOWAIT'))

        error = self._llamar_procedimiento(
            'CALL p_registrar_evolucion(:ses,:obj,:val,NULL,:ter,@id,@msg)',
            {'ses': SESION, 'obj': OBJETIVO, 'val': 3, 'ter': TERAPEUTA},
            timeout_corto=True)

        self._soltar_pestillo()
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

    def _afirmar_agotamiento(self, nombre_funcion, error):
        """
        El atacante no suelta: la victima agota los tres intentos.

        Se afirman las dos mitades. Que el decorador REINTENTO -- dos WARNING,
        de los intentos 1 y 2, porque en el tercero ya no reintenta -- y que lo
        que sobrevive es el 1205 y no otra cosa. Sin la segunda mitad,
        cualquier error repetido tres veces daria el mismo conteo de log.
        """
        reintentos = self.captura.reintentos_de(nombre_funcion)
        self.assertEqual(
            len(reintentos), 2,
            f'Se esperaban 2 reintentos antes de agotarse en {nombre_funcion} y '
            f'hubo {len(reintentos)}. Registros: {self.captura.mensajes()}')
        self.assertIsNotNone(
            error,
            f'{nombre_funcion}: con el atacante reteniendo durante todo el '
            'ataque, la operacion tenia que agotar los reintentos y fallar.')
        self.assertEqual(
            obtener_errno(error), ERRNO_LOCK_TIMEOUT,
            f'{nombre_funcion}: sobrevivio un error con errno '
            f'{obtener_errno(error)} en vez de {ERRNO_LOCK_TIMEOUT}.')

    def _afirmar_agotamiento_http(self, nombre_funcion, respuesta):
        """Lo mismo, para los caminos que entran por HTTP."""
        reintentos = self.captura.reintentos_de(nombre_funcion)
        self.assertEqual(
            len(reintentos), 2,
            f'Se esperaban 2 reintentos antes de agotarse en {nombre_funcion} y '
            f'hubo {len(reintentos)}. Registros: {self.captura.mensajes()}')
        cuerpo = respuesta.get_json() or {}
        self.assertEqual(
            respuesta.status_code, 400,
            'Se esperaba que la operacion fallara tras agotar los reintentos. '
            f'Llego {respuesta.status_code}: {cuerpo}')
        # El texto importa: es la traduccion PROPIA del 1205 de errors.py, y
        # es distinta de la del 1213. Afirmarla es lo que confirma que el
        # error que sobrevivio fue el lock wait timeout y no otro.
        self.assertEqual(cuerpo.get('codigo'), 'error_base_de_datos', cuerpo)
        self.assertIn(
            'tardo demasiado en obtener acceso', cuerpo.get('mensaje', ''),
            'El 1205 agotado tiene que llegar con su mensaje traducido, y '
            f'llego: {cuerpo}')

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
        self._tomar_pestillo()
        sql = self._atacante_que_retiene(
            'INSERT INTO pacientes (id_usuario,nombre,apellido,fecha_nacimiento,'
            f"nro_historia,activo,fecha_alta) VALUES (NULL,'Retencion','Test',"
            f"'2015-01-01','{MARCA_HISTORIA}-B',TRUE,CURRENT_DATE);")
        hilo, _ = self._lanzar_atacante(sql)
        self.assertTrue(
            self._esperar_transaccion_del_atacante(),
            'El atacante nunca llego a tener su INSERT sin confirmar.')

        error = None
        with self.app.app_context():
            try:
                alta_paciente({
                    'nombre': 'Proto', 'apellido': 'Timeout',
                    'fecha_nacimiento': '2015-01-01',
                    'nro_historia': f'{MARCA_HISTORIA}-B',
                })
            except (OperationalError, DBAPIError) as capturado:
                error = capturado
            finally:
                db.session.rollback()

        self._soltar_pestillo()
        hilo.join(timeout=30)
        self._afirmar_agotamiento('alta_paciente', error)

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
        self._tomar_pestillo()
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

        self._soltar_pestillo()
        hilo.join(timeout=30)
        self._afirmar_agotamiento_http('registrar_sesion', respuesta)

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
        self._tomar_pestillo()
        sql = self._atacante_que_retiene(
            f'SELECT id FROM sesiones WHERE id={SESION} FOR UPDATE;')
        hilo, _ = self._lanzar_atacante(sql)
        self.assertTrue(self._esperar_a_que_el_atacante_tenga_el_lock(
            f'SELECT id FROM sesiones WHERE id={SESION} FOR UPDATE NOWAIT'))

        respuesta = e.cliente().post(
            '/api/evoluciones', headers=e.encabezado_auth(self.tok_laura),
            json={'id_sesion': SESION, 'id_objetivo': OBJETIVO, 'valor': 3})

        self._soltar_pestillo()
        hilo.join(timeout=30)
        self._afirmar_agotamiento_http('registrar_evolucion', respuesta)
        self.assertEqual(
            self._contar('SELECT COUNT(*) FROM evoluciones '
                         'WHERE id_sesion = :s AND id_objetivo = :o',
                         {'s': SESION, 'o': OBJETIVO}), 0,
            'El intento agotado no debe dejar ninguna evolucion escrita.')


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


class TestBajaConUpdateDirectoDeSesion(BaseDeadlock):
    """
    Vigila la premisa de la NOTA PARA LA ENTREGA 4 de schema.sql.

    Esa nota decide poner el chequeo de baja en los DOS triggers de sesiones
    sabiendo que en el de UPDATE el orden de locks queda invertido
    (sesiones -> pacientes), y lo justifica con una medicion: que un UPDATE
    directo concurrente con una baja produce un 1213 y que la baja lo absorbe
    con un reintento. Si esa interaccion cambia, la justificacion de la
    decision cambia con ella, y hasta hoy no habia nada que la mirara.

    LA GUARDA CONTRA EL BANCO SUCIO ES LA MITAD DEL TEST. El escenario tiene
    una forma de "salir bien" sin haber probado nada: si el paciente ya
    estaba dado de baja de una corrida anterior, la baja contesta "ya estaba
    dado de baja" en el primer IF, no toma ningun lock, no se cruza con
    nadie y termina en cero reintentos y cero deadlocks -- que es justo el
    resultado que uno quiere ver. Por eso el paciente se crea en cada setUp y
    se afirma su estado ANTES del ataque, y por eso se exige que la baja haya
    arrastrado el objetivo: un resultado mejor de lo esperado es lo primero
    que hay que desconfiar.
    """

    def setUp(self):
        super().setUp()
        with self.app.app_context():
            db.session.execute(text(
                'INSERT INTO pacientes (id_usuario,nombre,apellido,fecha_nacimiento,'
                'nro_historia,activo,fecha_alta) '
                "VALUES (NULL,'Baja','UpdateDirecto','2015-01-01',:hc,TRUE,CURRENT_DATE)"),
                {'hc': f'{MARCA_HISTORIA}-BAJA'})
            self.id_paciente = db.session.execute(
                text('SELECT LAST_INSERT_ID()')).scalar()
            db.session.execute(text(
                'INSERT INTO objetivos_terapeuticos (id_paciente,descripcion,activo) '
                'VALUES (:p,:d,TRUE)'),
                {'p': self.id_paciente, 'd': f'{MARCA_OBJETIVO} de la baja'})
            self.id_objetivo_activo = db.session.execute(
                text('SELECT LAST_INSERT_ID()')).scalar()
            # Uno archivado: es lo que el atacante desarchiva para pedir
            # `pacientes` en exclusiva y cerrar el ciclo. Ver el test del 1213.
            db.session.execute(text(
                'INSERT INTO objetivos_terapeuticos (id_paciente,descripcion,activo) '
                'VALUES (:p,:d,FALSE)'),
                {'p': self.id_paciente, 'd': f'{MARCA_OBJETIVO} archivado de la baja'})
            self.id_objetivo_archivado = db.session.execute(
                text('SELECT LAST_INSERT_ID()')).scalar()
            db.session.execute(text(
                'INSERT INTO sesiones (id_terapeuta,id_paciente,fecha,hora_inicio,'
                'hora_fin,estado,notas) '
                "VALUES (:t,:p,'2026-06-02','15:00:00','16:00:00','completa',:n)"),
                {'t': TERAPEUTA, 'p': self.id_paciente, 'n': f'{MARCA_NOTAS} de la baja'})
            self.id_sesion = db.session.execute(
                text('SELECT LAST_INSERT_ID()')).scalar()
            db.session.commit()

    def _estado_del_paciente(self):
        with self.app.app_context():
            fila = db.session.execute(text(
                'SELECT activo, (SELECT COUNT(*) FROM objetivos_terapeuticos '
                ' WHERE id_paciente = p.id AND activo = TRUE) '
                'FROM pacientes p WHERE p.id = :p'),
                {'p': self.id_paciente}).first()
            db.session.rollback()
            return (bool(fila[0]), int(fila[1]))

    def test_la_baja_sobrevive_a_un_update_directo_sobre_sus_sesiones(self):
        from app.services.pacientes_service import baja_paciente

        # --- guarda 1: el escenario arranca donde tiene que arrancar -----
        activo, objetivos_activos = self._estado_del_paciente()
        self.assertTrue(activo,
                        'El paciente de este test tiene que arrancar ACTIVO. Si no lo '
                        'esta, la baja sale por el primer IF sin tomar ningun lock y '
                        'el resultado no significa nada.')
        self.assertEqual(objetivos_activos, 1,
                         'El paciente tiene que arrancar con 1 objetivo activo: es lo '
                         'que despues prueba que la baja hizo su trabajo de verdad.')

        atacante = (
            'START TRANSACTION;\n'
            f'INSERT INTO auditoria_accesos (id_usuario,email,resultado) VALUES {self._lastre()};\n'
            f"UPDATE sesiones SET notas='{MARCA_NOTAS} tocada por el atacante' "
            f'WHERE id={self.id_sesion};\n'
            f'SELECT SLEEP({SEGUNDOS_DE_RETENCION});\n'
            'COMMIT;\n'
        )
        antes = self._contador_de_deadlocks()
        hilo, _ = self._lanzar_atacante(atacante)

        # --- guarda 2: el atacante retiene de verdad antes de disparar ---
        self.assertTrue(self._esperar_a_que_el_atacante_tenga_el_lock(
            f'SELECT id FROM sesiones WHERE id={self.id_sesion} FOR UPDATE NOWAIT'))

        arranque = time.time()
        with self.app.app_context():
            paciente, resumen = baja_paciente(self.id_paciente)
        duracion = time.time() - arranque
        hilo.join(timeout=30)

        # --- lo que importa: la baja quedo bien -------------------------
        self.assertFalse(paciente.activo,
                         'El paciente tenia que quedar dado de baja.')
        self.assertEqual(
            resumen['objetivos_archivados'], 1,
            'La baja tenia que arrastrar el objetivo activo. Si archivo 0, no hizo '
            f'nada y el resto del test no prueba nada: {resumen}')
        activo, objetivos_activos = self._estado_del_paciente()
        self.assertFalse(activo)
        self.assertEqual(objetivos_activos, 0)

        # --- el mecanismo, tal como se mide hoy -------------------------
        #
        # MEDIDO el 2026-08-13, y NO es lo que dice la NOTA del schema. La
        # interaccion real es una ESPERA, no un deadlock: el atacante toma X
        # sobre la fila de sesiones y S sobre la de pacientes (via el trigger),
        # la baja pide X sobre esa misma fila de pacientes y se queda esperando
        # hasta que el atacante confirma. No hay ciclo porque la baja no toca
        # `sesiones` en ningun momento, asi que el atacante nunca necesita algo
        # que la baja tenga.
        #
        # Estas dos aserciones son el canario. Si algun dia dan otra cosa
        # -- porque la baja pase a escribir en sesiones, o porque el trigger
        # cambie -- hay que volver a leer la NOTA antes de tocar nada.
        deadlocks = self._contador_de_deadlocks() - antes
        reintentos = len(self.captura.reintentos_de('baja_paciente'))
        self.assertEqual(
            deadlocks, 0,
            f'Aparecio un deadlock ({deadlocks}) donde hoy hay una espera limpia. '
            'La NOTA PARA LA ENTREGA 4 de schema.sql describe justamente ese '
            'escenario: hay que revisarla con este resultado en la mano. '
            f'Reintentos registrados: {self.captura.mensajes()}')
        self.assertEqual(
            reintentos, 0,
            f'@reintentar_en_deadlock reintento {reintentos} vez/veces la baja. Hoy '
            'no deberia hacer falta ningun reintento porque no hay deadlock: si lo '
            'hubo, cambio la interaccion.')

        # La espera es la evidencia de que se cruzaron: sin contencion la baja
        # tarda decimas. No se afirma un numero exacto -- eso seria medir la
        # maquina -- sino que haya esperado al atacante.
        self.assertGreaterEqual(
            duracion, SEGUNDOS_DE_RETENCION * 0.5,
            f'La baja tardo {duracion:.2f} s: demasiado poco para haber esperado al '
            f'atacante, que retiene {SEGUNDOS_DE_RETENCION} s. Lo mas probable es '
            'que no se hayan cruzado y el escenario no se haya armado.')

    def test_la_baja_recibe_el_1213_y_lo_absorbe_con_un_reintento(self):
        """
        El escenario que SI arma un ciclo con la baja, y que la NOTA del schema
        atribuye al UPDATE de sesiones.

        El ciclo no puede pasar por `sesiones` -- la baja no las toca, asi que
        nunca necesita nada que un UPDATE de sesiones tenga --. Donde si pasa es
        por `objetivos_terapeuticos`, y por una inversion que ya existia antes
        del commit de la regla de baja: los triggers de objetivos toman
        `pacientes FOR UPDATE` DESPUES de la fila de objetivos, cuando la fila
        queda ACTIVA.

            atacante: X sobre un objetivo ACTIVO  ->  quiere pacientes
            baja:     X sobre pacientes           ->  quiere ese objetivo

        EL LASTRE ES LO QUE DECIDE QUIEN MUERE. InnoDB elige como victima a la
        transaccion que menos trabajo hizo. Sin las 200 filas de lastre el
        atacante es mas liviano y el 1213 se lo lleva EL, con lo cual la baja
        termina bien sin haber reintentado nada y el test pasaria sin haber
        probado lo que dice. Con lastre, la victima es la baja, que es el caso
        que hay que vigilar.
        """
        from app.services.pacientes_service import baja_paciente

        activo, objetivos_activos = self._estado_del_paciente()
        self.assertTrue(activo, 'El paciente tiene que arrancar ACTIVO.')
        self.assertEqual(objetivos_activos, 1)

        sql = self._atacante_de_deadlock(
            f'SELECT id FROM objetivos_terapeuticos WHERE id={self.id_objetivo_activo} FOR UPDATE;',
            f'UPDATE objetivos_terapeuticos SET activo=TRUE WHERE id={self.id_objetivo_archivado};')
        antes = self._contador_de_deadlocks()
        hilo, _ = self._lanzar_atacante(sql)
        self.assertTrue(self._esperar_a_que_el_atacante_tenga_el_lock(
            f'SELECT id FROM objetivos_terapeuticos WHERE id={self.id_objetivo_activo} '
            'FOR UPDATE NOWAIT'))

        with self.app.app_context():
            paciente, resumen = baja_paciente(self.id_paciente)
        hilo.join(timeout=30)

        # Las tres cosas juntas, que es lo que distingue este test de uno que
        # pasa sin haber probado nada: hubo un deadlock NUEVO, el decorador
        # REINTENTO, y la baja quedo bien y una sola vez.
        self.assertGreaterEqual(
            self._contador_de_deadlocks() - antes, 1,
            'El contador lock_deadlocks no se movio: no hubo ningun deadlock, asi '
            'que el reintento que se afirma abajo no probaria nada.')
        reintentos = len(self.captura.reintentos_de('baja_paciente'))
        self.assertEqual(
            reintentos, 1,
            f'Se esperaba exactamente 1 reintento de 3 y hubo {reintentos}. Con 0, la '
            'victima del deadlock fue el atacante y no la baja -- el escenario no '
            'probo lo que dice. Registros: {}'.format(self.captura.mensajes()))
        self.assertFalse(paciente.activo)
        # Archiva 2, no 1, y el motivo es parte del escenario: el deadlock mata
        # a la baja, el atacante termina su UPDATE --que DESARCHIVA el segundo
        # objetivo-- y recien entonces corre el reintento, que ya encuentra dos
        # activos. Se afirma >= 1 y no un numero exacto porque lo que importa es
        # que el reintento hizo el trabajo completo sobre el estado que
        # encontro, no cuantas filas habia.
        self.assertGreaterEqual(
            resumen['objetivos_archivados'], 1,
            f'La baja no archivo nada tras el reintento: {resumen}')
        activo, objetivos_activos = self._estado_del_paciente()
        self.assertFalse(activo)
        self.assertEqual(
            objetivos_activos, 0,
            'Quedo un objetivo activo sobre un paciente dado de baja: el reintento '
            'corrio pero dejo la operacion a medias.')


if __name__ == '__main__':
    unittest.main(verbosity=2)

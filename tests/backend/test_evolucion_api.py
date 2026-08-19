"""
tests/backend/test_evolucion_api.py

GET /api/pacientes/<id>/evolucion — la serie que alimenta el grafico de la
ficha (construccion, 2026-08-13).

QUE SE PRUEBA ACA Y QUE EN tests/db. La condicion que decide QUE SERIES
EXISTEN —los objetivos vivos al momento de cada sesion, la trampa de H2— vive
en el procedimiento y se prueba en tests/db/graficos/test_evolucion_series.ps1,
por SQL directo. Aca se prueba lo que solo existe en la capa HTTP: el rango,
el tope de 366 dias, los permisos y la forma del JSON.

EL TOPE TIENE DOS COMPORTAMIENTOS A PROPOSITO, y por eso hay un test para cada
uno. Sin fechas el endpoint devuelve el TRATAMIENTO ENTERO y no paga el tope:
el default esta acotado por la realidad del paciente (su fecha_alta), no por lo
que pida el llamador, y recortarlo dejaria el grafico a medias sin decirlo. Con
fechas explicitas el tope si se aplica, porque ahi el rango lo elige quien
llama. Un solo test no distingue las dos cosas: si alguien "unifica" el camino
y aplica el tope siempre, el test del default es el unico que lo agarra.
"""

import datetime as dt
import unittest

import _entorno as e
from app import db
from sqlalchemy import text

MARCA_HISTORIA = 'HC-TEST-GRAF'
MARCA_INVISIBLE = 'HC-TEST-INVIS'
DIAS_DE_TRATAMIENTO_LARGO = 800     # bastante mas que el tope de 366
MAXIMO_DIAS_RANGO = 366             # el de sesiones_service, replicado aca a
                                    # proposito: si cambia alla, estos tests
                                    # tienen que fallar y avisar, no seguirlo.


class TestEvolucionAPI(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = e.obtener_app()
        cls.laura_id, cls.laura_rol, _ = e.obtener_usuario_por_email(
            e.EMAILS_SEED['terapeuta'])
        cls.tok_laura = e.token_valido(
            cls.laura_id, cls.laura_rol, e.EMAILS_SEED['terapeuta'])
        cls.rrhh_id, cls.rrhh_rol, _ = e.obtener_usuario_por_email(
            e.EMAILS_SEED['rrhh'])
        cls.tok_rrhh = e.token_valido(
            cls.rrhh_id, cls.rrhh_rol, e.EMAILS_SEED['rrhh'])
        cls._limpiar()
        cls._sembrar()

    @classmethod
    def tearDownClass(cls):
        cls._limpiar()

    @classmethod
    def _limpiar(cls):
        with cls.app.app_context():
            for sentencia in (
                'DELETE e FROM evoluciones e JOIN sesiones s ON s.id = e.id_sesion '
                ' JOIN pacientes p ON p.id = s.id_paciente WHERE p.nro_historia LIKE :m',
                'DELETE s FROM sesiones s JOIN pacientes p ON p.id = s.id_paciente '
                ' WHERE p.nro_historia LIKE :m',
                'DELETE o FROM objetivos_terapeuticos o JOIN pacientes p ON p.id = o.id_paciente '
                ' WHERE p.nro_historia LIKE :m',
                'DELETE FROM pacientes WHERE nro_historia LIKE :m',
            ):
                db.session.execute(text(sentencia), {'m': MARCA_HISTORIA + '%'})
            db.session.commit()

    @classmethod
    def _sembrar(cls):
        """
        Un paciente con tratamiento MAS LARGO que el tope.

        Es lo que hace verificable el caso del default: si el paciente tuviera
        tres meses de historia, un endpoint que aplicara el tope siempre daria
        exactamente el mismo resultado que uno que no lo aplica, y el test no
        probaria nada.
        """
        cls.alta = dt.date.today() - dt.timedelta(days=DIAS_DE_TRATAMIENTO_LARGO)
        with cls.app.app_context():
            db.session.execute(text(
                'INSERT INTO pacientes (id_usuario,nombre,apellido,fecha_nacimiento,'
                'nro_historia,activo,fecha_alta) '
                "VALUES (NULL,'Grafico','Largo','2015-01-01',:hc,TRUE,:alta)"),
                {'hc': MARCA_HISTORIA, 'alta': cls.alta})
            cls.id_paciente = db.session.execute(
                text('SELECT LAST_INSERT_ID()')).scalar()
            db.session.execute(text(
                'INSERT INTO objetivos_terapeuticos (id_paciente,descripcion,activo) '
                "VALUES (:p,'GRAF API objetivo unico',TRUE)"),
                {'p': cls.id_paciente})
            db.session.execute(text(
                'UPDATE objetivos_terapeuticos SET fecha_creacion = :f '
                'WHERE id_paciente = :p'),
                {'f': dt.datetime.combine(cls.alta, dt.time(9, 0)), 'p': cls.id_paciente})
            # Una sesion al principio del tratamiento y otra reciente: con el
            # tope aplicado al default, la primera se caeria de la serie.
            db.session.execute(text(
                'INSERT INTO sesiones (id_terapeuta,id_paciente,fecha,hora_inicio,'
                "hora_fin,estado,notas) VALUES (1,:p,:f,'19:00:00','19:45:00','completa','GRAF API vieja')"),
                {'p': cls.id_paciente, 'f': cls.alta + dt.timedelta(days=1)})
            db.session.execute(text(
                'INSERT INTO sesiones (id_terapeuta,id_paciente,fecha,hora_inicio,'
                "hora_fin,estado,notas) VALUES (1,:p,:f,'19:30:00','20:15:00','completa','GRAF API nueva')"),
                {'p': cls.id_paciente, 'f': dt.date.today() - dt.timedelta(days=2)})
            db.session.commit()

    def setUp(self):
        self.cliente = e.cliente()

    def _pedir(self, id_paciente=None, token=None, **parametros):
        ruta = f'/api/pacientes/{self.id_paciente if id_paciente is None else id_paciente}/evolucion'
        if parametros:
            ruta += '?' + '&'.join(f'{k}={v}' for k, v in parametros.items())
        return self.cliente.get(
            ruta, headers=e.encabezado_auth(token or self.tok_laura))

    # --- el tope, por sus dos caminos ----------------------------------

    def test_sin_fechas_devuelve_el_tratamiento_entero_y_no_paga_el_tope(self):
        resp = self._pedir()
        self.assertEqual(resp.status_code, 200, resp.get_json())
        cuerpo = resp.get_json()
        periodo = cuerpo['periodo']

        self.assertTrue(periodo['completo'],
                        'Sin fechas, el periodo tiene que venir marcado como completo '
                        'para que la interfaz pueda decir "todo el tratamiento".')
        self.assertEqual(periodo['desde'], self.alta.isoformat(),
                         'El default arranca en la fecha_alta del paciente.')

        dias = (dt.date.fromisoformat(periodo['hasta'])
                - dt.date.fromisoformat(periodo['desde'])).days
        self.assertGreater(
            dias, MAXIMO_DIAS_RANGO,
            f'El periodo por defecto quedo en {dias} dias. Este paciente tiene '
            f'{DIAS_DE_TRATAMIENTO_LARGO} dias de tratamiento: si el default pagara el '
            'tope, el grafico mostraria un tratamiento recortado sin avisar.')

        # Y la prueba de que ese rango largo se USA: la sesion del primer dia
        # del tratamiento tiene que estar en la serie.
        fechas = [punto['fecha']
                  for serie in cuerpo['objetivos'] for punto in serie['puntos']]
        self.assertIn(
            (self.alta + dt.timedelta(days=1)).isoformat(), fechas,
            'La sesion mas vieja del tratamiento no esta en la serie: el default '
            f'no llego hasta el principio. Fechas devueltas: {fechas}')

    def test_con_fechas_explicitas_el_tope_se_aplica(self):
        desde = dt.date.today() - dt.timedelta(days=MAXIMO_DIAS_RANGO + 5)
        resp = self._pedir(desde=desde.isoformat(), hasta=dt.date.today().isoformat())
        self.assertEqual(
            resp.status_code, 400,
            'Con fechas explicitas el rango excesivo es un error del llamador, no '
            f'una serie recortada en silencio. Llego: {resp.get_json()}')
        self.assertIn('maximo es', resp.get_json().get('mensaje', ''))

    def test_con_fechas_explicitas_en_el_limite_funciona(self):
        # 366 dias exactos: el borde tiene que entrar. Con `dias > MAXIMO` el
        # calculo es (hasta - desde).days + 1, asi que el limite es 365 de
        # diferencia. Si alguien lo cambia a >=, este test lo agarra.
        hasta = dt.date.today()
        desde = hasta - dt.timedelta(days=MAXIMO_DIAS_RANGO - 1)
        resp = self._pedir(desde=desde.isoformat(), hasta=hasta.isoformat())
        self.assertEqual(resp.status_code, 200, resp.get_json())
        self.assertFalse(
            resp.get_json()['periodo']['completo'],
            'Con fechas explicitas el periodo NO es "completo": lo eligio el '
            'llamador, no el tratamiento del paciente.')

    def test_rango_invertido_es_un_error_no_una_lista_vacia(self):
        resp = self._pedir(desde='2026-06-01', hasta='2026-05-01')
        self.assertEqual(resp.status_code, 400, resp.get_json())
        self.assertIn('invertido', resp.get_json().get('mensaje', ''))

    # --- forma del JSON -------------------------------------------------

    def test_la_sesion_sin_calificar_viaja_como_valor_null(self):
        cuerpo = self._pedir().get_json()
        self.assertEqual(len(cuerpo['objetivos']), 1, cuerpo['objetivos'])
        serie = cuerpo['objetivos'][0]
        self.assertEqual(len(serie['puntos']), 2,
                         'Las dos sesiones tienen que estar, calificadas o no.')
        for punto in serie['puntos']:
            self.assertIsNone(
                punto['valor'],
                'Ninguna de las dos sesiones tiene evolucion cargada: el valor '
                f'tiene que ser null y llego {punto["valor"]!r}.')
            self.assertEqual(punto['estado_sesion'], 'completa')
        self.assertEqual(cuerpo['total_calificados'], 0)
        self.assertEqual(cuerpo['total_puntos'], 2)

    def test_el_paciente_dado_de_baja_conserva_su_serie(self):
        """
        Paciente 4 del seed: dado de baja y con TODOS sus objetivos archivados
        por la baja. Es el caso donde la version ingenua devolveria un grafico
        vacio sin ningun error.
        """
        with self.app.app_context():
            id_baja = db.session.execute(text(
                'SELECT id FROM pacientes WHERE activo = FALSE '
                'AND nro_historia NOT LIKE :m ORDER BY id LIMIT 1'),
                {'m': MARCA_HISTORIA + '%'}).scalar()
            activos = db.session.execute(text(
                'SELECT COUNT(*) FROM objetivos_terapeuticos '
                'WHERE id_paciente = :p AND activo = TRUE'), {'p': id_baja}).scalar()
            db.session.rollback()

        self.assertIsNotNone(id_baja, 'El seed tiene que traer un paciente de baja.')
        self.assertEqual(activos, 0,
                         'El paciente de baja del seed tiene que tener TODOS sus '
                         'objetivos archivados: es lo que hace valer este test.')

        resp = self._pedir(id_paciente=id_baja)
        self.assertEqual(resp.status_code, 200, resp.get_json())
        cuerpo = resp.get_json()
        self.assertGreater(
            len(cuerpo['objetivos']), 0,
            'El paciente dado de baja no devolvio ninguna serie. Sus objetivos estan '
            'todos archivados: si la condicion mirara solo `activo`, su historia '
            'entera seria invisible.')
        self.assertGreater(
            cuerpo['total_calificados'], 0,
            'La historia del paciente de baja quedo sin ninguna calificacion visible.')
        # La serie de un objetivo archivado tiene que traer con que cerrarse.
        for serie in cuerpo['objetivos']:
            self.assertFalse(serie['activo'])
            self.assertIsNotNone(
                serie['fecha_archivado'],
                'Una serie archivada sin fecha_archivado queda dibujada como si el '
                f'objetivo siguiera vigente: {serie["descripcion"]!r}')

    def test_ninguna_evolucion_del_periodo_queda_fuera_de_la_respuesta(self):
        """
        El contador del procedimiento cuenta EVOLUCIONES del periodo; el de la
        respuesta cuenta las que quedaron adentro de alguna serie. Si difieren,
        hay evoluciones que el grafico no muestra.
        """
        with self.app.app_context():
            id_baja = db.session.execute(text(
                'SELECT id FROM pacientes WHERE activo = FALSE '
                'AND nro_historia NOT LIKE :m ORDER BY id LIMIT 1'),
                {'m': MARCA_HISTORIA + '%'}).scalar()
            db.session.rollback()

        cuerpo = self._pedir(id_paciente=id_baja).get_json()
        # El mensaje del procedimiento: "Se encontraron N evoluciones en el periodo"
        numero = int(''.join(c for c in cuerpo['mensaje'] if c.isdigit()))
        self.assertEqual(
            cuerpo['total_calificados'], numero,
            f'El procedimiento contó {numero} evoluciones en el periodo y solo '
            f'{cuerpo["total_calificados"]} entraron en alguna serie: la diferencia '
            'son datos clinicos que el grafico no dibuja.')

    # --- permisos --------------------------------------------------------

    def test_rrhh_no_puede_ver_la_evolucion(self):
        resp = self._pedir(token=self.tok_rrhh)
        self.assertEqual(
            resp.status_code, 403,
            'La serie de evolucion es contenido clinico: RRHH no accede. '
            f'Llego {resp.status_code}: {resp.get_json()}')

    def test_sin_token_no_se_puede(self):
        resp = self.cliente.get(f'/api/pacientes/{self.id_paciente}/evolucion')
        self.assertIn(resp.status_code, (401, 422), resp.get_json())

    def test_paciente_inexistente_da_404(self):
        resp = self._pedir(id_paciente=999999)
        self.assertEqual(resp.status_code, 404, resp.get_json())


class TestNingunaEvolucionAceptadaQuedaInvisible(unittest.TestCase):
    """
    UNA sola invariante, por dos puertas distintas:

        si el sistema ACEPTO guardar una evolucion, esa evolucion tiene que
        aparecer en el grafico que la ficha pide por defecto.

    Sale de un defecto reportado por una terapeuta ocupacional externa que uso
    el sistema sin que nadie le explicara nada (2026-08-15): cargo paciente,
    tres objetivos, una sesion y una evolucion, y la pestania Progreso le
    contesto "Todavia no hay nada que graficar". El dato estaba guardado: lo que
    no lo alcanzaba era la ventana por defecto del endpoint.

    POR QUE NO ALCANZA LA ASERCION QUE YA EXISTE. tests/db/graficos tiene
    `ninguna_evolucion_queda_fuera_de_su_serie`, que mide lo mismo — pero llama
    al procedimiento con un rango EXPLICITO de 2000-01-01 a 2100-01-01. Ninguna
    ventana puede fallar cuando se le pasa un siglo de ancho. La ventana por
    defecto no vive en SQL sino en `_resolver_periodo`
    (evoluciones_service.py), asi que solo se puede medir desde aca.

    EL FIXTURE ES PROPIO A PROPOSITO. El seed no tiene ninguna sesion futura ni
    ningun objetivo creado despues de la sesion que califica, y un caso que no
    esta en el fixture no esta probado por mas que el test exista. Es la misma
    leccion que dejo el par de marcas del mismo dia.

    LAS DOS PUERTAS NO ESTAN EN EL MISMO ESTADO, y conviene no confundirlas:

    - La PRIMERA no es una decision abierta: ya esta decidida y escrita.
      ESTADO.md:1723-1727 dice que sin fechas el endpoint devuelve el
      "tratamiento entero", que ese caso no paga el tope de 366 dias, y el
      motivo textual es que "recortarlo dejaria el grafico a medias sin
      decirlo" — que es exactamente lo que paso. `fecha_alta -> date.today()`
      no cumple ese contrato. Ahi no hay que elegir nada: hay que cumplirlo.
    - La SEGUNDA (objetivo creado despues de la sesion) si es decision
      abierta, y este archivo no la toma.

    Lo que ninguno de los dos casos hace es imponer POR DONDE se cumple. Si el
    sistema pasa a rechazar la evolucion sobre una sesion que todavia no
    ocurrio, la evolucion invisible no puede existir y la invariante se cumple
    igual: por eso `_exigir_visible` acepta las dos salidas.
    """

    @classmethod
    def setUpClass(cls):
        cls.app = e.obtener_app()
        cls.laura_id, cls.laura_rol, _ = e.obtener_usuario_por_email(
            e.EMAILS_SEED['terapeuta'])
        cls.tok = e.token_valido(
            cls.laura_id, cls.laura_rol, e.EMAILS_SEED['terapeuta'])
        cls._limpiar()

    @classmethod
    def tearDownClass(cls):
        cls._limpiar()

    @classmethod
    def _limpiar(cls):
        with cls.app.app_context():
            for sentencia in (
                'DELETE ev FROM evoluciones ev JOIN sesiones s ON s.id = ev.id_sesion '
                ' JOIN pacientes p ON p.id = s.id_paciente WHERE p.nro_historia LIKE :m',
                'DELETE s FROM sesiones s JOIN pacientes p ON p.id = s.id_paciente '
                ' WHERE p.nro_historia LIKE :m',
                'DELETE o FROM objetivos_terapeuticos o JOIN pacientes p ON p.id = o.id_paciente '
                ' WHERE p.nro_historia LIKE :m',
                'DELETE FROM pacientes WHERE nro_historia LIKE :m',
            ):
                db.session.execute(text(sentencia), {'m': MARCA_INVISIBLE + '%'})
            db.session.commit()

    def setUp(self):
        self.cliente = e.cliente()

    # --- utilidades de siembra ------------------------------------------

    def _sembrar_paciente(self, sufijo, alta):
        with self.app.app_context():
            db.session.execute(text(
                'INSERT INTO pacientes (id_usuario,nombre,apellido,fecha_nacimiento,'
                'nro_historia,activo,fecha_alta) '
                "VALUES (NULL,'Invisible',:ap,'2007-02-14',:hc,TRUE,:alta)"),
                {'ap': sufijo, 'hc': f'{MARCA_INVISIBLE}-{sufijo}', 'alta': alta})
            id_paciente = db.session.execute(text('SELECT LAST_INSERT_ID()')).scalar()
            db.session.commit()
        return id_paciente

    def _sembrar_objetivo(self, id_paciente, descripcion, fecha_creacion=None):
        with self.app.app_context():
            db.session.execute(text(
                'INSERT INTO objetivos_terapeuticos (id_paciente,descripcion,activo) '
                'VALUES (:p,:d,TRUE)'), {'p': id_paciente, 'd': descripcion})
            id_objetivo = db.session.execute(text('SELECT LAST_INSERT_ID()')).scalar()
            if fecha_creacion is not None:
                db.session.execute(text(
                    'UPDATE objetivos_terapeuticos SET fecha_creacion = :f WHERE id = :o'),
                    {'f': fecha_creacion, 'o': id_objetivo})
            db.session.commit()
        return id_objetivo

    def _sembrar_sesion(self, id_paciente, fecha, hora='08:00:00'):
        # hora_fin se calcula: hardcodearla ya rompio este fixture con un
        # `ERROR 1644: La hora de fin debe ser posterior a la hora de inicio`
        # apenas se movio la hora de inicio de una sesion.
        inicio = dt.datetime.combine(dt.date(2000, 1, 1), dt.time.fromisoformat(hora))
        fin = (inicio + dt.timedelta(minutes=45)).time().isoformat()
        with self.app.app_context():
            db.session.execute(text(
                'INSERT INTO sesiones (id_terapeuta,id_paciente,fecha,hora_inicio,'
                "hora_fin,estado) VALUES (1,:p,:f,:h,:hf,'completa')"),
                {'p': id_paciente, 'f': fecha, 'h': hora, 'hf': fin})
            id_sesion = db.session.execute(text('SELECT LAST_INSERT_ID()')).scalar()
            db.session.commit()
        return id_sesion

    def _cargar_evolucion(self, id_sesion, id_objetivo, valor=2):
        return self.cliente.post('/api/evoluciones', json={
            'id_sesion': id_sesion, 'id_objetivo': id_objetivo, 'valor': valor,
            'observaciones': 'INVIS observacion de la terapeuta',
        }, headers=e.encabezado_auth(self.tok))

    def _grafico_por_defecto(self, id_paciente):
        """La pestania Progreso pide SIN fechas. Es el unico camino que la ficha usa."""
        resp = self.cliente.get(f'/api/pacientes/{id_paciente}/evolucion',
                                headers=e.encabezado_auth(self.tok))
        self.assertEqual(resp.status_code, 200, resp.get_json())
        return resp.get_json()

    def _exigir_visible(self, id_paciente, respuesta_post, como_entro):
        """
        La invariante, escrita una sola vez.

        Si el POST fue rechazado, el caso no puede existir y no hay nada que
        exigir: esa es la otra correccion posible y tambien cierra el agujero.
        """
        if respuesta_post.status_code != 201:
            return

        cuerpo = self._grafico_por_defecto(id_paciente)
        series = cuerpo['objetivos']
        puntos = sum(len(s['puntos']) for s in series)
        self.assertGreaterEqual(
            cuerpo['total_calificados'], 1,
            f'El sistema acepto guardar la evolucion ({como_entro}) y el grafico '
            f'que pide la ficha —sin fechas— no la muestra.\n'
            f'  periodo devuelto : {cuerpo["periodo"]}\n'
            f'  series           : {len(series)}\n'
            f'  puntos           : {puntos}\n'
            f'  calificados      : {cuerpo["total_calificados"]}\n'
            f'  mensaje del proc.: {cuerpo["mensaje"]!r}\n'
            'Con cero series la ficha dibuja el estado vacio "Todavia no hay nada '
            'que graficar" (PacienteFicha.jsx:345), que afirma algo falso: el dato '
            'esta guardado. Este test se apaga cuando el dato deja de ser '
            'invisible, sea porque el grafico pasa a alcanzarlo o porque el '
            'sistema deja de aceptar que se cargue asi. Cual de las dos es la '
            'correccion no lo decide este archivo.')

    # --- puerta 1: la sesion todavia no ocurrio --------------------------

    def test_evolucion_sobre_sesion_futura_aparece_en_el_grafico(self):
        """
        El caso literal de la TO: alta hoy, sesion agendada para pasado maniana,
        evolucion cargada en el acto.

        La ventana por defecto es `fecha_alta` -> `date.today()`
        (evoluciones_service.py:46), asi que una sesion posterior a hoy queda
        afuera y con ella TODA la serie: no hay objetivos, no hay puntos, no hay
        grafico.

        ESTO CONTRADICE UN CONTRATO YA ESCRITO, no es una alternativa de
        diseno. ESTADO.md:1723-1727: "Sin fechas devuelve el tratamiento entero
        y ese caso no paga el tope de 366 dias: el default esta acotado por la
        realidad del paciente, no por lo que pida el llamador, y recortarlo
        dejaria el grafico a medias sin decirlo". El propio docstring de
        `_resolver_periodo` repite "el TRATAMIENTO ENTERO" y en la misma frase
        lo implementa como "de fecha_alta a hoy": las dos mitades solo
        coinciden mientras ninguna sesion caiga despues de hoy.

        El sistema ya sabe en otro lado que una sesion que no ocurrio no se
        califica —`pendientes-evolucion` la excluye por fecha
        (sesiones_service.py:239-240)— pero eso es un filtro de listado, no una
        regla, y el camino de escritura no lo aplica.
        """
        hoy = dt.date.today()
        id_paciente = self._sembrar_paciente('FUT', hoy)
        objetivo = self._sembrar_objetivo(id_paciente, 'INVIS objetivo de sesion futura')
        sesion = self._sembrar_sesion(id_paciente, hoy + dt.timedelta(days=2))

        post = self._cargar_evolucion(sesion, objetivo)
        self._exigir_visible(
            id_paciente, post,
            'sobre una sesion agendada para dentro de dos dias')

    # --- puerta 2: el objetivo se creo despues de la sesion --------------

    def test_evolucion_sobre_objetivo_creado_despues_de_la_sesion_aparece(self):
        """
        La misma invariante por la otra puerta, y esta esta VIVA en la base real:
        la evolucion 460 de `asisto` califica la sesion 584 (2026-08-05 13:00)
        contra el objetivo 47, creado el 2026-08-14 20:28 — nueve dias despues—.

        La condicion de vida del procedimiento pide
        `o.fecha_creacion <= TIMESTAMP(s.fecha, s.hora_inicio)` (schema.sql:2248),
        asi que ese objetivo no es serie de esa sesion y la evolucion no entra en
        ningun grafico. Aca la sesion esta en el PASADO: si este caso queda en
        rojo cuando el de la sesion futura ya este verde, son dos defectos y no
        uno.
        """
        hoy = dt.date.today()
        id_paciente = self._sembrar_paciente('TARDE', hoy - dt.timedelta(days=30))
        sesion = self._sembrar_sesion(
            id_paciente, hoy - dt.timedelta(days=7), hora='09:00:00')
        # El objetivo se crea HOY: despues de la sesion que va a calificar.
        objetivo = self._sembrar_objetivo(
            id_paciente, 'INVIS objetivo creado despues de la sesion',
            fecha_creacion=dt.datetime.now())

        post = self._cargar_evolucion(sesion, objetivo, valor=4)
        self._exigir_visible(
            id_paciente, post,
            'contra un objetivo creado despues de esa sesion')


if __name__ == '__main__':
    unittest.main(verbosity=2)

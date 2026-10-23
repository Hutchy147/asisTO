"""
tests/nube/test_informes_api.py — informes del tratamiento (Entrega 6, HDU 5 y 8).

seed.sql: paciente 1 (Tomas) -> Laura, paciente 2 (Valentina) -> Diego; familiar
1 (Marta) -> paciente 1. Las sesiones del seed son de junio de 2026. El seed trae
un informe mensual PUBLICADO del paciente 1 en 2026-06 (id 1) y un borrador del
paciente 2 en 2026-06 (id 2). Cada prueba limpia lo que crea: se borran los
informes con id mayor al del seed y los avisos de informe generados.
"""
import datetime as dt
import re
import threading
import unittest
import urllib.error
from unittest import mock

from _base import BaseApi, EMAILS, CONTRASENA, hoy

PERIODO_VACIO = '2026-05'   # el seed no tiene sesiones en mayo
PERIODO_SEM = '2026-S1'
PERIODO_SIN_ASIGNACION = '2026-08'   # Diego estuvo asignado al paciente 1 hasta el 04/05/2026


def mes_futuro():
    d = hoy().replace(day=1) + dt.timedelta(days=40)
    return f'{d.year:04d}-{d.month:02d}'


class InformesApi(BaseApi):
    def setUp(self):
        self.tope_seed = 2   # el seed trae los informes 1 y 2
        self.antes = dt.datetime.now().replace(microsecond=0)

    def tearDown(self):
        self.sql('DELETE FROM informes WHERE id > :t', t=self.tope_seed)
        self.sql("DELETE FROM notificaciones WHERE tipo = 'informe_generado' AND fecha >= :f", f=self.antes)

    # --- utilidades --------------------------------------------------------
    def generar(self, quien='laura', paciente=1, **cuerpo):
        cuerpo.setdefault('usar_ia', False)
        return self.llamar(quien, 'post', f'/api/pacientes/{paciente}/informes', json=cuerpo)

    def borrador(self, periodo=PERIODO_VACIO, tipo='mensual', paciente=1, quien='laura'):
        r = self.generar(quien, paciente, tipo=tipo, periodo=periodo)
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        return r.get_json()

    def publicable(self, **kw):
        """Borrador con el texto ya resuelto (sin marcas COMPLETAR), listo para publicar."""
        b = self.borrador(**kw)
        r = self.llamar('laura', 'put', f"/api/informes/{b['id']}", json={'contenido': '## Resumen\nTexto revisado.'})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        return b['id']

    # --- permisos ----------------------------------------------------------
    def test_solo_terapeutas(self):
        rutas = [('get', '/api/pacientes/1/informes'), ('get', '/api/informes/1'),
                 ('get', '/api/informes/control'), ('get', '/api/informes/1/pdf'),
                 ('get', '/api/pacientes/1/informes/diarios?tipo=mensual&periodo=2026-06')]
        for quien in ('rrhh', 'admin', 'familiar', 'paciente'):
            for metodo, ruta in rutas:
                self.assertEqual(self.llamar(quien, metodo, ruta).status_code, 403, f'{quien} {ruta}')
        for metodo, ruta in rutas:
            self.assertEqual(self.llamar(None, metodo, ruta).status_code, 401, ruta)
        self.assertEqual(self.generar('rrhh', tipo='mensual', periodo=PERIODO_VACIO).status_code, 403)

    def test_terapeuta_no_asignado_no_escribe_pero_si_lee(self):
        # Diego no tiene asignado al paciente 1 en agosto
        r = self.generar('diego', 1, tipo='mensual', periodo=PERIODO_SIN_ASIGNACION)
        self.assertEqual(r.status_code, 403, r.get_data(as_text=True))
        b = self.borrador(periodo=PERIODO_SIN_ASIGNACION)
        self.assertEqual(self.llamar('diego', 'get', f"/api/informes/{b['id']}").status_code, 200)
        for metodo, ruta, cuerpo in (
            ('put', f"/api/informes/{b['id']}", {'contenido': 'x'}),
            ('post', f"/api/informes/{b['id']}/publicacion", None),
            ('delete', f"/api/informes/{b['id']}", None),
        ):
            kw = {'json': cuerpo} if cuerpo else {}
            self.assertEqual(self.llamar('diego', metodo, ruta, **kw).status_code, 403, ruta)
        # y el borrador sigue ahi
        self.assertEqual(self.llamar('laura', 'get', f"/api/informes/{b['id']}").status_code, 200)

    def test_la_asignacion_se_evalua_contra_el_periodo_no_contra_hoy(self):
        # Diego tuvo al paciente 1 hasta el 04/05/2026: puede informar mayo (carga retroactiva)
        # y no puede informar junio, aunque el paciente siga en tratamiento con otra persona.
        mayo = self.generar('diego', 1, tipo='mensual', periodo='2026-05')
        self.assertEqual(mayo.status_code, 201, mayo.get_data(as_text=True))
        junio = self.generar('diego', 1, tipo='mensual', periodo='2026-06')
        self.assertIn(junio.status_code, (403, 409))
        self.assertEqual(self.generar('diego', 1, tipo='mensual', periodo='2026-07').status_code, 403)

    # --- generacion --------------------------------------------------------
    def test_generar_mensual_con_plantilla(self):
        d = self.borrador()
        self.assertEqual(d['estado'], 'borrador')
        self.assertEqual(d['generado_con'], 'plantilla')
        self.assertIsNone(d['proveedor'])
        self.assertEqual(d['version'], 1)
        self.assertEqual((d['fecha_desde'], d['fecha_hasta']), ('2026-05-01', '2026-05-31'))
        for seccion in ('## Datos del paciente', '## Período', '## Asistencia', '## Objetivos trabajados',
                        '## Observaciones de las sesiones', '## Cierre y próximos pasos'):
            self.assertIn(seccion, d['contenido'])
        self.assertIn('Tomas Aguirre', d['contenido'])
        self.assertIn('No se registraron sesiones en el período', d['contenido'])
        self.assertIn('[COMPLETAR', d['contenido'])
        self.assertEqual(d['contenido'], d['contenido_original'])
        self.assertFalse(d['editado'])

    def test_semestral_usa_las_palabras_de_la_escala_y_ningun_numero(self):
        d = self.borrador(tipo='semestral', periodo=PERIODO_SEM)
        texto = d['contenido']
        self.assertIn('Primer semestre de 2026', texto)
        self.assertRegex(texto, r'asisti[oó] a \d+ sesi[oó]n')
        palabras = ('No logrado', 'Inicial', 'En proceso', 'Avanzado', 'Logrado')
        self.assertTrue(any(p in texto for p in palabras), texto)
        # nada de promedios ni porcentajes
        self.assertNotRegex(texto, r'\d+[.,]\d+')
        self.assertNotIn('%', texto)
        self.assertNotIn('promedio', texto.lower())

    def test_regenerar_reemplaza_el_borrador_y_no_duplica(self):
        primero = self.borrador()
        self.llamar('laura', 'put', f"/api/informes/{primero['id']}", json={'contenido': '## Otro\nEditado a mano.'})
        segundo = self.borrador()
        self.assertEqual(segundo['id'], primero['id'])
        self.assertEqual(segundo['version'], 1)
        self.assertNotIn('Editado a mano', segundo['contenido'])
        historial = self.llamar('laura', 'get', '/api/pacientes/1/informes').get_json()
        mayo = [i for i in historial['informes'] if i['periodo'] == PERIODO_VACIO]
        self.assertEqual(len(mayo), 1)

    def test_periodos_invalidos(self):
        casos = [
            dict(tipo='mensual', periodo='2026-13'),
            dict(tipo='mensual', periodo='junio'),
            dict(tipo='semestral', periodo='2026-S3'),
            dict(tipo='semestral', periodo='2026-06'),
            dict(tipo='trimestral', periodo='2026-T2'),
            dict(tipo='mensual', periodo=mes_futuro()),
            dict(tipo='', periodo='2026-06'),
        ]
        for c in casos:
            r = self.generar(**c)
            self.assertEqual(r.status_code, 400, f'{c} -> {r.get_data(as_text=True)}')

    def test_ya_publicado_no_se_regenera(self):
        # el seed ya tiene publicado el mensual 2026-06 del paciente 1
        r = self.generar('laura', 1, tipo='mensual', periodo='2026-06')
        self.assertEqual(r.status_code, 409, r.get_data(as_text=True))
        self.assertIn('corregir', r.get_json()['mensaje'])

    def test_no_se_genera_para_un_paciente_inexistente(self):
        self.assertEqual(self.generar('laura', 999, tipo='mensual', periodo=PERIODO_VACIO).status_code, 404)

    # --- edicion, publicacion y correccion --------------------------------
    def test_no_se_publica_con_completar_sin_resolver(self):
        b = self.borrador()
        r = self.llamar('laura', 'post', f"/api/informes/{b['id']}/publicacion")
        self.assertEqual(r.status_code, 400)
        self.assertIn('COMPLETAR', r.get_json()['mensaje'])
        self.assertEqual(self.llamar('laura', 'get', f"/api/informes/{b['id']}").get_json()['estado'], 'borrador')

    def test_editar_guarda_y_marca_editado(self):
        b = self.borrador()
        r = self.llamar('laura', 'put', f"/api/informes/{b['id']}", json={'contenido': '## Resumen\nTexto propio.'})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        d = r.get_json()
        self.assertTrue(d['editado'])
        self.assertEqual(d['contenido'], '## Resumen\nTexto propio.')
        self.assertIn('Datos del paciente', d['contenido_original'])   # lo generado se conserva
        self.assertIsNotNone(d['fecha_edicion'])
        for vacio in ('', '   ', None):
            self.assertEqual(self.llamar('laura', 'put', f"/api/informes/{b['id']}", json={'contenido': vacio}).status_code, 400)
        largo = 'x' * 60001
        self.assertEqual(self.llamar('laura', 'put', f"/api/informes/{b['id']}", json={'contenido': largo}).status_code, 400)

    def test_publicar_congela_el_informe(self):
        id_informe = self.publicable()
        r = self.llamar('laura', 'post', f'/api/informes/{id_informe}/publicacion')
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        d = r.get_json()
        self.assertEqual(d['estado'], 'final')
        self.assertIsNotNone(d['fecha_publicacion'])
        # un publicado no se edita, no se descarta y no se vuelve a publicar
        self.assertEqual(self.llamar('laura', 'put', f'/api/informes/{id_informe}', json={'contenido': 'otro'}).status_code, 400)
        self.assertEqual(self.llamar('laura', 'delete', f'/api/informes/{id_informe}').status_code, 400)
        self.assertEqual(self.llamar('laura', 'post', f'/api/informes/{id_informe}/publicacion').status_code, 400)
        # sigue intacto
        self.assertEqual(self.llamar('laura', 'get', f'/api/informes/{id_informe}').get_json()['contenido'], '## Resumen\nTexto revisado.')

    def test_corregir_arma_version_nueva_y_reemplaza_al_publicar(self):
        original = self.publicable()
        self.llamar('laura', 'post', f'/api/informes/{original}/publicacion')
        r = self.llamar('laura', 'post', f'/api/informes/{original}/correccion')
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        nuevo = r.get_json()
        self.assertEqual(nuevo['version'], 2)
        self.assertEqual(nuevo['estado'], 'borrador')
        self.assertEqual(nuevo['contenido'], '## Resumen\nTexto revisado.')
        # mientras exista ese borrador no se puede abrir otra correccion
        self.assertEqual(self.llamar('laura', 'post', f'/api/informes/{original}/correccion').status_code, 409)
        # el vigente sigue siendo el viejo hasta publicar el nuevo
        self.assertEqual(self.llamar('laura', 'get', f'/api/informes/{original}').get_json()['estado'], 'final')
        self.llamar('laura', 'put', f"/api/informes/{nuevo['id']}", json={'contenido': '## Resumen\nTexto corregido.'})
        self.assertEqual(self.llamar('laura', 'post', f"/api/informes/{nuevo['id']}/publicacion").status_code, 200)
        self.assertEqual(self.llamar('laura', 'get', f'/api/informes/{original}').get_json()['estado'], 'reemplazado')
        self.assertEqual(self.llamar('laura', 'get', f"/api/informes/{nuevo['id']}").get_json()['estado'], 'final')
        # solo se corrige un publicado vigente
        self.assertEqual(self.llamar('laura', 'post', f'/api/informes/{original}/correccion').status_code, 400)
        # el historial conserva las dos versiones
        historial = self.llamar('laura', 'get', '/api/pacientes/1/informes').get_json()['informes']
        versiones = sorted(i['version'] for i in historial if i['periodo'] == PERIODO_VACIO)
        self.assertEqual(versiones, [1, 2])

    def test_descartar_solo_borradores(self):
        b = self.borrador()
        self.assertEqual(self.llamar('laura', 'delete', f"/api/informes/{b['id']}").status_code, 200)
        self.assertEqual(self.llamar('laura', 'get', f"/api/informes/{b['id']}").status_code, 404)
        self.assertEqual(self.llamar('laura', 'delete', '/api/informes/999999').status_code, 404)
        # el publicado del seed no se toca
        self.assertEqual(self.llamar('laura', 'delete', '/api/informes/1').status_code, 400)

    def test_dos_publicaciones_simultaneas_una_sola_gana(self):
        id_informe = self.publicable()
        resultados = []

        def publicar():
            cliente = self.app.test_client()
            r = cliente.post('/api/auth/login', json={'email': EMAILS['laura'], 'contrasena': CONTRASENA})
            token = r.get_json()['token']
            resp = cliente.post(f'/api/informes/{id_informe}/publicacion', headers={'Authorization': f'Bearer {token}'})
            resultados.append(resp.status_code)

        hilos = [threading.Thread(target=publicar) for _ in range(2)]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join()
        self.assertEqual(sorted(resultados), [200, 400], resultados)
        familiares = self.llamar('familiar', 'get', '/api/familiar/notificaciones?tipo=informe_generado').get_json()
        self.assertEqual(sum(1 for n in familiares['notificaciones'] if n['fecha'] >= self.antes.isoformat()), 1)

    # --- avisos al familiar ------------------------------------------------
    def test_publicar_avisa_al_familiar_vinculado(self):
        antes = self.llamar('familiar', 'get', '/api/familiar/notificaciones?tipo=informe_generado').get_json()['total']
        id_informe = self.publicable()
        d = self.llamar('laura', 'post', f'/api/informes/{id_informe}/publicacion').get_json()
        self.assertEqual(d['familiares_avisados'], 1)
        despues = self.llamar('familiar', 'get', '/api/familiar/notificaciones?tipo=informe_generado').get_json()['total']
        self.assertEqual(despues, antes + 1)

    def test_un_borrador_no_avisa(self):
        antes = self.llamar('familiar', 'get', '/api/familiar/notificaciones?tipo=informe_generado').get_json()['total']
        self.publicable()
        despues = self.llamar('familiar', 'get', '/api/familiar/notificaciones?tipo=informe_generado').get_json()['total']
        self.assertEqual(despues, antes)

    # --- diarios y control -------------------------------------------------
    def test_diarios_del_periodo(self):
        r = self.llamar('laura', 'get', '/api/pacientes/1/informes/diarios?tipo=mensual&periodo=2026-06')
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        d = r.get_json()
        self.assertGreater(len(d['diarios']), 0)
        self.assertTrue(all(x['fecha'].startswith('2026-06') for x in d['diarios']))
        con_objetivo = [x for x in d['diarios'] if x['objetivos']]
        self.assertTrue(con_objetivo)
        self.assertIn(con_objetivo[0]['objetivos'][0]['valor'], ('No logrado', 'Inicial', 'En proceso', 'Avanzado', 'Logrado'))
        vacio = self.llamar('laura', 'get', f'/api/pacientes/1/informes/diarios?tipo=mensual&periodo={PERIODO_VACIO}').get_json()
        self.assertEqual(vacio['diarios'], [])
        self.assertEqual(self.llamar('laura', 'get', '/api/pacientes/1/informes/diarios?tipo=mensual&periodo=xx').status_code, 400)

    def test_control_mensual(self):
        r = self.llamar('laura', 'get', '/api/informes/control?mes=2026-06')
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        d = r.get_json()
        self.assertEqual(d['mes'], '2026-06')
        self.assertTrue(d['cierra_semestre'])
        filas = {f['id_paciente']: f for f in d['pacientes']}
        self.assertIn(1, filas)
        self.assertNotIn(2, filas)                        # el paciente 2 es de Diego
        self.assertEqual(filas[1]['mensual']['estado'], 'publicado')
        self.assertEqual(filas[1]['semestral']['estado'], 'pendiente')   # junio cierra el semestre
        self.assertEqual(d['total'], len(d['pacientes']))
        self.assertEqual(sum(d['resumen'].values()), d['total'])
        # un mes que no cierra semestre no lo pide
        mayo = self.llamar('laura', 'get', f'/api/informes/control?mes={PERIODO_VACIO}').get_json()
        self.assertEqual({f['semestral']['estado'] for f in mayo['pacientes']}, {'no_corresponde'})
        self.assertEqual(self.llamar('laura', 'get', '/api/informes/control?mes=2026-99').status_code, 400)
        # el de Diego ve a su paciente y no al de Laura, con el borrador del seed
        diego = {f['id_paciente']: f for f in self.llamar('diego', 'get', '/api/informes/control?mes=2026-06').get_json()['pacientes']}
        self.assertIn(2, diego)
        self.assertNotIn(1, diego)
        self.assertEqual(diego[2]['mensual']['estado'], 'borrador')

    def test_control_refleja_un_borrador_nuevo(self):
        antes = {f['id_paciente']: f for f in self.llamar('laura', 'get', f'/api/informes/control?mes={PERIODO_VACIO}').get_json()['pacientes']}
        self.assertEqual(antes[1]['mensual']['estado'], 'pendiente')
        self.borrador()
        despues = {f['id_paciente']: f for f in self.llamar('laura', 'get', f'/api/informes/control?mes={PERIODO_VACIO}').get_json()['pacientes']}
        self.assertEqual(despues[1]['mensual']['estado'], 'borrador')

    # --- familiar ----------------------------------------------------------
    def test_familiar_ve_solo_publicados(self):
        id_borrador = self.borrador()['id']
        d = self.llamar('familiar', 'get', '/api/familiar/pacientes/1/informes').get_json()
        ids = [i['id'] for i in d['informes']]
        self.assertIn(1, ids)                              # el publicado del seed
        self.assertNotIn(id_borrador, ids)                 # el borrador no
        self.assertTrue(all(i['estado'] == 'final' for i in d['informes']))
        # y no recibe nombres de profesionales ni el contenido original
        texto = str(d)
        self.assertNotIn('autor', texto)
        self.assertNotIn('contenido_original', texto)
        r = self.llamar('familiar', 'get', '/api/familiar/pacientes/1/informes/1')
        self.assertEqual(r.status_code, 200)
        self.assertIn('Tomas Aguirre', r.get_json()['contenido'])
        self.assertNotIn('autor', r.get_json())
        self.assertNotIn('contenido_original', r.get_json())
        # el borrador y el reemplazado responden "no existe"
        self.assertEqual(self.llamar('familiar', 'get', f'/api/familiar/pacientes/1/informes/{id_borrador}').status_code, 404)
        self.assertEqual(self.llamar('familiar', 'get', f'/api/familiar/pacientes/1/informes/{id_borrador}/pdf').status_code, 404)

    def test_familiar_ajeno_o_inexistente(self):
        # Marta no ve al paciente 2, ni un informe del paciente 2 por el camino del paciente 1
        self.assertEqual(self.llamar('familiar', 'get', '/api/familiar/pacientes/2/informes').status_code, 403)
        self.assertEqual(self.llamar('familiar', 'get', '/api/familiar/pacientes/999/informes').status_code, 403)
        self.assertEqual(self.llamar('familiar', 'get', '/api/familiar/pacientes/2/informes/2').status_code, 403)
        self.assertEqual(self.llamar('familiar', 'get', '/api/familiar/pacientes/1/informes/2').status_code, 404)
        self.assertEqual(self.llamar('familiar', 'get', '/api/familiar/pacientes/1/informes/999').status_code, 404)
        for quien in ('laura', 'rrhh', 'admin', 'paciente'):
            self.assertEqual(self.llamar(quien, 'get', '/api/familiar/pacientes/1/informes').status_code, 403, quien)
        self.assertEqual(self.llamar(None, 'get', '/api/familiar/pacientes/1/informes').status_code, 401)

    def test_una_version_reemplazada_deja_de_verse(self):
        original = self.publicable()
        self.llamar('laura', 'post', f'/api/informes/{original}/publicacion')
        nuevo = self.llamar('laura', 'post', f'/api/informes/{original}/correccion').get_json()
        self.llamar('laura', 'put', f"/api/informes/{nuevo['id']}", json={'contenido': '## Resumen\nCorregido.'})
        self.llamar('laura', 'post', f"/api/informes/{nuevo['id']}/publicacion")
        ids = [i['id'] for i in self.llamar('familiar', 'get', '/api/familiar/pacientes/1/informes').get_json()['informes']]
        self.assertIn(nuevo['id'], ids)
        self.assertNotIn(original, ids)
        self.assertEqual(self.llamar('familiar', 'get', f'/api/familiar/pacientes/1/informes/{original}').status_code, 404)

    # --- PDF ---------------------------------------------------------------
    def test_pdf_terapeuta_y_familiar(self):
        r = self.llamar('familiar', 'get', '/api/familiar/pacientes/1/informes/1/pdf')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.mimetype, 'application/pdf')
        self.assertTrue(r.data.startswith(b'%PDF'))
        self.assertGreater(len(r.data), 1500)
        self.assertIn('attachment', r.headers['Content-Disposition'])
        self.assertIn('informe-mensual-2026-06-tomas-aguirre', r.headers['Content-Disposition'])
        r2 = self.llamar('laura', 'get', '/api/informes/1/pdf')
        self.assertEqual(r2.status_code, 200)
        self.assertTrue(r2.data.startswith(b'%PDF'))
        # un borrador tambien se exporta (la terapeuta lo revisa en papel), pero pesa distinto: lleva la marca
        b = self.borrador()
        r3 = self.llamar('laura', 'get', f"/api/informes/{b['id']}/pdf")
        self.assertEqual(r3.status_code, 200)
        self.assertTrue(r3.data.startswith(b'%PDF'))
        self.assertEqual(self.llamar('laura', 'get', '/api/informes/999999/pdf').status_code, 404)

    def test_pdf_con_caracteres_especiales(self):
        id_informe = self.publicable()
        texto = '## Evolución & seguimiento <b>\n- Ñandú: "comillas" y símbolos < > &\n\nPárrafo con acentos áéíóú.'
        self.llamar('laura', 'put', f'/api/informes/{id_informe}', json={'contenido': texto})
        r = self.llamar('laura', 'get', f'/api/informes/{id_informe}/pdf')
        self.assertEqual(r.status_code, 200, r.data[:200])
        self.assertTrue(r.data.startswith(b'%PDF'))

    # --- IA ----------------------------------------------------------------
    def test_ia_redacta_y_el_nombre_no_sale_del_servidor(self):
        enviados = {}

        class Falso:
            nombre = 'falso:modelo-de-prueba'

            def redactar(self, instrucciones, datos_json):
                enviados['instrucciones'] = instrucciones
                enviados['datos'] = datos_json
                return '## Evolución\nEl paciente mostró avances.\n\n## Cierre y próximos pasos\n[COMPLETAR: pasos]'

        # Se planta el nombre en un texto libre (una observacion y una nota de la sesion), que es por
        # donde se cuela en la vida real. Sin esto la prueba no ejercita el reemplazo.
        fila = self.sql("SELECT e.id, e.observaciones, s.id, s.notas FROM evoluciones e "
                        "JOIN sesiones s ON s.id = e.id_sesion "
                        "WHERE s.id_paciente = 1 AND s.fecha BETWEEN '2026-06-01' AND '2026-06-30' ORDER BY e.id LIMIT 1")[0]
        id_ev, obs_original, id_ses, nota_original = fila
        self.sql("UPDATE evoluciones SET observaciones = 'Tomas Aguirre pidio ayuda; TOMAS se calmo' WHERE id = :i", i=id_ev)
        self.sql("UPDATE sesiones SET notas = 'Aguirre llego tarde' WHERE id = :i", i=id_ses)
        try:
            with mock.patch('app.services.informes_generador.obtener_proveedor', return_value=Falso()):
                r = self.llamar('laura', 'post', '/api/pacientes/1/informes', json={'tipo': 'semestral', 'periodo': PERIODO_SEM})
        finally:
            self.sql("UPDATE evoluciones SET observaciones = :o WHERE id = :i", o=obs_original, i=id_ev)
            self.sql("UPDATE sesiones SET notas = :n WHERE id = :i", n=nota_original, i=id_ses)
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        d = r.get_json()
        self.assertEqual(d['generado_con'], 'ia')
        self.assertEqual(d['proveedor'], 'falso:modelo-de-prueba')
        self.assertIsNone(d.get('advertencia'))
        # la identificacion la agrega el sistema; la narrativa, la IA
        self.assertIn('Tomas Aguirre', d['contenido'])
        self.assertIn('El paciente mostró avances', d['contenido'])
        # lo que viajo al proveedor SI llevaba el texto libre, pero ya sin el nombre
        self.assertIn('pidio ayuda', enviados['datos'])
        for prohibido in ('tomas', 'aguirre'):
            self.assertNotIn(prohibido, enviados['datos'].lower())
        self.assertIn('No use números', enviados['instrucciones'])

    def test_si_la_ia_falla_se_usa_la_plantilla_y_se_avisa(self):
        class Roto:
            nombre = 'roto'

            def redactar(self, instrucciones, datos_json):
                raise urllib.error.URLError('sin red')

        with mock.patch('app.services.informes_generador.obtener_proveedor', return_value=Roto()):
            r = self.llamar('laura', 'post', '/api/pacientes/1/informes', json={'tipo': 'mensual', 'periodo': PERIODO_VACIO})
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        d = r.get_json()
        self.assertEqual(d['generado_con'], 'plantilla')
        self.assertIn('plantilla', d['advertencia'])
        self.assertIn('## Asistencia', d['contenido'])

    def test_respuesta_de_ia_sin_estructura_se_descarta(self):
        class Charla:
            nombre = 'charlatan'

            def redactar(self, instrucciones, datos_json):
                return 'Claro, aquí tiene su informe sin ninguna sección.'

        with mock.patch('app.services.informes_generador.obtener_proveedor', return_value=Charla()):
            d = self.llamar('laura', 'post', '/api/pacientes/1/informes', json={'tipo': 'mensual', 'periodo': PERIODO_VACIO}).get_json()
        self.assertEqual(d['generado_con'], 'plantilla')
        self.assertTrue(d['advertencia'])

    def test_usar_ia_false_no_llama_al_proveedor(self):
        class NoDebeLlamarse:
            nombre = 'x'

            def redactar(self, *a):
                raise AssertionError('no deberia llamarse')

        with mock.patch('app.services.informes_generador.obtener_proveedor', return_value=NoDebeLlamarse()):
            r = self.generar(tipo='mensual', periodo=PERIODO_VACIO, usar_ia=False)
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        self.assertEqual(r.get_json()['generado_con'], 'plantilla')

    # --- PTI ---------------------------------------------------------------
    def test_pti_exige_ingreso_y_se_arma_desde_el_ingreso(self):
        # el paciente 3 es de Laura y el seed no tiene ingresos
        sin = self.generar('laura', 3, tipo='pti', periodo='pti')
        self.assertEqual(sin.status_code, 409, sin.get_data(as_text=True))
        self.assertIn('ingreso', sin.get_json()['mensaje'])
        self.assertEqual(self.llamar('laura', 'post', '/api/pacientes/3/ingreso').status_code, 201)
        try:
            r = self.generar('laura', 3, tipo='pti', periodo='pti')
            self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
            d = r.get_json()
            self.assertEqual(d['tipo'], 'pti')
            self.assertEqual(d['periodo'], 'pti')
            self.assertIn('## Datos del paciente', d['contenido'])
            self.assertIn('[COMPLETAR', d['contenido'])    # el ingreso todavia no tiene respuestas
            # el control lo marca como pendiente para quien ya tiene ingreso
            fila = {f['id_paciente']: f for f in self.llamar('laura', 'get', '/api/informes/control?mes=2026-06').get_json()['pacientes']}[3]
            self.assertEqual(fila['pti']['estado'], 'borrador')
        finally:
            self.sql('DELETE FROM informes WHERE id > :t', t=self.tope_seed)
            self.sql('DELETE FROM ingreso_respuestas WHERE id_ingreso IN (SELECT id FROM ingresos WHERE id_paciente = 3)')
            self.sql('DELETE FROM ingreso_etapas WHERE id_ingreso IN (SELECT id FROM ingresos WHERE id_paciente = 3)')
            self.sql('DELETE FROM ingresos WHERE id_paciente = 3')

    # --- reglas en la base, sin pasar por la API ---------------------------
    def test_la_base_rechaza_lo_que_la_api_tambien_rechazaria(self):
        def llamar_crear(ter, per_hasta, contenido, tipo='mensual', periodo='2026-08'):
            # CALL y SELECT de las variables OUT tienen que ir por la misma conexion
            from sqlalchemy import text
            from app import db
            with self.app.app_context():
                db.session.execute(
                    text("CALL p_crear_informe(1, :ter, :tipo, :per, '2026-08-01', :hasta, :cont, 'plantilla', NULL, @i, @m)"),
                    dict(ter=ter, tipo=tipo, per=periodo, hasta=per_hasta, cont=contenido))
                fila = db.session.execute(text('SELECT @i, @m')).first()
                db.session.commit()
                return tuple(fila)

        self.assertIn('no tiene asignado', llamar_crear(2, '2026-08-31', 'x')[1])
        self.assertIn('futuro', llamar_crear(1, (hoy() + dt.timedelta(days=3)).isoformat(), 'x')[1])
        self.assertIn('vacio', llamar_crear(1, '2026-08-31', '   ')[1])
        self.assertIn('tipo', llamar_crear(1, '2026-08-31', 'x', tipo='trimestral')[1])
        ok = llamar_crear(1, '2026-08-31', 'x')
        self.assertIsNotNone(ok[0], ok)

    def test_escritura_minima_sigue_llegando_a_la_fk(self):
        # tests/db inserta (id_paciente, id_terapeuta, periodo) con un paciente inexistente
        # y espera una violacion de FK (1452/1216), no un error de columna sin valor.
        from sqlalchemy.exc import DBAPIError
        with self.assertRaises(DBAPIError) as ctx:
            self.sql("INSERT INTO informes (id_paciente, id_terapeuta, periodo) VALUES (999, 1, '2026-T3')")
        self.assertIn(ctx.exception.orig.args[0], (1452, 1216))


if __name__ == '__main__':
    unittest.main()

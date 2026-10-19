"""
tests/nube/test_ingreso_api.py — flujo de ingreso e historia clinica (Entrega 4).

seed.sql: paciente 1, 3 -> Laura; 2 -> Diego; 4 dado de baja. Cada flujo
completo se hace sobre un paciente NUEVO (alta por la API, asignado a Laura)
para que las pruebas no dependan unas de otras.
"""
import itertools
import unittest

from _base import BaseApi

_numero = itertools.count(1)


class IngresoApi(BaseApi):
    def _paciente_nuevo(self):
        n = next(_numero) + 7000
        r = self.llamar('laura', 'post', '/api/pacientes', json={
            'nombre': 'Ingreso', 'apellido': f'Prueba{n}', 'fecha_nacimiento': '2018-05-04',
            'nro_historia': f'HC-{n}'})
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        return r.get_json()['paciente']['id']

    def _ingreso(self, quien, idp):
        r = self.llamar(quien, 'get', f'/api/pacientes/{idp}/ingreso')
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        return r.get_json()

    def _responder_obligatorios(self, idp, etapa):
        d = self._ingreso('laura', idp)
        campos = next(e for e in d['etapas'] if e['etapa'] == etapa)['campos']
        resp = {}
        for c in campos:
            if c['obligatorio']:
                resp[c['clave']] = ('2026-10-01' if c['tipo'] == 'fecha'
                                    else c['opciones'][0] if c['tipo'] == 'opcion'
                                    else f"Respuesta de {c['clave']}")
        r = self.llamar('laura', 'put', f'/api/pacientes/{idp}/ingreso/etapas/{etapa}', json={'respuestas': resp})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))

    def test_permisos_de_lectura(self):
        d = self._ingreso('laura', 1)
        self.assertIsNone(d['ingreso'])
        self.assertEqual(d['minimo_objetivos'], 3)
        # lectura abierta entre terapeutas (paciente 2 es de Diego)
        self.assertEqual(self.llamar('laura', 'get', '/api/pacientes/2/ingreso').status_code, 200)
        for quien in ('admin', 'rrhh', 'familiar', 'paciente'):
            self.assertEqual(self.llamar(quien, 'get', '/api/pacientes/1/ingreso').status_code, 403, quien)
        self.assertEqual(self.llamar(None, 'get', '/api/pacientes/1/ingreso').status_code, 401)
        self.assertEqual(self.llamar('laura', 'get', '/api/pacientes/999/ingreso').status_code, 404)

    def test_iniciar_y_rechazos(self):
        idp = self._paciente_nuevo()
        # sin asignacion sobre el paciente: la base lo rechaza
        r = self.llamar('diego', 'post', f'/api/pacientes/{idp}/ingreso')
        self.assertEqual(r.status_code, 403, r.get_data(as_text=True))
        # control positivo
        r = self.llamar('laura', 'post', f'/api/pacientes/{idp}/ingreso')
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        d = r.get_json()
        self.assertEqual(d['ingreso']['estado'], 'en_curso')
        self.assertEqual([e['etapa'] for e in d['etapas']], ['carpeta', 'evaluacion', 'entrevista', 'pti'])
        self.assertTrue(all(e['estado'] == 'pendiente' for e in d['etapas']))
        # repetir: 409
        self.assertEqual(self.llamar('laura', 'post', f'/api/pacientes/{idp}/ingreso').status_code, 409)
        # paciente de baja y paciente inexistente
        r = self.llamar('laura', 'post', '/api/pacientes/4/ingreso')
        self.assertEqual(r.status_code, 400)
        self.assertIn('dado de baja', r.get_json()['mensaje'])
        self.assertEqual(self.llamar('laura', 'post', '/api/pacientes/999/ingreso').status_code, 404)
        self.assertEqual(self.llamar('admin', 'post', f'/api/pacientes/{idp}/ingreso').status_code, 403)

    def test_guardar_validaciones_y_permiso(self):
        idp = self._paciente_nuevo()
        self.llamar('laura', 'post', f'/api/pacientes/{idp}/ingreso')
        url = f'/api/pacientes/{idp}/ingreso/etapas/evaluacion'
        # campo de otra etapa, fecha mala, opcion invalida, demasiado largo
        r = self.llamar('laura', 'put', url, json={'respuestas': {'frecuencia': '1 vez por semana'}})
        self.assertEqual((r.status_code, r.get_json()['campo']), (400, 'frecuencia'))
        r = self.llamar('laura', 'put', url, json={'respuestas': {'fecha_evaluacion': '31/12/2026'}})
        self.assertEqual((r.status_code, r.get_json()['campo']), (400, 'fecha_evaluacion'))
        r = self.llamar('laura', 'put', f'/api/pacientes/{idp}/ingreso/etapas/pti', json={'respuestas': {'frecuencia': 'a diario'}})
        self.assertEqual((r.status_code, r.get_json()['campo']), (400, 'frecuencia'))
        r = self.llamar('laura', 'put', url, json={'respuestas': {'motivo_consulta': 'x' * 4001}})
        self.assertEqual((r.status_code, r.get_json()['campo']), (400, 'motivo_consulta'))
        self.assertEqual(self.llamar('laura', 'put', url, json={'respuestas': 'no'}).status_code, 400)
        self.assertEqual(self.llamar('laura', 'put', f'/api/pacientes/{idp}/ingreso/etapas/otra', json={'respuestas': {}}).status_code, 404)
        # quien no tiene asignado al paciente no escribe
        r = self.llamar('diego', 'put', url, json={'respuestas': {'motivo_consulta': 'intento ajeno'}})
        self.assertEqual(r.status_code, 403, r.get_data(as_text=True))
        # control positivo + persistencia + la etapa pasa a en_curso
        r = self.llamar('laura', 'put', url, json={'respuestas': {'motivo_consulta': 'Dificultad en la escritura'}})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        etapa = next(e for e in r.get_json()['etapas'] if e['etapa'] == 'evaluacion')
        self.assertEqual(etapa['estado'], 'en_curso')
        valor = next(c['valor'] for c in etapa['campos'] if c['clave'] == 'motivo_consulta')
        self.assertEqual(valor, 'Dificultad en la escritura')
        # un valor vacio borra la respuesta
        r = self.llamar('laura', 'put', url, json={'respuestas': {'motivo_consulta': '  '}})
        etapa = next(e for e in r.get_json()['etapas'] if e['etapa'] == 'evaluacion')
        self.assertIsNone(next(c['valor'] for c in etapa['campos'] if c['clave'] == 'motivo_consulta'))
        # sin ingreso iniciado
        self.assertEqual(self.llamar('laura', 'put', '/api/pacientes/1/ingreso/etapas/pti', json={'respuestas': {}}).status_code, 404)

    def test_cerrar_reabrir_y_completar(self):
        idp = self._paciente_nuevo()
        self.llamar('laura', 'post', f'/api/pacientes/{idp}/ingreso')
        base = f'/api/pacientes/{idp}/ingreso'
        # cerrar sin los obligatorios
        r = self.llamar('laura', 'post', f'{base}/etapas/carpeta/cierre')
        self.assertEqual(r.status_code, 400)
        self.assertIn('Faltan completar', r.get_json()['mensaje'])
        # completar con todo pendiente
        r = self.llamar('laura', 'post', f'{base}/completado')
        self.assertEqual(r.status_code, 400)
        self.assertIn('Faltan cerrar 4 etapa', r.get_json()['mensaje'])
        # control positivo: con obligatorios cierra; cerrada no se modifica
        self._responder_obligatorios(idp, 'carpeta')
        r = self.llamar('laura', 'post', f'{base}/etapas/carpeta/cierre')
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        r = self.llamar('laura', 'put', f'{base}/etapas/carpeta', json={'respuestas': {'medicacion': 'Ninguna'}})
        self.assertEqual(r.status_code, 409)
        self.assertEqual(self.llamar('laura', 'post', f'{base}/etapas/carpeta/cierre').status_code, 409)
        # reabrir: solo la asignada, y solo si estaba cerrada
        self.assertEqual(self.llamar('diego', 'post', f'{base}/etapas/carpeta/reapertura').status_code, 403)
        self.assertEqual(self.llamar('laura', 'post', f'{base}/etapas/carpeta/reapertura').status_code, 200)
        self.assertEqual(self.llamar('laura', 'post', f'{base}/etapas/carpeta/reapertura').status_code, 409)
        self.assertEqual(self.llamar('laura', 'post', f'{base}/etapas/carpeta/cierre').status_code, 200)
        for etapa in ('evaluacion', 'entrevista', 'pti'):
            self._responder_obligatorios(idp, etapa)
            self.assertEqual(self.llamar('laura', 'post', f'{base}/etapas/{etapa}/cierre').status_code, 200, etapa)
        # etapas cerradas pero sin objetivos fijados
        r = self.llamar('laura', 'post', f'{base}/completado')
        self.assertEqual(r.status_code, 400)
        self.assertIn('al menos 3 objetivos', r.get_json()['mensaje'])
        self.assertEqual(self.llamar('laura', 'get', f'/api/pacientes/{idp}/historia-clinica').status_code, 404)
        for i in range(3):
            r = self.llamar('laura', 'post', '/api/objetivos', json={'id_paciente': idp, 'descripcion': f'Objetivo de ingreso {i} del paciente {idp}'})
            self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        # completar: otro terapeuta no puede; la asignada si
        self.assertEqual(self.llamar('diego', 'post', f'{base}/completado').status_code, 403)
        r = self.llamar('laura', 'post', f'{base}/completado')
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(r.get_json()['ingreso']['estado'], 'completado')
        # completado: no se modifica ni se reabre ni se vuelve a completar
        self.assertEqual(self.llamar('laura', 'put', f'{base}/etapas/pti', json={'respuestas': {'estrategias': 'otra'}}).status_code, 409)
        self.assertEqual(self.llamar('laura', 'post', f'{base}/etapas/pti/reapertura').status_code, 409)
        self.assertEqual(self.llamar('laura', 'post', f'{base}/completado').status_code, 409)
        # historia clinica
        r = self.llamar('diego', 'get', f'/api/pacientes/{idp}/historia-clinica')  # lectura abierta
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        h = r.get_json()
        self.assertEqual(len(h['objetivos']), 3)
        self.assertEqual([s['etapa'] for s in h['secciones']], ['carpeta', 'evaluacion', 'entrevista', 'pti'])
        self.assertTrue(all(s['campos'] for s in h['secciones']))
        self.assertIn('diagnostico', h['paciente'])
        self.assertEqual(self.llamar('rrhh', 'get', f'/api/pacientes/{idp}/historia-clinica').status_code, 403)
        self.assertEqual(self.llamar('familiar', 'get', f'/api/pacientes/{idp}/historia-clinica').status_code, 403)

    def test_la_copia_no_cambia_si_se_reconfigura_el_formulario(self):
        idp = self._paciente_nuevo()
        self.llamar('laura', 'post', f'/api/pacientes/{idp}/ingreso')
        base = f'/api/pacientes/{idp}/ingreso'
        for etapa in ('carpeta', 'evaluacion', 'entrevista', 'pti'):
            self._responder_obligatorios(idp, etapa)
            self.llamar('laura', 'post', f'{base}/etapas/{etapa}/cierre')
        for i in range(3):
            self.llamar('laura', 'post', '/api/objetivos', json={'id_paciente': idp, 'descripcion': f'Objetivo copia {i} paciente {idp}'})
        self.assertEqual(self.llamar('laura', 'post', f'{base}/completado').status_code, 200)
        antes = self.llamar('laura', 'get', f'/api/pacientes/{idp}/historia-clinica').get_json()
        campo = next(c for s in self.llamar('admin', 'get', '/api/admin/ingreso/campos').get_json()['etapas']
                     for c in s['campos'] if c['clave'] == 'impresion')
        r = self.llamar('admin', 'put', f"/api/admin/ingreso/campos/{campo['id']}", json={'etiqueta': 'Etiqueta nueva'})
        self.assertEqual(r.status_code, 200)
        despues = self.llamar('laura', 'get', f'/api/pacientes/{idp}/historia-clinica').get_json()
        self.assertEqual(antes['secciones'], despues['secciones'])
        self.llamar('admin', 'put', f"/api/admin/ingreso/campos/{campo['id']}", json={'etiqueta': campo['etiqueta']})

    def test_configuracion_del_formulario(self):
        for quien in ('laura', 'rrhh', 'familiar', 'paciente'):
            self.assertEqual(self.llamar(quien, 'get', '/api/admin/ingreso/campos').status_code, 403, quien)
        d = self.llamar('admin', 'get', '/api/admin/ingreso/campos').get_json()
        self.assertEqual([e['etapa'] for e in d['etapas']], ['carpeta', 'evaluacion', 'entrevista', 'pti'])
        self.assertTrue(all(e['campos'] for e in d['etapas']))
        # crear: control positivo y rechazos
        cuerpo = {'etapa': 'pti', 'clave': 'campo_extra', 'etiqueta': 'Campo extra', 'tipo': 'texto'}
        r = self.llamar('admin', 'post', '/api/admin/ingreso/campos', json=cuerpo)
        if r.status_code == 409:   # la base se comparte entre corridas del modulo
            r = self.llamar('admin', 'post', '/api/admin/ingreso/campos', json=dict(cuerpo, clave='campo_extra_2'))
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        id_campo = r.get_json()['campo']['id']
        r = self.llamar('admin', 'post', '/api/admin/ingreso/campos', json=cuerpo)
        self.assertIn(r.status_code, (201, 409))
        for malo in ({'etapa': 'x', 'clave': 'a', 'etiqueta': 'A'},
                     {'etapa': 'pti', 'clave': 'Mal Clave', 'etiqueta': 'A'},
                     {'etapa': 'pti', 'clave': 'sin_etiqueta'},
                     {'etapa': 'pti', 'clave': 'tipo_malo', 'etiqueta': 'A', 'tipo': 'otro'},
                     {'etapa': 'pti', 'clave': 'sin_opciones', 'etiqueta': 'A', 'tipo': 'opcion', 'opciones': ['una sola']}):
            self.assertIn(self.llamar('admin', 'post', '/api/admin/ingreso/campos', json=malo).status_code, (400, 404), malo)
        # el campo nuevo aparece en el formulario de un ingreso y se desactiva
        idp = self._paciente_nuevo()
        self.llamar('laura', 'post', f'/api/pacientes/{idp}/ingreso')
        pti = next(e for e in self._ingreso('laura', idp)['etapas'] if e['etapa'] == 'pti')
        self.assertIn(id_campo, [c['id'] for c in pti['campos']])
        r = self.llamar('admin', 'put', f'/api/admin/ingreso/campos/{id_campo}', json={'activo': False, 'obligatorio': True})
        self.assertEqual(r.status_code, 200)
        pti = next(e for e in self._ingreso('laura', idp)['etapas'] if e['etapa'] == 'pti')
        self.assertNotIn(id_campo, [c['id'] for c in pti['campos']])
        self.assertEqual(self.llamar('admin', 'put', '/api/admin/ingreso/campos/99999', json={'activo': True}).status_code, 404)
        self.assertEqual(self.llamar('admin', 'put', f'/api/admin/ingreso/campos/{id_campo}', json={'activo': 'si'}).status_code, 400)

    def test_procedimiento_directo_ingreso_inexistente(self):
        from sqlalchemy import text
        from app import db
        with self.app.app_context():
            db.session.execute(text("CALL p_completar_ingreso(99999, 1, @ok, @m)"))
            r = db.session.execute(text('SELECT @ok, @m')).first()
            db.session.commit()
        self.assertEqual(tuple(r), (0, 'El ingreso indicado no existe'))


if __name__ == '__main__':
    unittest.main()

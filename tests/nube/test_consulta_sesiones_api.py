"""
tests/nube/test_consulta_sesiones_api.py — consulta de sesiones registradas y
tendencias por objetivo (Entrega 5).

Cada prueba arma su propio paciente (de Laura) con sesiones entre las 04:10 y
las 04:29 de dias pasados, y lo limpia al terminar.
"""
import datetime as dt
import itertools
import unittest

from _base import BaseApi, hoy

_numero = itertools.count(1)
ID_LAURA, ID_DIEGO = 1, 2


def dia(n):
    return (hoy() - dt.timedelta(days=n)).isoformat()


class ConsultaSesionesBase(BaseApi):
    def paciente_nuevo(self):
        n = next(_numero) + 8000
        r = self.llamar('laura', 'post', '/api/pacientes', json={
            'nombre': 'Consulta', 'apellido': f'Prueba{n}', 'fecha_nacimiento': '2018-05-04',
            'nro_historia': f'HC-{n}'})
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        idp = r.get_json()['paciente']['id']
        # La asignacion nace hoy; las sesiones de prueba son de hace meses.
        self.sql('UPDATE asignaciones SET fecha_desde = :d WHERE id_paciente = :p', d=dia(200), p=idp)
        self.addCleanup(self.borrar_paciente, idp)
        return idp

    def borrar_paciente(self, idp):
        self.sql('DELETE e FROM evoluciones e JOIN sesiones s ON s.id = e.id_sesion WHERE s.id_paciente = :p', p=idp)
        self.sql('DELETE FROM sesiones WHERE id_paciente = :p', p=idp)

    def objetivo(self, idp, texto):
        r = self.llamar('laura', 'post', '/api/objetivos', json={'id_paciente': idp, 'descripcion': texto})
        self.assertIn(r.status_code, (200, 201), r.get_data(as_text=True))
        j = r.get_json()
        idobj = (j.get('objetivo') or j)['id']
        # Un objetivo nuevo no puede calificar sesiones anteriores a su alta:
        # se lo "envejece" para que las sesiones de prueba (pasadas) lo admitan.
        self.sql('UPDATE objetivos_terapeuticos SET fecha_creacion = :f WHERE id = :i',
                 f=f'{dia(200)} 00:00:00', i=idobj)
        return idobj

    def sesion(self, idp, fecha, estado='completa', hora='04:10', idter=ID_LAURA):
        self.sql(
            'INSERT INTO sesiones (id_paciente, id_terapeuta, fecha, hora_inicio, hora_fin, estado, ausencia_de) '
            "VALUES (:p, :t, :f, :h, ADDTIME(:h, '00:45:00'), :e, :a)",
            p=idp, t=idter, f=fecha, h=hora, e=estado, a='paciente' if estado == 'ausencia' else None)
        return self.sql('SELECT MAX(id) FROM sesiones WHERE id_paciente = :p', p=idp)[0][0]

    def evolucion(self, id_sesion, id_objetivo, valor):
        self.sql('INSERT INTO evoluciones (id_sesion, id_objetivo, valor) VALUES (:s, :o, :v)',
                 s=id_sesion, o=id_objetivo, v=valor)


class SesionesRegistradasApi(ConsultaSesionesBase):
    URL = '/api/sesiones/registradas'

    def armar(self):
        idp = self.paciente_nuevo()
        obj = self.objetivo(idp, 'Objetivo de consulta')
        s = {
            'completa': self.sesion(idp, dia(10), 'completa', '04:10'),
            'ausencia': self.sesion(idp, dia(9), 'ausencia', '04:11'),
            'incompleta_con': self.sesion(idp, dia(8), 'incompleta', '04:12'),
            'incompleta_sin': self.sesion(idp, dia(7), 'incompleta', '04:13'),
            'futura': self.sesion(idp, dia(-3), 'completa', '04:14'),
        }
        self.evolucion(s['incompleta_con'], obj, 3)
        return idp, s

    def ids(self, r):
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        return [x['id'] for x in r.get_json()['sesiones']]

    def test_solo_entra_lo_ocurrido_y_registrado(self):
        idp, s = self.armar()
        ids = self.ids(self.llamar('laura', 'get', f'{self.URL}?id_paciente={idp}'))
        self.assertEqual(set(ids), {s['completa'], s['ausencia'], s['incompleta_con']})
        # orden: la mas reciente primero
        self.assertEqual(ids, [s['incompleta_con'], s['ausencia'], s['completa']])

    def test_filtro_por_estado(self):
        idp, s = self.armar()
        ids = self.ids(self.llamar('laura', 'get', f'{self.URL}?id_paciente={idp}&estado=ausencia'))
        self.assertEqual(ids, [s['ausencia']])

    def test_rango_de_fechas(self):
        idp, s = self.armar()
        r = self.llamar('laura', 'get', f'{self.URL}?id_paciente={idp}&desde={dia(9)}&hasta={dia(8)}')
        self.assertEqual(set(self.ids(r)), {s['ausencia'], s['incompleta_con']})
        self.assertEqual(self.llamar('laura', 'get', f'{self.URL}?desde={dia(1)}&hasta={dia(5)}').status_code, 400)
        self.assertEqual(self.llamar('laura', 'get', f'{self.URL}?desde={dia(900)}&hasta={dia(1)}').status_code, 400)

    def test_mias_y_todas(self):
        idp, s = self.armar()
        ajena = self.sesion(2, dia(6), 'completa', '04:15', idter=ID_DIEGO)
        self.addCleanup(lambda: self.sql('DELETE FROM sesiones WHERE id = :i', i=ajena))
        mias = self.ids(self.llamar('laura', 'get', f'{self.URL}?desde={dia(11)}'))
        self.assertNotIn(ajena, mias)
        todas = self.llamar('laura', 'get', f'{self.URL}?desde={dia(11)}&terapeuta=todas')
        self.assertIn(ajena, self.ids(todas))
        propia = {x['id']: x['es_propia'] for x in todas.get_json()['sesiones']}
        self.assertTrue(propia[s['completa']])
        self.assertFalse(propia[ajena])

    def test_paginacion(self):
        idp, s = self.armar()
        r = self.llamar('laura', 'get', f'{self.URL}?id_paciente={idp}&por_pagina=2&pagina=2')
        j = r.get_json()
        self.assertEqual((j['total'], j['paginas'], j['pagina']), (3, 2, 2))
        self.assertEqual([x['id'] for x in j['sesiones']], [s['completa']])

    def test_parametros_invalidos_y_permisos(self):
        for q in ('estado=rara', 'terapeuta=nadie', 'pagina=0', 'por_pagina=500', 'id_paciente=abc'):
            self.assertEqual(self.llamar('laura', 'get', f'{self.URL}?{q}').status_code, 400, q)
        for quien in ('rrhh', 'familiar', 'admin'):
            self.assertEqual(self.llamar(quien, 'get', self.URL).status_code, 403, quien)

    def test_trae_companero_de_dupla_y_paciente(self):
        idp, s = self.armar()
        x = self.llamar('laura', 'get', f'{self.URL}?id_paciente={idp}').get_json()['sesiones'][0]
        self.assertIn('nombre_completo', x['paciente'])
        self.assertIn('companero', x)
        self.assertIn('tiene_evolucion', x)


class TendenciasApi(ConsultaSesionesBase):
    def armar(self):
        idp = self.paciente_nuevo()
        o = {k: self.objetivo(idp, f'Objetivo {k}') for k in 'ABCD'}
        # periodo actual (30 dias): 6 sesiones; anterior: 3 sesiones
        valores = {
            24: (1, 3, 5, 2), 20: (1, 3, 5, 3), 15: (2, 3, 4, 3),
            10: (4, 3, 2, None), 5: (5, 3, 1, None), 1: (5, 3, 1, None),
            35: (2, 3, 1, None), 40: (2, 3, 1, None), 45: (2, 3, 1, None),
        }
        for i, (atras, vals) in enumerate(sorted(valores.items(), reverse=True)):
            sid = self.sesion(idp, dia(atras), 'completa', f'04:{20 + i}')
            for k, v in zip('ABCD', vals):
                if v is not None:
                    self.evolucion(sid, o[k], v)
        return idp, o

    def pedir(self, idp, dias=30, quien='laura'):
        return self.llamar(quien, 'get', f'/api/pacientes/{idp}/tendencias?dias={dias}')

    def test_tendencia_y_cambio_por_objetivo(self):
        idp, o = self.armar()
        r = self.pedir(idp)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        j = r.get_json()
        por = {x['id']: x for x in j['objetivos']}
        self.assertEqual(por[o['A']]['tendencia'], 'mejora')
        self.assertEqual(por[o['B']]['tendencia'], 'se_mantiene')
        self.assertEqual(por[o['C']]['tendencia'], 'retrocede')
        self.assertEqual(por[o['D']]['tendencia'], 'sin_datos')   # solo 3 calificaciones
        self.assertEqual(por[o['A']]['cambio'], 'mejoro')
        self.assertEqual((por[o['A']]['nivel_anterior'], por[o['A']]['nivel_actual']), (2, 3))
        self.assertEqual(por[o['B']]['cambio'], 'igual')
        self.assertEqual(por[o['D']]['cambio'], 'sin_datos')       # sin periodo anterior
        # nada de promedios en la respuesta
        self.assertFalse({'promedio', 'prom_actual', 'porcentaje'} & set(por[o['A']]))
        self.assertEqual(j['periodo']['hasta'], hoy().isoformat())

    def test_periodo_mas_corto_deja_sin_datos(self):
        idp, o = self.armar()
        j = self.pedir(idp, dias=60).get_json()
        por = {x['id']: x for x in j['objetivos']}
        self.assertEqual(por[o['B']]['tendencia'], 'se_mantiene')

    def test_umbral_es_media_escala(self):
        idp = self.paciente_nuevo()
        o = self.objetivo(idp, 'Objetivo umbral')
        # 4 calificaciones: mitades (3,3) y (3,4) -> diferencia 0.5 -> mejora (borde inclusive)
        for i, v in enumerate((3, 3, 3, 4)):
            self.evolucion(self.sesion(idp, dia(20 - i), 'completa', f'04:{20 + i}'), o, v)
        por = {x['id']: x for x in self.pedir(idp).get_json()['objetivos']}
        self.assertEqual(por[o]['tendencia'], 'mejora')
        # 3 (1 por mitad, impar) no alcanza: sin datos
        idp2 = self.paciente_nuevo()
        o2 = self.objetivo(idp2, 'Objetivo corto')
        for i, v in enumerate((1, 3, 5)):
            self.evolucion(self.sesion(idp2, dia(40 - i), 'completa', f'04:{20 + i}'), o2, v)
        por = {x['id']: x for x in self.pedir(idp2).get_json()['objetivos']}
        self.assertEqual(por[o2]['tendencia'], 'sin_datos')

    def test_paciente_sin_calificaciones_lista_sus_objetivos_activos(self):
        idp = self.paciente_nuevo()
        o = self.objetivo(idp, 'Objetivo vacio')
        j = self.pedir(idp).get_json()
        self.assertEqual([(x['id'], x['tendencia'], x['cambio']) for x in j['objetivos']], [(o, 'sin_datos', 'sin_datos')])

    def test_validaciones_y_permisos(self):
        for dias in ('7', 'abc', '0'):
            self.assertEqual(self.pedir(1, dias).status_code, 400, dias)
        self.assertEqual(self.llamar('laura', 'get', '/api/pacientes/999999/tendencias').status_code, 404)
        self.assertEqual(self.pedir(2, 30).status_code, 200)   # lectura abierta entre terapeutas
        for quien in ('rrhh', 'familiar', 'admin'):
            self.assertEqual(self.pedir(1, 30, quien).status_code, 403, quien)


if __name__ == '__main__':
    unittest.main()

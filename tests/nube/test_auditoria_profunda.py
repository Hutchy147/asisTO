"""
tests/nube/test_auditoria_profunda.py — regresiones de la auditoria del 22-oct.

Cubre: fechas extremas que desbordaban (500), filtro de avisos con un paciente
no numerico (500), avisos de cierre de dos sesiones del mismo dia, tildes que
faltaban en los mensajes y la anonimizacion de los datos que van a la IA.
seed.sql: paciente 1 -> Laura, vinculado a la familiar de prueba.
"""
import unittest

from _base import BaseApi, dia_habil_pasado


class AuditoriaProfunda(BaseApi):
    # ---- fechas extremas: 400, nunca 500 ----
    def test_fechas_extremas_dan_400(self):
        casos = [
            ('laura', '/api/sesiones?desde=9999-12-31'),
            ('laura', '/api/sesiones/registradas?desde=9999-12-31'),
            ('laura', '/api/pacientes/1/evolucion?desde=9999-12-31'),
            ('familiar', '/api/familiar/pacientes/1/evolucion?desde=9999-12-31'),
            ('paciente', '/api/paciente/mi-progreso?desde=9999-12-31'),
            ('rrhh', '/api/rrhh/auditoria-accesos?hasta=9999-12-31'),
        ]
        for quien, ruta in casos:
            r = self.llamar(quien, 'get', ruta)
            self.assertEqual(r.status_code, 400, f'{ruta}: {r.get_data(as_text=True)}')
            self.assertIn('fuera del rango', r.get_json()['mensaje'])
        # control positivo: una fecha normal sigue andando
        self.assertEqual(self.llamar('laura', 'get', '/api/sesiones?desde=2026-01-05&hasta=2026-01-09').status_code, 200)

    # ---- filtro de avisos ----
    def test_filtro_de_avisos_con_paciente_no_numerico(self):
        for valor in ('abc', '1e9', '%', '[]'):
            r = self.llamar('familiar', 'get', f'/api/familiar/notificaciones?id_paciente={valor}')
            self.assertEqual(r.status_code, 400, valor)
            self.assertEqual(r.get_json().get('campo'), 'id_paciente')
        self.assertEqual(self.llamar('familiar', 'get', '/api/familiar/notificaciones?id_paciente=1').status_code, 200)

    # ---- dos sesiones del mismo dia: un aviso por cada una ----
    def test_dos_sesiones_del_mismo_dia_avisan_dos_veces(self):
        fecha = dia_habil_pasado(9)
        ids = []
        for hora in ('17:00', '18:00'):
            r = self.llamar('laura', 'post', '/api/sesiones', json={
                'id_paciente': 1, 'fecha': fecha, 'hora_inicio': hora, 'estado': 'incompleta'})
            self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
            ids.append(r.get_json()['sesion']['id'])
        antes = self.sql('SELECT COUNT(*) FROM notificaciones WHERE id_paciente=1')[0][0]
        def cambiar(id_sesion, hora, estado):
            return self.llamar('laura', 'put', f'/api/sesiones/{id_sesion}', json={
                'fecha': fecha, 'hora_inicio': hora, 'estado': estado})
        for id_sesion, hora in zip(ids, ('17:00', '18:00')):
            r = cambiar(id_sesion, hora, 'completa')
            self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        textos = [t for (t,) in self.sql(
            'SELECT mensaje FROM notificaciones WHERE id_paciente=1 ORDER BY id DESC LIMIT 2')]
        despues = self.sql('SELECT COUNT(*) FROM notificaciones WHERE id_paciente=1')[0][0]
        self.assertEqual(despues - antes, 2, textos)
        self.assertTrue(any('a las 17:00' in t for t in textos), textos)
        self.assertTrue(any('a las 18:00' in t for t in textos), textos)
        # reabrir y volver a cerrar la misma sesion no repite el aviso
        self.assertEqual(cambiar(ids[0], '17:00', 'incompleta').status_code, 200)
        self.assertEqual(cambiar(ids[0], '17:00', 'completa').status_code, 200)
        self.assertEqual(self.sql('SELECT COUNT(*) FROM notificaciones WHERE id_paciente=1')[0][0], despues)

    # ---- tildes ----
    def test_tildes_que_faltaban(self):
        from app.utils.textos import acentuar
        self.assertEqual(acentuar('El renglon no puede estar vacio'), 'El renglón no puede estar vacío')
        self.assertEqual(acentuar('La observacion no puede estar vacia.'), 'La observación no puede estar vacía.')
        self.assertEqual(acentuar('el objetivo se creo despues de esa sesion'),
                         'el objetivo se creó después de esa sesión')
        self.assertEqual(acentuar('Vinculo eliminado'), 'Vínculo eliminado')
        self.assertEqual(acentuar('La hora de inicio no es valida.'), 'La hora de inicio no es válida.')
        r = self.llamar('laura', 'post', '/api/sesiones/1/renglones', json={'texto': '   ', 'momento': 'registro'})
        self.assertEqual(r.status_code, 400)
        self.assertIn('renglón', r.get_json()['mensaje'])

    # ---- datos para la IA: sin nombre, sin romper otras palabras ----
    def test_anonimizacion_por_palabra_y_sin_tildes(self):
        from app.services.informes_generador import _sin_nombre
        nombres = ['Ana', 'Paz', 'Lucia']
        texto = 'Ana trabajó toda la semana; es capaz de esperar. Lucía y ANA PAZ. Analizar.'
        limpio = _sin_nombre(texto, nombres)
        self.assertNotRegex(limpio.lower(), r'\b(ana|paz|lucia|lucía)\b')
        for palabra in ('semana', 'capaz', 'Analizar'):
            self.assertIn(palabra, limpio)


if __name__ == '__main__':
    unittest.main()

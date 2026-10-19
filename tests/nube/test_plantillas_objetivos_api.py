"""
tests/nube/test_plantillas_objetivos_api.py — plantillas de objetivos por area (Entrega 5).
El administrador cura el catalogo, el terapeuta lo lee; el resto no entra.
Cada prueba borra lo que crea (areas 'Zz Prueba ...').
"""
import unittest

from _base import BaseApi

URL = '/api/plantillas-objetivos'


class PlantillasObjetivosApi(BaseApi):
    def limpiar(self):
        self.sql("DELETE FROM plantillas_objetivos WHERE area LIKE 'Zz Prueba%'")

    def setUp(self):
        self.limpiar()
        self.addCleanup(self.limpiar)

    def crear(self, area='Zz Prueba A', descripcion='Texto de prueba', quien='admin'):
        return self.llamar(quien, 'post', URL, json={'area': area, 'descripcion': descripcion})

    def test_terapeuta_y_admin_leen_agrupado_por_area(self):
        self.assertEqual(self.crear().status_code, 201)
        for quien in ('laura', 'admin'):
            r = self.llamar(quien, 'get', URL)
            self.assertEqual(r.status_code, 200, quien)
            d = r.get_json()
            areas = [a['area'] for a in d['areas']]
            self.assertIn('Zz Prueba A', areas)
            self.assertEqual(areas, sorted(areas, key=str.lower))
            self.assertEqual(d['total'], sum(len(a['plantillas']) for a in d['areas']))

    def test_otros_roles_no_leen_ni_escriben(self):
        for quien in ('rrhh', 'familiar'):
            self.assertEqual(self.llamar(quien, 'get', URL).status_code, 403, quien)
        self.assertEqual(self.llamar('laura', 'post', URL, json={'area': 'x', 'descripcion': 'y'}).status_code, 403)
        self.assertEqual(self.llamar('laura', 'put', URL + '/1', json={'area': 'x', 'descripcion': 'y'}).status_code, 403)
        self.assertEqual(self.llamar('laura', 'delete', URL + '/1').status_code, 403)

    def test_crear_editar_y_quitar(self):
        r = self.crear(area='  Zz Prueba A  ', descripcion='  Primera versión  ')
        self.assertEqual(r.status_code, 201)
        p = r.get_json()['plantilla']
        self.assertEqual((p['area'], p['descripcion']), ('Zz Prueba A', 'Primera versión'))  # recorta y conserva tildes
        r = self.llamar('admin', 'put', f"{URL}/{p['id']}", json={'area': 'Zz Prueba B', 'descripcion': 'Segunda'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()['plantilla']['area'], 'Zz Prueba B')
        r = self.llamar('admin', 'delete', f"{URL}/{p['id']}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.sql(f"SELECT COUNT(*) FROM plantillas_objetivos WHERE id = {p['id']}")[0][0], 0)

    def test_validaciones_con_mensaje_y_campo(self):
        casos = [
            ({'area': '', 'descripcion': 'x'}, 'área es obligatoria', 'area'),
            ({'area': '   ', 'descripcion': 'x'}, 'área es obligatoria', 'area'),
            ({'area': 'Zz Prueba A', 'descripcion': ''}, 'descripción es obligatoria', 'descripcion'),
            ({'area': 'A' * 121, 'descripcion': 'x'}, 'área no puede superar', 'area'),
            ({'area': 'Zz Prueba A', 'descripcion': 'D' * 701}, 'descripción no puede superar', 'descripcion'),
        ]
        for cuerpo, texto, campo in casos:
            r = self.llamar('admin', 'post', URL, json=cuerpo)
            self.assertEqual(r.status_code, 400, cuerpo)
            j = r.get_json()
            self.assertIn(texto, j['mensaje'])
            self.assertEqual(j['campo'], campo)
        # justo en el limite se acepta
        self.assertEqual(self.crear(area='Zz Prueba ' + 'A' * 100, descripcion='D' * 700).status_code, 201)

    def test_no_admite_duplicados_en_el_area(self):
        self.assertEqual(self.crear().status_code, 201)
        r = self.crear()
        self.assertEqual(r.status_code, 409)
        self.assertIn('Ya existe una plantilla igual', r.get_json()['mensaje'])
        # misma descripcion en otra area: permitido
        self.assertEqual(self.crear(area='Zz Prueba B').status_code, 201)
        # editar para igualar a otra: rechazado
        otra = self.crear(area='Zz Prueba A', descripcion='Otra').get_json()['plantilla']
        r = self.llamar('admin', 'put', f"{URL}/{otra['id']}", json={'area': 'Zz Prueba A', 'descripcion': 'Texto de prueba'})
        self.assertEqual(r.status_code, 409)
        # editar sin cambios (misma fila) esta permitido
        r = self.llamar('admin', 'put', f"{URL}/{otra['id']}", json={'area': 'Zz Prueba A', 'descripcion': 'Otra'})
        self.assertEqual(r.status_code, 200)

    def test_inexistente_da_404(self):
        self.assertEqual(self.llamar('admin', 'put', URL + '/999999', json={'area': 'a', 'descripcion': 'b'}).status_code, 404)
        self.assertEqual(self.llamar('admin', 'delete', URL + '/999999').status_code, 404)

    def test_tipos_invalidos_no_rompen(self):
        r = self.llamar('admin', 'post', URL, json={'area': 5, 'descripcion': ['x']})
        self.assertEqual(r.status_code, 400)
        r = self.llamar('admin', 'post', URL, data='no es json')
        self.assertEqual(r.status_code, 400)

    def test_quitar_una_plantilla_no_toca_objetivos_ya_creados(self):
        p = self.crear(descripcion='Texto copiado al objetivo').get_json()['plantilla']
        r = self.llamar('laura', 'post', '/api/objetivos', json={'id_paciente': 1, 'descripcion': p['descripcion']})
        self.assertIn(r.status_code, (200, 201), r.get_data(as_text=True))
        id_obj = (r.get_json().get('objetivo') or r.get_json())['id']
        self.addCleanup(lambda: self.sql(f'DELETE FROM objetivos_terapeuticos WHERE id = {id_obj}'))
        self.assertEqual(self.llamar('admin', 'delete', f"{URL}/{p['id']}").status_code, 200)
        self.assertEqual(self.sql(f'SELECT descripcion FROM objetivos_terapeuticos WHERE id = {id_obj}')[0][0], 'Texto copiado al objetivo')


if __name__ == '__main__':
    unittest.main()

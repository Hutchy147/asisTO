"""
tests/nube/test_cierre_tratamiento_api.py — pausa/alta de tratamiento y
minimo de 3 objetivos activos (Entrega 3, bloque 9).
seed.sql: paciente 1 -> Laura, paciente 2 -> Diego, paciente 4 de baja (alta).
Cada test deja a los pacientes como los encontro.
"""
import unittest

from _base import BaseApi


class CierreTratamientoApi(BaseApi):
    def _estado(self, pid):
        return self.sql(
            'SELECT activo, tipo_cierre, motivo_baja FROM pacientes WHERE id=:i', i=pid)[0]

    def _restaurar(self, pid):
        self.llamar('laura', 'post', f'/api/pacientes/{pid}/reactivacion')

    def _activos(self, pid):
        return self.sql(
            'SELECT id FROM objetivos_terapeuticos WHERE id_paciente=:i AND activo=TRUE ORDER BY id',
            i=pid)

    def _nuevo_objetivo(self, pid, texto):
        r = self.llamar('laura', 'post', '/api/objetivos',
                        json={'id_paciente': pid, 'descripcion': texto})
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        return r.get_json()['objetivo']['id']

    # ---- pausa ----
    def test_pausa_exige_tipo_y_motivo(self):
        for cuerpo, campo in (({}, 'tipo'), ({'tipo': 'x'}, 'tipo'),
                              ({'tipo': 'pausa'}, 'motivo'),
                              ({'tipo': 'pausa', 'motivo': '   '}, 'motivo'),
                              ({'tipo': 'pausa', 'motivo': 'a' * 201}, 'motivo')):
            r = self.llamar('laura', 'post', '/api/pacientes/1/baja', json=cuerpo)
            self.assertEqual((r.status_code, r.get_json()['campo']), (400, campo), cuerpo)
        self.assertEqual(self._estado(1)[0], 1)  # nada se toco

    def test_pausa_no_toca_objetivos_ni_asignacion_y_se_retoma(self):
        antes = len(self._activos(1))
        r = self.llamar('laura', 'post', '/api/pacientes/1/baja',
                        json={'tipo': 'pausa', 'motivo': 'Viaje familiar'})
        try:
            self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
            p = r.get_json()['paciente']
            self.assertEqual((p['activo'], p['tipo_cierre'], p['motivo_baja']),
                             (False, 'pausa', 'Viaje familiar'))
            self.assertEqual(len(self._activos(1)), antes)
            vig = self.sql('SELECT COUNT(*) FROM asignaciones WHERE id_paciente=1 AND fecha_hasta IS NULL')[0][0]
            self.assertEqual(vig, 1)
            # una segunda baja se rechaza
            r2 = self.llamar('laura', 'post', '/api/pacientes/1/baja',
                             json={'tipo': 'pausa', 'motivo': 'otra'})
            self.assertEqual(r2.status_code, 400)
        finally:
            self._restaurar(1)
        s = self._estado(1)
        self.assertEqual((s[0], s[1], s[2]), (1, None, None))

    # ---- alta ----
    def test_alta_archiva_y_cierra_y_marca_tipo(self):
        r = self.llamar('diego', 'post', '/api/pacientes/2/baja', json={'tipo': 'alta'})
        try:
            self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
            j = r.get_json()
            self.assertEqual(j['paciente']['tipo_cierre'], 'alta')
            self.assertGreaterEqual(j['objetivos_archivados'], 1)
            self.assertEqual(len(self._activos(2)), 0)
        finally:
            # el alta no se deshace sola: dejar al paciente reactivado con sus objetivos
            self.llamar('diego', 'post', '/api/pacientes/2/reactivacion')
            self.sql("UPDATE objetivos_terapeuticos SET activo=TRUE, fecha_archivado=NULL "
                     "WHERE id_paciente=2 AND fecha_archivado >= CURDATE()")
        self.assertEqual(self._estado(2)[1], None)

    def test_baja_historica_se_lee_como_alta(self):
        d = self.llamar('laura', 'get', '/api/pacientes/4').get_json()
        self.assertEqual(d['paciente']['tipo_cierre'], 'alta')
        self.assertTrue(d['solo_lectura'])

    # ---- minimo de 3 ----
    def test_no_se_puede_archivar_por_debajo_de_3(self):
        extra = None
        try:
            while len(self._activos(1)) < 3:
                self._nuevo_objetivo(1, f'Relleno minimo {len(self._activos(1))}')
            # con exactamente 3, archivar uno se rechaza (control negativo)
            ids = [f[0] for f in self._activos(1)]
            while len(ids) > 3:
                self.llamar('laura', 'delete', f'/api/objetivos/{ids.pop()}')
            r = self.llamar('laura', 'delete', f'/api/objetivos/{ids[0]}')
            self.assertEqual((r.status_code, r.get_json()['campo']), (400, 'id_objetivo'), r.get_data(as_text=True))
            self.assertEqual(len(self._activos(1)), 3)
            # control positivo: con el reemplazo creado antes, se puede
            extra = self._nuevo_objetivo(1, 'Reemplazo para archivar')
            r = self.llamar('laura', 'delete', f'/api/objetivos/{ids[0]}')
            self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
            self.assertEqual(len(self._activos(1)), 3)
        finally:
            self.sql("UPDATE objetivos_terapeuticos SET activo=TRUE, fecha_archivado=NULL WHERE id=:i",
                     i=ids[0] if 'ids' in dir() else 0)

    def test_detalle_y_listado_informan_cuanto_falta(self):
        d = self.llamar('laura', 'get', '/api/pacientes/1').get_json()
        n = len(d['objetivos_activos'])
        self.assertEqual(d['minimo_objetivos'], 3)
        self.assertEqual(d['faltan_objetivos'], max(0, 3 - n))
        fila = next(x for x in self.llamar('laura', 'get', '/api/pacientes').get_json()['pacientes']
                    if x['id'] == 1)
        self.assertEqual(fila['faltan_objetivos'], max(0, 3 - n))
        self.assertEqual(self.llamar('laura', 'get', '/api/pacientes/4').get_json()['faltan_objetivos'], 0)


if __name__ == '__main__':
    unittest.main()

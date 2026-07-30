"""
tests/backend/test_rbac_mecanismo.py

Verifica que no exista ninguna forma de llegar a un recurso restringido
sin el rol correcto.

IMPORTANTE sobre el alcance: hoy la unica ruta protegida real en produccion
es /auth/me (@requiere_rol() sin argumentos: exige sesion valida, cualquier
rol). Todavia no existe NINGUN endpoint de negocio con un rol especifico
restringido (pacientes, objetivos, sesiones, RRHH no estan implementados).
Por eso _entorno.py registra rutas de prueba TEMPORALES sobre la MISMA app
real, decoradas con el @requiere_rol real importado de app.utils.security
-- no es una reimplementacion propia del RBAC, es la funcion de produccion
ejercitada con datos de prueba. Es la misma tecnica que ya uso Terminal 1
para sus 28 verificaciones (ver ESTADO.md).

Consecuencia honesta para AUDITORIA.md: lo que se puede afirmar hoy es
sobre el MECANISMO (@requiere_rol funciona para cualquier combinacion de
roles que se le pida), no sobre un endpoint de negocio real, porque
ninguno existe todavia. En particular "RRHH no debe llegar a contenido
clinico" y "un familiar no debe ver un paciente no vinculado" no se pueden
probar contra un endpoint real hoy: no hay ningun endpoint que devuelva
contenido clinico ni datos de un paciente por id. Queda como requisito
para cuando existan (Entrega 1 objetivos/sesiones, Entrega 2 RRHH,
Entrega 3 portal familiar).
"""

import unittest

import _entorno as e
from _entorno import (
    RUTA_CONTENIDO_CLINICO, RUTA_CUALQUIER_ROL, RUTA_SOLO_FAMILIAR,
    RUTA_SOLO_PACIENTE, RUTA_SOLO_RRHH, RUTA_SOLO_TERAPEUTA,
)


class TestMecanismoRBAC(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        e.obtener_app()  # fuerza la creacion (y el registro de rutas de prueba) antes del primer request
        cls.usuarios = {}
        for etiqueta, email in e.EMAILS_SEED.items():
            id_usuario, rol, activo = e.obtener_usuario_por_email(email)
            cls.usuarios[etiqueta] = {
                'id': id_usuario, 'rol': rol, 'email': email,
                'token': e.token_valido(id_usuario, rol, email),
            }

    def setUp(self):
        self.cliente = e.cliente()

    def _pedir(self, ruta, etiqueta_usuario=None):
        headers = e.encabezado_auth(self.usuarios[etiqueta_usuario]['token']) if etiqueta_usuario else {}
        return self.cliente.get(ruta, headers=headers)

    # --- Matriz completa: cada ruta restringida contra cada rol ----------

    def test_matriz_rol_correcto_entra_rol_incorrecto_403(self):
        matriz = [
            (RUTA_SOLO_TERAPEUTA, 'terapeuta', True),
            (RUTA_SOLO_TERAPEUTA, 'terapeuta2', True),
            (RUTA_SOLO_TERAPEUTA, 'rrhh', False),
            (RUTA_SOLO_TERAPEUTA, 'familiar', False),
            (RUTA_SOLO_TERAPEUTA, 'paciente', False),
            (RUTA_SOLO_RRHH, 'rrhh', True),
            (RUTA_SOLO_RRHH, 'terapeuta', False),
            (RUTA_SOLO_RRHH, 'familiar', False),
            (RUTA_SOLO_RRHH, 'paciente', False),
            (RUTA_SOLO_FAMILIAR, 'familiar', True),
            (RUTA_SOLO_FAMILIAR, 'familiar2', True),
            (RUTA_SOLO_FAMILIAR, 'terapeuta', False),
            (RUTA_SOLO_FAMILIAR, 'rrhh', False),
            (RUTA_SOLO_PACIENTE, 'paciente', True),
            (RUTA_SOLO_PACIENTE, 'terapeuta', False),
            (RUTA_SOLO_PACIENTE, 'rrhh', False),
            (RUTA_SOLO_PACIENTE, 'familiar', False),
        ]
        for ruta, etiqueta, deberia_entrar in matriz:
            with self.subTest(ruta=ruta, usuario=etiqueta):
                resp = self._pedir(ruta, etiqueta)
                if deberia_entrar:
                    self.assertEqual(resp.status_code, 200, f'{etiqueta} deberia entrar a {ruta}')
                else:
                    self.assertEqual(resp.status_code, 403, f'{etiqueta} NO deberia entrar a {ruta}')
                    self.assertEqual(resp.get_json().get('codigo'), 'rol_no_autorizado')

    def test_rrhh_no_entra_a_la_ruta_de_contenido_clinico_proxy(self):
        """
        Proxy directo del limite duro del CLAUDE.md: una ruta que exige
        cualquier rol MENOS rrhh debe rechazar a rrhh con 403, y aceptar a
        los demas. No hay endpoint real de contenido clinico todavia; esto
        prueba que el mecanismo que lo va a sostener (@requiere_rol
        excluyendo 'rrhh') funciona.
        """
        resp_rrhh = self._pedir(RUTA_CONTENIDO_CLINICO, 'rrhh')
        self.assertEqual(resp_rrhh.status_code, 403)
        self.assertEqual(resp_rrhh.get_json().get('codigo'), 'rol_no_autorizado')

        for etiqueta in ('terapeuta', 'familiar', 'paciente'):
            with self.subTest(usuario=etiqueta):
                resp = self._pedir(RUTA_CONTENIDO_CLINICO, etiqueta)
                self.assertEqual(resp.status_code, 200)

    def test_sin_token_es_401_no_403_en_ruta_restringida(self):
        """
        La distincion 401 vs 403 importa: sin token, el problema es la
        sesion, no el permiso. Si esto diera 403 seria un error de UX
        (el frontend mostraria "no autorizado" en vez de mandar al login),
        pero tambien romperia la lectura correcta de logs de seguridad.
        """
        resp = self._pedir(RUTA_SOLO_RRHH, etiqueta_usuario=None)
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.get_json().get('codigo'), 'token_faltante')

    def test_ruta_sin_roles_especificos_acepta_cualquier_rol_autenticado(self):
        for etiqueta in self.usuarios:
            with self.subTest(usuario=etiqueta):
                resp = self._pedir(RUTA_CUALQUIER_ROL, etiqueta)
                self.assertEqual(resp.status_code, 200)

    def test_token_por_query_string_se_ignora_no_hay_canal_alternativo(self):
        """
        Confirma que obtener_token_del_header no tiene un fallback oculto
        a query string ni a cookies: solo el header Authorization cuenta.
        """
        token = self.usuarios['rrhh']['token']
        resp = self.cliente.get(f'{RUTA_SOLO_RRHH}?token={token}')
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.get_json().get('codigo'), 'token_faltante')

    def test_esquema_bearer_en_minuscula_no_se_acepta(self):
        """
        obtener_token_del_header exige 'Bearer ' con mayuscula exacta. No
        es una vulnerabilidad (falla cerrado: rechaza en vez de aceptar
        algo que no deberia), pero vale dejarlo confirmado por si algun
        cliente HTTP futuro manda el esquema en minuscula por error y el
        401 resultante sorprende en integracion.
        """
        token = self.usuarios['terapeuta']['token']
        resp = self.cliente.get(RUTA_SOLO_TERAPEUTA, headers={'Authorization': f'bearer {token}'})
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.get_json().get('codigo'), 'token_faltante')


if __name__ == '__main__':
    unittest.main()

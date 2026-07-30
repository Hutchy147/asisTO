"""
tests/backend/_entorno.py

Utilidades compartidas por los tests de seguridad del backend (JWT, RBAC,
manejo de errores). Se importa desde cada archivo de test ANTES que
cualquier otra cosa, porque fija la variable de entorno DB_NAME antes de
que se importe config.py -- Config lee el .env una sola vez, al importarse
el modulo, asi que si DB_NAME ya cambio en el entorno para ese momento,
Config apunta a la base de pruebas en vez de a "asisto".

Requiere una base descartable ya armada con:
    cd tests/db/setup
    .\\build_test_db.ps1 -TestDbName asisto_test_backend
    cd ../../../backend
    $env:DB_NAME = "asisto_test_backend"
    .\\venv\\Scripts\\python.exe scripts\\generar_hashes.py --aplicar

Y que el usuario de MySQL de la app (el que este en backend/.env, tipicamente
asisto_app) tenga permisos sobre esa base. Ver AUDITORIA.md, seccion de
metodologia del modulo de autenticacion.

Nunca apunta a "asisto": si DB_NAME no esta seteada, ASISTO_TEST_DB_REQUERIDA
corta la ejecucion en vez de correr contra la base real por accidente.
"""

import base64
import datetime as dt
import json
import os
import sys

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
sys.path.insert(0, BACKEND_DIR)

NOMBRE_DB_TEST = os.environ.setdefault('DB_NAME', 'asisto_test_backend')

if NOMBRE_DB_TEST == 'asisto':
    raise RuntimeError(
        'tests/backend nunca debe correr contra la base real "asisto". '
        'Definir DB_NAME=asisto_test_backend (o similar) antes de importar este modulo.'
    )

import jwt  # noqa: E402
from app import create_app, db  # noqa: E402
from app.models import Usuario  # noqa: E402

CONTRASENA_SEED = 'asisto2026'  # ver backend/scripts/generar_hashes.py

EMAILS_SEED = {
    'terapeuta': 'laura.fernandez@asisto.local',
    'terapeuta2': 'diego.moyano@asisto.local',
    'rrhh': 'silvia.quiroga@asisto.local',
    'familiar': 'marta.ledesma@asisto.local',
    'familiar2': 'jorge.bustos@asisto.local',
    'paciente': 'camila.rios@asisto.local',
}

# Rutas de prueba temporales, compartidas por todos los archivos de test
# que necesiten ejercitar @requiere_rol con distintas combinaciones de rol.
# Se registran UNA sola vez, en obtener_app(), antes de que la app sirva
# ningun request: Flask 3.x prohibe registrar rutas nuevas despues del
# primer request ("the application... has already handled its first
# request"), y como todos los archivos de test comparten el mismo proceso
# de unittest discover, el singleton de app ya habria atendido requests de
# un archivo por el momento en que otro intenta registrar las suyas.
RUTA_SOLO_TERAPEUTA = '/api/_test_rbac/solo_terapeuta'
RUTA_SOLO_RRHH = '/api/_test_rbac/solo_rrhh'
RUTA_SOLO_FAMILIAR = '/api/_test_rbac/solo_familiar'
RUTA_SOLO_PACIENTE = '/api/_test_rbac/solo_paciente'
RUTA_CONTENIDO_CLINICO = '/api/_test_rbac/contenido_clinico'  # proxy: todos menos rrhh
RUTA_CUALQUIER_ROL = '/api/_test_rbac/cualquier_rol_autenticado'

_app = None


def _registrar_rutas_de_prueba(app):
    from app.utils.security import requiere_rol

    @app.route(RUTA_SOLO_TERAPEUTA)
    @requiere_rol('terapeuta')
    def _solo_terapeuta():
        return {'ok': True, 'ruta': 'terapeuta'}

    @app.route(RUTA_SOLO_RRHH)
    @requiere_rol('rrhh')
    def _solo_rrhh():
        return {'ok': True, 'ruta': 'rrhh'}

    @app.route(RUTA_SOLO_FAMILIAR)
    @requiere_rol('familiar')
    def _solo_familiar():
        return {'ok': True, 'ruta': 'familiar'}

    @app.route(RUTA_SOLO_PACIENTE)
    @requiere_rol('paciente')
    def _solo_paciente():
        return {'ok': True, 'ruta': 'paciente'}

    @app.route(RUTA_CONTENIDO_CLINICO)
    @requiere_rol('terapeuta', 'familiar', 'paciente')  # todos MENOS rrhh
    def _contenido_clinico():
        return {'ok': True, 'ruta': 'contenido_clinico_sin_rrhh'}

    @app.route(RUTA_CUALQUIER_ROL)
    @requiere_rol()
    def _cualquier_rol():
        return {'ok': True, 'ruta': 'cualquier_rol'}


def obtener_app():
    """Una sola instancia de la app por proceso de test."""
    global _app
    if _app is None:
        _app = create_app()
        _app.config['TESTING'] = True
        _registrar_rutas_de_prueba(_app)
    return _app


def cliente():
    return obtener_app().test_client()


def obtener_usuario_por_email(email):
    with obtener_app().app_context():
        usuario = Usuario.query.filter_by(email=email).first()
        if usuario is None:
            raise AssertionError(f'No existe el usuario de seed {email!r} en {NOMBRE_DB_TEST}')
        return usuario.id, usuario.rol, usuario.activo


def establecer_activo(id_usuario, activo):
    """Escribe directo en la base de pruebas (nunca en 'asisto')."""
    with obtener_app().app_context():
        usuario = db.session.get(Usuario, id_usuario)
        usuario.activo = activo
        db.session.commit()


def establecer_rol(id_usuario, rol):
    with obtener_app().app_context():
        usuario = db.session.get(Usuario, id_usuario)
        usuario.rol = rol
        db.session.commit()


def restaurar_usuario(id_usuario, activo=True, rol=None):
    with obtener_app().app_context():
        usuario = db.session.get(Usuario, id_usuario)
        usuario.activo = activo
        if rol is not None:
            usuario.rol = rol
        db.session.commit()


# --- Fabricacion de tokens para los ataques ------------------------------

def _secreto_real():
    return obtener_app().config['JWT_SECRET_KEY']


def _algoritmo_real():
    return obtener_app().config['JWT_ALGORITHM']


def token_valido(id_usuario, rol, email, segundos_vida=3600):
    ahora = dt.datetime.now(dt.timezone.utc)
    payload = {
        'sub': str(id_usuario),
        'rol': rol,
        'email': email,
        'iat': ahora,
        'exp': ahora + dt.timedelta(seconds=segundos_vida),
    }
    return jwt.encode(payload, _secreto_real(), algorithm=_algoritmo_real())


def token_expirado(id_usuario, rol, email):
    ahora = dt.datetime.now(dt.timezone.utc)
    payload = {
        'sub': str(id_usuario),
        'rol': rol,
        'email': email,
        'iat': ahora - dt.timedelta(hours=2),
        'exp': ahora - dt.timedelta(hours=1),  # vencio hace una hora
    }
    return jwt.encode(payload, _secreto_real(), algorithm=_algoritmo_real())


def token_firma_alterada(id_usuario, rol, email):
    """Token real, pero se corrompe un caracter de la firma (3er segmento)."""
    valido = token_valido(id_usuario, rol, email)
    cabecera, payload, firma = valido.split('.')
    firma_alterada = ('A' if firma[0] != 'A' else 'B') + firma[1:]
    return f'{cabecera}.{payload}.{firma_alterada}'


def token_firmado_con_otro_secreto(id_usuario, rol, email, secreto_falso='clave-adivinada-por-un-atacante'):
    ahora = dt.datetime.now(dt.timezone.utc)
    payload = {
        'sub': str(id_usuario),
        'rol': rol,
        'email': email,
        'iat': ahora,
        'exp': ahora + dt.timedelta(hours=1),
    }
    return jwt.encode(payload, secreto_falso, algorithm=_algoritmo_real())


def _base64url_sin_relleno(datos_bytes):
    return base64.urlsafe_b64encode(datos_bytes).rstrip(b'=').decode('ascii')


def token_alg_none(id_usuario, rol, email):
    """
    Ataque clasico 'alg: none': token sin firma, header declara alg=none.

    PyJWT solo debe aceptarlo si el servidor pasara algorithms=['none'] (no
    lo hace: decodificar_token fija algorithms=[JWT_ALGORITHM] = ['HS256']).
    Se arma a mano en vez de con jwt.encode porque PyJWT >= 2.x no permite
    alg='none' desde la API publica sin un flag explicito.
    """
    ahora = dt.datetime.now(dt.timezone.utc)
    cabecera = {'alg': 'none', 'typ': 'JWT'}
    payload = {
        'sub': str(id_usuario),
        'rol': rol,
        'email': email,
        'iat': int(ahora.timestamp()),
        'exp': int((ahora + dt.timedelta(hours=1)).timestamp()),
    }
    cabecera_b64 = _base64url_sin_relleno(json.dumps(cabecera).encode('utf-8'))
    payload_b64 = _base64url_sin_relleno(json.dumps(payload).encode('utf-8'))
    return f'{cabecera_b64}.{payload_b64}.'


def token_claims_modificados_sin_resfirmar(token_original, cambios):
    """
    Simula un atacante que intercepta un token real y edita el payload a
    mano (por ejemplo 'rol': 'rrhh') sin poder volver a firmarlo, porque no
    conoce JWT_SECRET_KEY. Rompe la firma: es indistinguible de
    token_firma_alterada para el servidor, y es exactamente el punto.
    """
    cabecera, payload_b64, firma = token_original.split('.')
    relleno = '=' * (-len(payload_b64) % 4)
    payload = json.loads(base64.urlsafe_b64decode(payload_b64 + relleno))
    payload.update(cambios)
    nuevo_payload_b64 = _base64url_sin_relleno(json.dumps(payload).encode('utf-8'))
    return f'{cabecera}.{nuevo_payload_b64}.{firma}'


def encabezado_auth(token):
    return {'Authorization': f'Bearer {token}'}

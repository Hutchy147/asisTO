"""
tests/backend/_entorno.py

Utilidades compartidas por los tests de seguridad del backend (JWT, RBAC,
manejo de errores). Se importa desde cada archivo de test ANTES que
cualquier otra cosa, porque fija la variable de entorno DB_NAME antes de
que se importe config.py -- Config lee el .env una sola vez, al importarse
el modulo, asi que si DB_NAME ya cambio en el entorno para ese momento,
Config apunta a la base de pruebas en vez de a "asisto".

Requiere una base descartable ya armada. Lo normal es dejar que
run_backend_tests.ps1 la arme: elige el nombre segun ASISTO_ROL y exporta
DB_NAME. A mano, para el rol auditoria:
    cd tests/db/setup
    .\\build_test_db.ps1 -TestDbName asisto_test_backend2
    cd ../../../backend
    $env:DB_NAME = "asisto_test_backend2"
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

# Nombre de la base de pruebas SEGUN EL ROL de la terminal.
#
# run_backend_tests.ps1 ya exporta DB_NAME, asi que por el camino normal esto
# no decide nada. Importa para las corridas directas de unittest, que es como
# se itera cuando se esta escribiendo un test.
#
# El nombre era fijo y eso hacia que dos terminales corriendo la suite a la
# vez usaran la MISMA base -- que la suite borra y recrea. Se perdieron
# corridas de las dos partes por esto, y del lado de auditoria aparecieron
# dos tests en rojo que en aislamiento no se reprodujeron.
#
# El mapeo esta duplicado en tests/db/lib/TestHelpers.ps1
# (Get-NombreBaseDePrueba). Si se toca uno hay que tocar el otro. Eso incluye
# el recorte de espacios de _base_por_rol(): los dos comparan el valor
# RECORTADO.
BASES_POR_ROL = {
    'construccion': 'asisto_test_backend',
    'auditoria': 'asisto_test_backend2',
    'apoyo': 'asisto_test_backend3',
}


def _base_por_rol():
    """
    SIN ROL NO SE CORRE: esto levanta, no avisa.

    Es el mismo criterio que Get-NombreBaseDePrueba en PowerShell y por el
    mismo motivo: estos tests escriben y borran filas de su base, y sin saber
    el rol terminarian haciendolo sobre la de otra terminal. Un aviso ya se
    probo y no alcanzo -- paso una sesion entera sin que nadie lo leyera.
    """
    # SE COMPARA RECORTADO, igual que Get-NombreBaseDePrueba y por el mismo
    # motivo: `set VAR=valor && comando` en CMD guarda el espacio previo al
    # `&&`, asi que ASISTO_ROL llega como 'auditoria ' en las tres terminales
    # sin que se note. Sin el recorte, este raise -- que es duro a proposito --
    # frena a las tres por un caracter invisible.
    #
    # MAYUSCULAS: tampoco distinguen (decision del 2026-08-12). 'Auditoria' y
    # 'AUDITORIA' son el rol auditoria. Los tres lugares que leen la variable
    # convergen a insensible, no a estricto: no hay ningun caso donde una
    # mayuscula signifique otra cosa, y rechazar un valor valido cuesta una
    # sesion de trabajo. Del lado de PowerShell el `switch` ya era insensible;
    # este .lower() es lo que hacia falta para que los dos digan lo mismo.
    #
    # Espacios y mayusculas, y nada mas: no se normalizan acentos ni se aceptan
    # abreviaturas. Un valor realmente invalido tiene que seguir levantando.
    rol_como_lo_escribieron = os.environ.get('ASISTO_ROL', '').strip()
    rol = rol_como_lo_escribieron.lower()
    if rol in BASES_POR_ROL:
        return BASES_POR_ROL[rol]

    # Se muestra el valor RECORTADO PERO SIN CAMBIAR DE CAJA: en minusculas
    # mandaria a buscar una diferencia de mayusculas que ya no importa. Un valor
    # de solo espacios queda como '' y cae en "no esta definida".
    motivo = (f'ASISTO_ROL trae un valor desconocido ({rol_como_lo_escribieron!r}).'
              if rol else 'ASISTO_ROL no esta definida.')
    raise RuntimeError(
        f'\n\n{motivo}\n\n'
        'Estos tests escriben y borran filas de su base de pruebas, asi que sin\n'
        "saber el rol de esta terminal no se pueden correr: usarian\n"
        f"'{BASES_POR_ROL['construccion']}', que es la del rol CONSTRUCCION.\n\n"
        'Definir el rol en esta sesion y volver a correr:\n\n'
        '    $env:ASISTO_ROL = "auditoria"      # o "construccion" / "apoyo"\n\n'
        'Lo normal, igual, es no correr unittest a mano sino:\n\n'
        '    cd tests\\backend\n'
        '    .\\run_backend_tests.ps1\n\n'
        'que arma la base, aplica los hashes y exporta DB_NAME por su cuenta.\n'
        'Si preferis un nombre puntual, definir DB_NAME antes de importar:\n\n'
        '    $env:DB_NAME = "mi_base_de_prueba"\n'
    )


# OJO con el orden: la version anterior hacia
#     os.environ.setdefault('DB_NAME', _base_por_rol())
# y Python evalua el argumento SIEMPRE, tambien cuando DB_NAME ya estaba
# puesta. Con un aviso eso solo ensuciaba la salida; ahora que _base_por_rol
# levanta, habria roto el camino normal -- el del runner, que si exporta
# DB_NAME. Se resuelve solo si falta.
_db_name = os.environ.get('DB_NAME')
if not _db_name:
    _db_name = _base_por_rol()
    os.environ['DB_NAME'] = _db_name

NOMBRE_DB_TEST = _db_name

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
        # Las mediciones de tiempo fallan logins decenas de veces desde la misma
        # IP: el limite por IP se apaga (se prueba en tests/nube).
        _app.config['LIMITES_POR_IP'] = {k: (0, 15) for k in _app.config['LIMITES_POR_IP']}
        _registrar_rutas_de_prueba(_app)
    return _app


def cliente():
    # Sin cookies: cada ataque manda exactamente el header que arma.
    return obtener_app().test_client(use_cookies=False)


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


def desbloquear(id_usuario):
    """Pone en cero los intentos fallidos y levanta el bloqueo de la cuenta."""
    with obtener_app().app_context():
        usuario = db.session.get(Usuario, id_usuario)
        usuario.intentos_fallidos = 0
        usuario.bloqueado_hasta = None
        db.session.commit()


def restaurar_sesiones(id_usuario):
    """Deshace la revocacion de un logout de prueba (sesiones_validas_desde)."""
    with obtener_app().app_context():
        usuario = db.session.get(Usuario, id_usuario)
        usuario.sesiones_validas_desde = None
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
        # Con decimales, como los emite la app: un iat redondeado al segundo
        # podria quedar antes de un logout del mismo segundo (revocado).
        'iat': ahora.timestamp(),
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

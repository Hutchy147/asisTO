# backend/config.py
# Configuracion de la app. Todo valor sensible sale del .env, nunca del codigo.

import os
from urllib.parse import quote_plus

from dotenv import load_dotenv

# El .env vive junto a este archivo, no en el cwd desde donde se ejecute
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, '.env'))

# Como generar un valor seguro. Se repite en el mensaje de error y en el
# README para que nadie tenga que buscarlo.
COMANDO_GENERAR_SECRETO = (
    'python -c "import secrets; print(secrets.token_urlsafe(48))"'
)


class ConfigInvalida(RuntimeError):
    """Falta configuracion obligatoria. La app no puede arrancar."""


def _env_int(key, default):
    """Lee un entero del entorno tolerando valores vacios o invalidos."""
    raw = os.getenv(key)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


class Config:
    # --- Flask ---
    # SIN valor por defecto a proposito. Ver Config.validar().
    SECRET_KEY = os.getenv('SECRET_KEY')
    DEBUG = os.getenv('FLASK_DEBUG', '1') == '1'

    # --- JWT ---
    # Tampoco cae en SECRET_KEY si falta: son dos secretos distintos y
    # rotar uno no tiene por que invalidar lo que firma el otro.
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')
    JWT_ACCESS_TOKEN_EXPIRES = _env_int('JWT_ACCESS_TOKEN_EXPIRES', 3600)
    JWT_ALGORITHM = 'HS256'

    # --- Recuperacion de contrasena ---
    # Sin servidor de mail, en desarrollo el enlace de recuperacion se
    # devuelve en la respuesta y se loguea. Por omision sigue a FLASK_DEBUG:
    # en produccion (FLASK_DEBUG=0) la API NUNCA devuelve el token.
    RECUPERACION_MOSTRAR_TOKEN = os.getenv(
        'RECUPERACION_MOSTRAR_TOKEN', os.getenv('FLASK_DEBUG', '1')
    ) == '1'

    # --- Base de datos ---
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = _env_int('DB_PORT', 3306)
    DB_NAME = os.getenv('DB_NAME', 'asisto')
    DB_USER = os.getenv('DB_USER', 'root')
    DB_PASSWORD = os.getenv('DB_PASSWORD', '')

    # quote_plus: las contrasenas con @ o : rompen la URI si no se escapan
    SQLALCHEMY_DATABASE_URI = (
        f'mysql+pymysql://{quote_plus(DB_USER)}:{quote_plus(DB_PASSWORD)}'
        f'@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        # Evita el "MySQL server has gone away" tras periodos de inactividad
        'pool_pre_ping': True,
        'pool_recycle': 3600,
    }

    # --- CORS ---
    # Lista separada por comas. En desarrollo alcanza con el origen de Vite.
    CORS_ORIGINS = [
        origin.strip()
        for origin in os.getenv('CORS_ORIGINS', 'http://localhost:5173').split(',')
        if origin.strip()
    ]

    # --- Secretos obligatorios ---
    # Un default para estos dos seria un secreto conocido y commiteado
    # firmando los JWT de todos: cualquiera que lea el repositorio podria
    # emitir un token valido con rol 'terapeuta'. La app tiene que negarse
    # a arrancar antes que funcionar con un secreto publico.
    SECRETOS_REQUERIDOS = ('SECRET_KEY', 'JWT_SECRET_KEY')

    @classmethod
    def validar(cls):
        """Corta el arranque si falta un secreto. Se llama en create_app()."""
        faltantes = [
            nombre for nombre in cls.SECRETOS_REQUERIDOS
            if not (getattr(cls, nombre, None) or '').strip()
        ]

        if not faltantes:
            return

        raise ConfigInvalida(
            'Falta configuracion obligatoria en backend/.env: '
            + ', '.join(faltantes)
            + '\n\nLa aplicacion no arranca sin estos valores: firman los JWT '
            'y un valor por defecto seria un secreto conocido.\n'
            'Generar uno distinto para cada uno con:\n'
            f'  {COMANDO_GENERAR_SECRETO}\n\n'
            'Si todavia no existe el archivo, copiar backend/.env.example '
            'como backend/.env y completarlo.'
        )

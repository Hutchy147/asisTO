# backend/config.py
# Configuracion de la app. Todo valor sensible sale del .env, nunca del codigo.

import os
from urllib.parse import quote_plus

from dotenv import load_dotenv

# El .env vive junto a este archivo, no en el cwd desde donde se ejecute
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, '.env'))


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
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-inseguro-cambiar-en-env')
    DEBUG = os.getenv('FLASK_DEBUG', '1') == '1'

    # --- JWT ---
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', SECRET_KEY)
    JWT_ACCESS_TOKEN_EXPIRES = _env_int('JWT_ACCESS_TOKEN_EXPIRES', 3600)

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

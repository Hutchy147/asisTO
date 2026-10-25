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


def _env_float(key, default):
    try:
        return float(os.getenv(key, default))
    except (TypeError, ValueError):
        return default


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
    # Sin FLASK_DEBUG en el .env, apagado: el modo debug prende el depurador
    # interactivo de Werkzeug y, por arrastre, que la recuperacion devuelva el
    # token en la respuesta. Desarrollo lo pide explicito (.env.example).
    DEBUG = os.getenv('FLASK_DEBUG', '0') == '1'

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
        'RECUPERACION_MOSTRAR_TOKEN', os.getenv('FLASK_DEBUG', '0')
    ) == '1'

    # --- Informes con IA (Entrega 6) ---
    # Sin proveedor configurado el generador arma el informe con una plantilla
    # que vuelca los datos del periodo: funciona igual y no envia nada afuera.
    # Con proveedor y clave redacta con IA (los datos salen SIN el nombre del
    # paciente). Siempre queda como borrador y lo revisa una persona.
    INFORMES_IA_PROVEEDOR = os.getenv('INFORMES_IA_PROVEEDOR', '').strip().lower()
    INFORMES_IA_API_KEY = os.getenv('INFORMES_IA_API_KEY', '').strip()
    INFORMES_IA_MODELO = os.getenv('INFORMES_IA_MODELO', 'claude-sonnet-5-5').strip()
    INFORMES_IA_TIMEOUT = _env_int('INFORMES_IA_TIMEOUT', 60)
    # Solo para el proveedor 'ollama' (modelo local): direccion del servidor.
    INFORMES_IA_URL = os.getenv('INFORMES_IA_URL', 'http://127.0.0.1:11434').strip().rstrip('/')
    # Ventana de contexto (tokens) y cuanto tiempo queda el modelo cargado en memoria
    # despues de usarlo: sin esto cada informe paga la carga del modelo (5 a 15 s).
    INFORMES_IA_CTX = _env_int('INFORMES_IA_CTX', 8192)
    INFORMES_IA_KEEP_ALIVE = os.getenv('INFORMES_IA_KEEP_ALIVE', '30m').strip()
    # Como "piensa" el modelo local. Valores bajos = mas fiel a los datos y mas
    # repetible; ver docs/api-informes.md. Semilla 0 = distinta en cada corrida.
    INFORMES_IA_TEMPERATURA = _env_float('INFORMES_IA_TEMPERATURA', 0.1)
    INFORMES_IA_REPETICION = _env_float('INFORMES_IA_REPETICION', 1.15)
    INFORMES_IA_SEMILLA = _env_int('INFORMES_IA_SEMILLA', 7)

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

    # --- Seguridad ---
    # La sesion del navegador viaja en una cookie HttpOnly (el JavaScript de
    # la pagina no la puede leer: un XSS no se lleva la sesion). `Secure` la
    # manda solo por HTTPS: por omision va encendido fuera de desarrollo.
    COOKIE_SESION = 'asisto_sesion'
    COOKIE_SEGURA = os.getenv('COOKIE_SEGURA', '0' if DEBUG else '1') == '1'
    # Strict: el navegador no manda la cookie en pedidos que nacen en otro
    # sitio (un enlace o formulario de una pagina de phishing).
    COOKIE_SAMESITE = 'Strict'

    # Tope del cuerpo de una solicitud. El texto mas largo del sistema (un
    # informe) ronda las decenas de KB; 1 MB deja margen y corta abusos.
    MAX_CONTENT_LENGTH = _env_int('MAX_CONTENT_LENGTH', 1024 * 1024)

    # Detras de un proxy inverso (nginx, IIS) request.remote_addr es la IP del
    # proxy. Con N > 0 se confia en los N saltos de X-Forwarded-For para
    # conocer la IP real del cliente (auditoria y limites por IP). En 0 no se
    # confia en esa cabecera: cualquiera podria inventarla.
    PROXIES_CONFIABLES = _env_int('PROXIES_CONFIABLES', 0)

    # Limites por IP de los endpoints publicos: (maximo, minutos). 0 = apagado.
    LIMITES_POR_IP = {
        # Solo cuentan los FALLOS: el bloqueo por cuenta frena a quien prueba
        # claves contra un email; esto, a quien prueba una clave contra muchos.
        'login_fallido': (_env_int('LIMITE_LOGIN_FALLIDOS_POR_IP', 30), 15),
        'recuperar': (_env_int('LIMITE_RECUPERAR_POR_IP', 10), 15),
        'restablecer': (_env_int('LIMITE_RESTABLECER_POR_IP', 20), 15),
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

    # Un secreto corto se puede adivinar por fuerza bruta offline a partir de
    # un JWT cualquiera: con el, se fabrican tokens de cualquier rol.
    LARGO_MINIMO_SECRETO = 32

    @classmethod
    def validar(cls):
        """Corta el arranque si falta un secreto. Se llama en create_app()."""
        faltantes = [
            nombre for nombre in cls.SECRETOS_REQUERIDOS
            if not (getattr(cls, nombre, None) or '').strip()
        ]

        if not faltantes:
            cortos = [
                nombre for nombre in cls.SECRETOS_REQUERIDOS
                if len(getattr(cls, nombre).strip()) < cls.LARGO_MINIMO_SECRETO
            ]
            if cortos:
                raise ConfigInvalida(
                    'Secreto demasiado corto en backend/.env: ' + ', '.join(cortos)
                    + f' (minimo {cls.LARGO_MINIMO_SECRETO} caracteres).\n'
                    f'Generar uno nuevo con:\n  {COMANDO_GENERAR_SECRETO}'
                )
            if cls.SECRET_KEY.strip() == cls.JWT_SECRET_KEY.strip():
                raise ConfigInvalida(
                    'SECRET_KEY y JWT_SECRET_KEY tienen que ser distintos. '
                    f'Generar otro con:\n  {COMANDO_GENERAR_SECRETO}'
                )
            if cls.RECUPERACION_MOSTRAR_TOKEN and not cls.DEBUG:
                # El enlace de recuperacion en la respuesta es una toma de
                # cuenta para cualquiera que conozca un email. Solo desarrollo.
                raise ConfigInvalida(
                    'RECUPERACION_MOSTRAR_TOKEN=1 solo se admite con FLASK_DEBUG=1 '
                    '(desarrollo). En produccion tiene que quedar en 0.'
                )
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

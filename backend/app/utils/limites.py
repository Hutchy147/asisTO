# backend/app/utils/limites.py
#
# Limite de intentos POR DIRECCION IP en los endpoints publicos (login,
# recuperacion y restablecimiento de contrasena).
#
# Complementa al bloqueo POR CUENTA (5 fallos en 15 minutos, en la base): ese
# frena a quien prueba muchas claves contra un email, pero no a quien prueba
# UNA clave comun contra muchos emails ("password spraying") ni a quien pide
# enlaces de recuperacion en masa para molestar. Esto si.
#
# Ventana deslizante en memoria del proceso, protegida con un lock. Con un
# solo proceso (waitress con hilos, que es como se sirve) alcanza; con varios
# procesos cada uno cuenta por su lado y el limite efectivo se multiplica.
# Detras de un proxy inverso hay que configurar PROXIES_CONFIABLES para que
# la IP sea la del cliente y no la del proxy (ver config.py).

import threading
import time
from collections import defaultdict, deque

from flask import current_app, request

from app.utils.errors import ErrorAplicacion

_lock = threading.Lock()
_eventos = defaultdict(deque)   # (regla, ip) -> instantes (time.monotonic)

MENSAJE = ('Demasiados intentos desde esta conexión. Espere unos minutos e '
           'intente nuevamente.')


def _ip():
    return (request.remote_addr or 'desconocida')[:45]


def _limpiar(cola, ventana, ahora):
    while cola and ahora - cola[0] > ventana:
        cola.popleft()


def _regla(nombre):
    """(maximo, ventana_en_segundos) desde la configuracion."""
    maximo, minutos = current_app.config['LIMITES_POR_IP'][nombre]
    return int(maximo), int(minutos) * 60


def verificar(nombre):
    """Lanza 429 si la IP ya agoto la regla. No cuenta este intento."""
    maximo, ventana = _regla(nombre)
    if maximo <= 0:
        return
    ahora = time.monotonic()
    with _lock:
        cola = _eventos[(nombre, _ip())]
        _limpiar(cola, ventana, ahora)
        if len(cola) >= maximo:
            espera = int(ventana - (ahora - cola[0])) + 1
            raise ErrorAplicacion(MENSAJE, http_status=429, encabezados={'Retry-After': str(espera)})


def registrar(nombre):
    """Cuenta un intento de la IP para la regla."""
    maximo, ventana = _regla(nombre)
    if maximo <= 0:
        return
    ahora = time.monotonic()
    with _lock:
        cola = _eventos[(nombre, _ip())]
        _limpiar(cola, ventana, ahora)
        cola.append(ahora)


def consumir(nombre):
    """verificar + registrar: para reglas que cuentan todo intento."""
    verificar(nombre)
    registrar(nombre)


def reiniciar():
    """Solo para pruebas."""
    with _lock:
        _eventos.clear()

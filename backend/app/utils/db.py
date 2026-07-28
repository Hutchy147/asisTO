# backend/app/utils/db.py
#
# Reintento ante deadlock.
#
# El schema serializa las escrituras que compiten sobre el mismo paciente o
# el mismo terapeuta con locks de fila padre (ver NOTA DE CONCURRENCIA en
# schema.sql). En la secuencia que se probo esos locks NO llegan a formar
# un ciclo: las transacciones hacen cola y esperan. Pero "no se formo en la
# secuencia probada" no es "no puede formarse": basta con que dos rutas de
# escritura futuras tomen los mismos locks en orden distinto.
#
# Si el ciclo se forma, InnoDB lo detecta y aborta una de las dos con
# ERROR 1213. Eso NO es un error del usuario ni un bug: es una condicion
# transitoria y reintentable. La transaccion abortada se revierte entera,
# asi que reintentarla es seguro; propagar el error al usuario seria
# mostrarle una falla que se resuelve sola con volver a intentar.
#
# Uso:
#   @reintentar_en_deadlock()
#   def registrar_algo(...):
#       ...
#       db.session.commit()
#
# IMPORTANTE: la funcion decorada tiene que contener la transaccion entera,
# commit incluido. Si el commit queda afuera, el reintento repite solo una
# parte y el resultado es peor que no reintentar.

import logging
import time
from functools import wraps

from sqlalchemy.exc import DBAPIError, OperationalError

from app.utils.errors import ERRNO_DEADLOCK, ERRNO_LOCK_TIMEOUT, obtener_errno

logger = logging.getLogger(__name__)

# Los dos son transitorios y se resuelven reintentando
ERRORES_REINTENTABLES = (ERRNO_DEADLOCK, ERRNO_LOCK_TIMEOUT)


def es_reintentable(error):
    """True si el error es un deadlock o un timeout de lock."""
    return obtener_errno(error) in ERRORES_REINTENTABLES


def reintentar_en_deadlock(intentos=3, espera_inicial=0.05, factor=2.0):
    """
    Reintenta la operacion si InnoDB aborta la transaccion por deadlock.

    Backoff corto y exponencial (50ms, 100ms, ...): un deadlock se resuelve
    en cuanto la otra transaccion termina, que es cuestion de milisegundos.
    Esperar mas solo alarga la respuesta.

    Despues del ultimo intento el error se propaga: si persiste, no es
    transitorio y hay que verlo, no esconderlo.
    """
    def decorador(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Import local: evita un ciclo con app/__init__.py
            from app import db

            espera = espera_inicial

            for intento in range(1, intentos + 1):
                try:
                    return func(*args, **kwargs)
                except (OperationalError, DBAPIError) as error:
                    if not es_reintentable(error):
                        raise

                    # La transaccion ya quedo abortada del lado de MySQL;
                    # hay que descartarla antes de volver a intentar.
                    db.session.rollback()

                    if intento == intentos:
                        logger.error(
                            'Deadlock persistente en %s tras %s intentos',
                            func.__name__, intentos,
                        )
                        raise

                    logger.warning(
                        'Deadlock en %s (intento %s de %s), reintentando en %.0f ms',
                        func.__name__, intento, intentos, espera * 1000,
                    )
                    time.sleep(espera)
                    espera *= factor

        return wrapper
    return decorador

# backend/app/utils/fechas.py
# Ayudas para validar fechas que llegan como texto en la API.

import re

_FORMATO_ISO = re.compile(r'^\s*\d{4}-\d{2}-\d{2}\s*$')


def mensaje_fecha_invalida(valor, etiqueta, mensaje_formato):
    """
    Mensaje para una fecha que no se pudo leer.

    Si el texto tiene la forma AAAA-MM-DD pero el dia no existe (30 de
    febrero, mes 13), decir "formato" confunde: el formato esta bien. En ese
    caso se avisa que la fecha no existe; si no, el mensaje de formato.
    """
    if isinstance(valor, str) and _FORMATO_ISO.match(valor):
        nombre = f'"{etiqueta}" ' if etiqueta else ''
        return f'La fecha {nombre}({valor.strip()}) no existe en el calendario.'
    return mensaje_formato

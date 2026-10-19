# backend/app/utils/textos.py
#
# Los mensajes de los procedimientos almacenados son ASCII (los archivos SQL
# no llevan tildes). Antes de mostrarlos se restituyen las que corresponden.
# La lista es CERRADA a proposito: solo palabras que aparecen en mensajes de
# la base. Una palabra que no esta aca se muestra como viene.

import re

_TILDES = {
    'clinica': 'clínica', 'quedo': 'quedó', 'esta': 'está', 'reabrala': 'reábrala',
    'terapeutico': 'terapéutico', 'terapeutica': 'terapéutica',
    'tambien': 'también', 'minimo': 'mínimo', 'maximo': 'máximo',
    'sesion': 'sesión', 'asignacion': 'asignación', 'dia': 'día',
    'atendio': 'atendió', 'falto': 'faltó', 'quien': 'quién',
    'evolucion': 'evolución', 'descripcion': 'descripción',
    'ninios': 'niños', 'unica': 'única',
}


def acentuar(mensaje):
    """Restituye las tildes de un mensaje ASCII de la base."""
    if not mensaje:
        return mensaje

    def cambiar(m):
        palabra = m.group(0)
        nueva = _TILDES.get(palabra.lower())
        if nueva is None:
            return palabra
        return nueva.capitalize() if palabra[0].isupper() else nueva

    return re.sub(r'[A-Za-z]+', cambiar, mensaje)

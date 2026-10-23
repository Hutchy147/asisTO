# backend/app/utils/textos.py
#
# Los mensajes de los procedimientos almacenados son ASCII (los archivos SQL
# no llevan tildes), y varios mensajes de la capa de aplicacion tambien.
# Antes de salir al cliente se restituyen las tildes que corresponden.
# La lista es CERRADA a proposito: solo palabras que aparecen en mensajes del
# sistema. Una palabra que no esta aca se muestra como viene.
#
# Se aplica en un solo lugar: el `mensaje` de primer nivel de cada respuesta
# JSON (ver acentuar_respuesta en app/__init__.py). Los datos que escribe la
# gente (observaciones, objetivos, nombres) nunca pasan por aca.

import re

_TILDES = {
    'clinica': 'clínica', 'quedo': 'quedó', 'reabrala': 'reábrala',
    'terapeutico': 'terapéutico', 'terapeutica': 'terapéutica',
    'tambien': 'también', 'minimo': 'mínimo', 'maximo': 'máximo',
    'sesion': 'sesión', 'asignacion': 'asignación', 'dia': 'día', 'dias': 'días',
    'atendio': 'atendió', 'falto': 'faltó', 'quien': 'quién',
    'evolucion': 'evolución', 'descripcion': 'descripción',
    'ninios': 'niños', 'unica': 'única', 'area': 'área',
    # Informes (Entrega 6)
    'periodo': 'período', 'version': 'versión', 'correccion': 'corrección',
    'valido': 'válido', 'vacio': 'vacío', 'escribalas': 'escríbalas',
    # Mensajes de acceso, recuperacion y errores generales
    'contrasena': 'contraseña', 'contrasenas': 'contraseñas',
    'autenticacion': 'autenticación', 'recuperacion': 'recuperación',
    'vencio': 'venció', 'genero': 'generó', 'numero': 'número',
    'numeros': 'números', 'todavia': 'todavía', 'ocurrio': 'ocurrió',
    'operacion': 'operación', 'accion': 'acción', 'metodo': 'método',
    'identificacion': 'identificación', 'publicacion': 'publicación',
    'observacion': 'observación', 'creacion': 'creación',
    'relacion': 'relación', 'segun': 'según', 'ultimo': 'último',
    'ultima': 'última', 'telefono': 'teléfono', 'electronico': 'electrónico',
    'politica': 'política', 'diagnostico': 'diagnóstico', 'tenia': 'tenía',
    'existia': 'existía', 'califico': 'calificó', 'mas': 'más',
    'codigo': 'código', 'pagina': 'página', 'razon': 'razón',
    # Barrido de los mensajes del sistema (22-oct): quedaban sin tilde.
    'renglon': 'renglón', 'vacia': 'vacía', 'despues': 'después',
    'limite': 'límite', 'reactivelo': 'reactívelo', 'valida': 'válida',
    'creo': 'creó', 'vinculo': 'vínculo',
    # Seguridad (23-oct)
    'comun': 'común', 'facilmente': 'fácilmente', 'cerro': 'cerró',
    'pagina': 'página',
}

# "esta" se acentua solo cuando es el verbo ("esta cerrada", "no esta
# asignado"), no el demostrativo ("de esta etapa"). Se decide por la palabra
# que sigue.
_ESTA_VERBO = re.compile(
    r'\s+(?:dad[oa]|cerrad[oa]|abiert[oa]|completad[oa]|asignad[oa]|'
    r'vinculad[oa]|archivad[oa]|pausad[oa]|inactiv[oa]|activ[oa]|'
    r'bloquead[oa]|marcad[oa]|publicad[oa]|reemplazad[oa]|finalizad[oa]|'
    r'configurad[oa]|habilitad[oa]|deshabilitad[oa]|vigente|disponible|'
    r'pendiente|en|ya|sin|fuera|por|vacio|vacia|todavia|iniciad[oa]|'
    r'registrad[oa]|publicad[oa])\b',
    re.IGNORECASE,
)


def acentuar(mensaje):
    """Restituye las tildes de un mensaje ASCII del sistema."""
    if not mensaje:
        return mensaje

    def cambiar(m):
        palabra = m.group(0)
        minuscula = palabra.lower()
        if minuscula == 'esta':
            antes = mensaje[:m.start()].rstrip().lower()
            if not (_ESTA_VERBO.match(mensaje, m.end()) or antes.endswith('no')
                    or antes.endswith('ya')):
                return palabra
            nueva = 'está'
        else:
            nueva = _TILDES.get(minuscula)
            if nueva is None:
                return palabra
        return nueva.capitalize() if palabra[0].isupper() else nueva

    return re.sub(r'[A-Za-z]+', cambiar, mensaje)

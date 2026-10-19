# backend/app/services/portal_paciente_service.py
# Portal del paciente (Entrega 6, HDU 10): el paciente ve SUS objetivos y su
# progreso. Solo lectura.
#
# Es la misma vista reducida que recibe el familiar (portal_familiar_service.
# evolucion_reducida): sin diagnostico, sin observaciones, sin nombres de
# terapeutas, sin numero de historia ni obra social, solo sesiones ocurridas, y
# la escala siempre en palabras. Una sola version de la regla de que se recorta.
#
# QUE NO RECIBE: los informes. La HDU 10 es objetivos y progreso propio; los
# informes son un documento del equipo para la familia (HDU 8).
#
# La identidad sale del token, nunca de un parametro: no hay forma de pedir el
# progreso de otra persona porque el endpoint no recibe ningun id.

from flask import g

from app.models import Paciente
from app.services.portal_familiar_service import _resumen_paciente, evolucion_reducida
from app.utils.errors import ErrorAplicacion


def _paciente_actual():
    paciente = Paciente.query.filter_by(id_usuario=g.usuario_actual.id).first()
    if paciente is None:
        raise ErrorAplicacion(
            'Su cuenta no tiene una ficha de paciente asociada. Comuníquese con el centro.',
            http_status=409,
        )
    return paciente


def mi_progreso(desde=None, hasta=None):
    paciente = _paciente_actual()
    datos = evolucion_reducida(paciente.id, desde, hasta)
    # El paciente ve sus objetivos y su gráfico; el detalle por sesión es del
    # portal familiar.
    datos.pop('sesiones', None)
    datos['paciente'] = _resumen_paciente(paciente)
    return datos

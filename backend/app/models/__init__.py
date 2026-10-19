# backend/app/models/__init__.py
#
# Modelos de SQLAlchemy mapeados al schema EXISTENTE.
#
# La fuente de verdad es backend/database/schema.sql, no estos modelos.
# Nunca se corre db.create_all(): el schema tiene triggers, procedimientos,
# columnas generadas y CHECK constraints que SQLAlchemy no puede expresar,
# y regenerarlo desde aca los perderia en silencio.
#
# Si hay que cambiar una tabla: se cambia schema.sql primero y despues el
# modelo. En ese orden.

from app.models.usuario import Usuario
from app.models.perfiles import Familiar, Rrhh, Terapeuta
from app.models.paciente import Paciente
from app.models.objetivo import ObjetivoTerapeutico
from app.models.sesion import Sesion
from app.models.evolucion import Evolucion
from app.models.observacion_rrhh import ObservacionRrhh
from app.models.asignacion import Asignacion
from app.models.auditoria_acceso import AuditoriaAcceso
from app.models.sesion_renglon import SesionRenglon
from app.models.agenda_recurrente import AgendaRecurrente
from app.models.sesion_objetivo import SesionObjetivo
from app.models.familiar_paciente import FamiliarPaciente
from app.models.notificacion import Notificacion, PreferenciaNotificacion
from app.models.plantilla_objetivo import PlantillaObjetivo
from app.models.ingreso import Ingreso, IngresoCampo, IngresoEtapa, IngresoRespuesta
from app.models.informe import Informe

__all__ = [
    'Usuario', 'Terapeuta', 'Rrhh', 'Familiar', 'Paciente',
    'ObjetivoTerapeutico', 'Sesion', 'Evolucion', 'ObservacionRrhh', 'Asignacion',
    'AuditoriaAcceso', 'SesionRenglon', 'AgendaRecurrente',
    'SesionObjetivo', 'FamiliarPaciente', 'Notificacion', 'PreferenciaNotificacion',
    'PlantillaObjetivo', 'Ingreso', 'IngresoCampo', 'IngresoEtapa', 'IngresoRespuesta',
    'Informe',
]

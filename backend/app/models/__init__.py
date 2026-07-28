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

__all__ = ['Usuario', 'Terapeuta', 'Rrhh', 'Familiar', 'Paciente']

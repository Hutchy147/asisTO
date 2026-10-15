# backend/app/models/asignacion.py
#
# Asignacion paciente-terapeuta (HDU 11). Vigente = fecha_hasta IS NULL.
# Las reglas (una sola vigente por par, nada abierto sobre un paciente de
# baja, fecha_hasta >= fecha_desde, y la regla 8 sobre sesiones y evoluciones)
# viven en la base. Este modelo solo lee: las escrituras van por
# p_abrir_asignacion y p_cerrar_asignacion.

from app import db


class Asignacion(db.Model):
    __tablename__ = 'asignaciones'

    id = db.Column(db.Integer, primary_key=True)
    id_terapeuta = db.Column(
        db.Integer, db.ForeignKey('terapeutas.id'), nullable=False
    )
    id_paciente = db.Column(
        db.Integer, db.ForeignKey('pacientes.id'), nullable=False
    )
    fecha_desde = db.Column(db.Date, nullable=False)
    fecha_hasta = db.Column(db.Date, nullable=True)

    @property
    def vigente(self):
        return self.fecha_hasta is None

    def to_dict(self):
        return {
            'id': self.id,
            'id_terapeuta': self.id_terapeuta,
            'id_paciente': self.id_paciente,
            'fecha_desde': self.fecha_desde.isoformat(),
            'fecha_hasta': self.fecha_hasta.isoformat() if self.fecha_hasta else None,
            'vigente': self.vigente,
        }

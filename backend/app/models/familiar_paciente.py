# backend/app/models/familiar_paciente.py
#
# Vinculo familiar-paciente (portal familiar). Solo lectura: las altas y
# bajas van por p_vincular_familiar, p_desvincular_familiar y
# p_crear_familiar_y_vincular.

from app import db


class FamiliarPaciente(db.Model):
    __tablename__ = 'familiares_pacientes'

    id_familiar = db.Column(
        db.Integer, db.ForeignKey('familiares.id'), primary_key=True
    )
    id_paciente = db.Column(
        db.Integer, db.ForeignKey('pacientes.id'), primary_key=True
    )
    fecha_vinculo = db.Column(db.Date, nullable=False)

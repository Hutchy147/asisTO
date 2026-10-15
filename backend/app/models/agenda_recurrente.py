# backend/app/models/agenda_recurrente.py
#
# Plantilla de la agenda semanal (Entrega 3). No es una sesion: sirve para
# generar sesiones futuras. Ver el comentario de la tabla en schema.sql.

from app import db
from app.models.sesion import formatear_hora

NOMBRES_DIA = {1: 'Lunes', 2: 'Martes', 3: 'Miércoles', 4: 'Jueves', 5: 'Viernes'}


class AgendaRecurrente(db.Model):
    __tablename__ = 'agenda_recurrente'

    id = db.Column(db.Integer, primary_key=True)
    id_terapeuta = db.Column(db.Integer, db.ForeignKey('terapeutas.id'), nullable=False)
    id_paciente = db.Column(db.Integer, db.ForeignKey('pacientes.id'), nullable=False)
    dia_semana = db.Column(db.Integer, nullable=False)
    hora_inicio = db.Column(db.Time, nullable=False)
    hora_fin = db.Column(db.Time, nullable=False)
    activo = db.Column(db.Boolean, nullable=False, default=True)
    fecha_creacion = db.Column(db.DateTime, server_default=db.FetchedValue())

    paciente = db.relationship('Paciente')

    def to_dict(self):
        return {
            'id': self.id,
            'id_paciente': self.id_paciente,
            'paciente': (
                f'{self.paciente.nombre} {self.paciente.apellido}'
                if self.paciente else None
            ),
            'dia_semana': self.dia_semana,
            'dia': NOMBRES_DIA.get(self.dia_semana),
            'hora_inicio': formatear_hora(self.hora_inicio),
            'hora_fin': formatear_hora(self.hora_fin),
        }

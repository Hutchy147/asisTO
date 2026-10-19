# backend/app/models/notificacion.py
#
# Avisos del tratamiento para el familiar. Las altas las hace
# p_notificar_paciente; marcar leida y las preferencias las escribe el propio
# familiar desde el servicio (no hay regla de negocio entre medio).

from app import db

TIPOS = ('nueva_sesion', 'informe_generado', 'cambio_objetivo')


class Notificacion(db.Model):
    __tablename__ = 'notificaciones'

    id = db.Column(db.Integer, primary_key=True)
    id_familiar = db.Column(db.Integer, db.ForeignKey('familiares.id'), nullable=False)
    id_paciente = db.Column(db.Integer, db.ForeignKey('pacientes.id'), nullable=False)
    tipo = db.Column(db.String(30), nullable=False)
    mensaje = db.Column(db.String(500), nullable=False)
    leida = db.Column(db.Boolean, nullable=False, default=False)
    fecha = db.Column(db.DateTime, nullable=False)


class PreferenciaNotificacion(db.Model):
    __tablename__ = 'preferencias_notificacion'

    id_familiar = db.Column(db.Integer, db.ForeignKey('familiares.id'), primary_key=True)
    tipo = db.Column(db.String(30), primary_key=True)
    habilitada = db.Column(db.Boolean, nullable=False, default=True)

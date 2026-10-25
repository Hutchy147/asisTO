# backend/app/models/auditoria_acceso.py
# Registro de intentos de login. Solo lectura desde el ORM: las filas las
# inserta p_registrar_acceso.

from app import db

RESULTADOS_ACCESO = ('exitoso', 'fallido', 'bloqueado', 'recuperacion', 'restablecida', 'inactiva')


class AuditoriaAcceso(db.Model):
    __tablename__ = 'auditoria_accesos'

    id = db.Column(db.Integer, primary_key=True)
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    email = db.Column(db.String(180), nullable=False)
    resultado = db.Column(db.Enum(*RESULTADOS_ACCESO, name='resultado'), nullable=False)
    ip = db.Column(db.String(45), nullable=True)
    fecha = db.Column(db.DateTime, nullable=False, server_default=db.FetchedValue())

    def to_dict(self):
        return {
            'id': self.id,
            'id_usuario': self.id_usuario,
            'email': self.email,
            'resultado': self.resultado,
            'fecha': self.fecha.isoformat(sep=' ') if self.fecha else None,
        }

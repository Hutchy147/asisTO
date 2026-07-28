# backend/app/models/perfiles.py
# Perfiles por rol. Cada uno extiende un usuario con los datos propios de
# su rol. La relacion es 1 a 1 (UNIQUE sobre id_usuario en el schema).

from app import db


class Terapeuta(db.Model):
    __tablename__ = 'terapeutas'

    id = db.Column(db.Integer, primary_key=True)
    id_usuario = db.Column(
        db.Integer, db.ForeignKey('usuarios.id'), nullable=False, unique=True
    )
    matricula = db.Column(db.String(50), nullable=False, unique=True)
    especialidad = db.Column(db.String(120), nullable=True)
    nro_licencia = db.Column(db.String(50), nullable=True)

    usuario = db.relationship('Usuario', backref=db.backref('terapeuta', uselist=False))

    def to_dict(self):
        return {
            'id': self.id,
            'matricula': self.matricula,
            'especialidad': self.especialidad,
            'nro_licencia': self.nro_licencia,
        }


class Rrhh(db.Model):
    __tablename__ = 'rrhh'

    id = db.Column(db.Integer, primary_key=True)
    id_usuario = db.Column(
        db.Integer, db.ForeignKey('usuarios.id'), nullable=False, unique=True
    )
    sector = db.Column(db.String(120), nullable=True)
    nro_legajo = db.Column(db.String(50), nullable=False, unique=True)

    usuario = db.relationship('Usuario', backref=db.backref('rrhh', uselist=False))

    def to_dict(self):
        return {
            'id': self.id,
            'sector': self.sector,
            'nro_legajo': self.nro_legajo,
        }


class Familiar(db.Model):
    __tablename__ = 'familiares'

    id = db.Column(db.Integer, primary_key=True)
    id_usuario = db.Column(
        db.Integer, db.ForeignKey('usuarios.id'), nullable=False, unique=True
    )
    parentesco = db.Column(db.String(60), nullable=True)
    telefono = db.Column(db.String(40), nullable=True)

    usuario = db.relationship('Usuario', backref=db.backref('familiar', uselist=False))

    def to_dict(self):
        return {
            'id': self.id,
            'parentesco': self.parentesco,
            'telefono': self.telefono,
        }

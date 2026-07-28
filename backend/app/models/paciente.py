# backend/app/models/paciente.py

from app import db


class Paciente(db.Model):
    """
    Identidad clinica del paciente — regla 5 del CLAUDE.md.

    id_usuario es NULLABLE A PROPOSITO. El login del paciente es opcional:
    un menor existe como registro clinico completo, sin credenciales.

    Por eso nombre, apellido y fecha_nacimiento viven ACA y no en usuarios.
    Esta tabla es la fuente de verdad de quien es el paciente, tenga login
    o no. NO mover esos campos al modelo Usuario.

    Consecuencia practica para el modulo de auth: un paciente con
    id_usuario NULL simplemente no tiene forma de loguear. Eso es el
    comportamiento correcto, no un error a reportar ni un dato faltante
    que haya que completar.
    """

    __tablename__ = 'pacientes'

    id = db.Column(db.Integer, primary_key=True)
    id_usuario = db.Column(
        db.Integer, db.ForeignKey('usuarios.id'), nullable=True, unique=True
    )
    nombre = db.Column(db.String(100), nullable=False)
    apellido = db.Column(db.String(100), nullable=False)
    fecha_nacimiento = db.Column(db.Date, nullable=False)
    diagnostico = db.Column(db.Text, nullable=True)
    nro_historia = db.Column(db.String(30), nullable=False, unique=True)
    activo = db.Column(db.Boolean, nullable=False, default=True)
    fecha_alta = db.Column(db.Date, nullable=False)
    fecha_baja = db.Column(db.Date, nullable=True)

    usuario = db.relationship('Usuario', backref=db.backref('paciente', uselist=False))

    @property
    def nombre_completo(self):
        return f'{self.nombre} {self.apellido}'

    @property
    def tiene_login(self):
        """False para los pacientes sin credenciales. Es un estado valido."""
        return self.id_usuario is not None

    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'apellido': self.apellido,
            'nombre_completo': self.nombre_completo,
            'fecha_nacimiento': self.fecha_nacimiento.isoformat() if self.fecha_nacimiento else None,
            'nro_historia': self.nro_historia,
            'activo': bool(self.activo),
            'tiene_login': self.tiene_login,
        }

    def __repr__(self):
        return f'<Paciente {self.id} {self.nro_historia}>'

# backend/app/models/usuario.py

from app import db

# Los cuatro roles del sistema. Coinciden exactamente con el ENUM de la
# columna usuarios.rol: si se agrega uno, hay que tocar schema.sql tambien.
ROL_TERAPEUTA = 'terapeuta'
ROL_RRHH = 'rrhh'
ROL_FAMILIAR = 'familiar'
ROL_PACIENTE = 'paciente'

ROLES = (ROL_TERAPEUTA, ROL_RRHH, ROL_FAMILIAR, ROL_PACIENTE)


class Usuario(db.Model):
    """
    Credenciales y datos de acceso.

    OJO: esta tabla NO es la fuente de verdad de la identidad clinica del
    paciente. Un paciente puede existir sin ninguna fila aca (regla 5).
    Ver el modelo Paciente.
    """

    __tablename__ = 'usuarios'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    apellido = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(180), nullable=False, unique=True)
    contrasena_hash = db.Column(db.String(255), nullable=False)
    activo = db.Column(db.Boolean, nullable=False, default=True)
    rol = db.Column(db.Enum(*ROLES, name='rol'), nullable=False)

    # --- Campos de seguridad: Entrega 3 ---
    # Existen en el schema y se mapean para no migrar la tabla despues,
    # pero la logica de bloqueo por intentos fallidos y la recuperacion de
    # contrasena NO estan implementadas todavia. No usar estos campos.
    intentos_fallidos = db.Column(db.SmallInteger, nullable=False, default=0)
    bloqueado_hasta = db.Column(db.DateTime, nullable=True)
    token_recuperacion = db.Column(db.String(255), nullable=True)
    token_expira = db.Column(db.DateTime, nullable=True)

    # El valor lo pone la base (DEFAULT CURRENT_TIMESTAMP). Ver el comentario
    # equivalente en app/models/objetivo.py.
    fecha_creacion = db.Column(
        db.DateTime, nullable=False, server_default=db.FetchedValue()
    )

    @property
    def nombre_completo(self):
        return f'{self.nombre} {self.apellido}'

    def to_dict(self):
        """Representacion segura: nunca incluye el hash ni los tokens."""
        return {
            'id': self.id,
            'nombre': self.nombre,
            'apellido': self.apellido,
            'nombre_completo': self.nombre_completo,
            'email': self.email,
            'rol': self.rol,
            'activo': bool(self.activo),
        }

    def __repr__(self):
        return f'<Usuario {self.id} {self.email} ({self.rol})>'

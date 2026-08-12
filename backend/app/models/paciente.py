# backend/app/models/paciente.py

from app import db

# Topes de largo de los campos de texto del paciente.
#
# CADA UNO DE ESTOS NUMEROS VIVE EN TRES LUGARES y los tres se mueven en el
# mismo commit: el VARCHAR de schema.sql, la constante de aca, y el campo del
# formulario en el frontend. No es una precaucion teorica — con
# `objetivos_terapeuticos.descripcion` los tres numeros ya divergieron (180 en
# el formulario, ninguno en el servicio, 500 en la base) y el resultado fue que
# una terapeuta no podia cargar un objetivo de su practica, cortado a mitad de
# frase y sin un solo aviso.
#
# El servicio valida contra estas constantes ANTES de escribir. Sin eso el
# unico limite es el VARCHAR, que llega como errno 1406 con mensaje generico y
# sin marcar el campo.
MAXIMO_CARACTERES_NOMBRE = 100
MAXIMO_CARACTERES_APELLIDO = 100
MAXIMO_CARACTERES_OBRA_SOCIAL = 120
MAXIMO_CARACTERES_NRO_HISTORIA = 30


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
    nombre = db.Column(db.String(MAXIMO_CARACTERES_NOMBRE), nullable=False)
    apellido = db.Column(db.String(MAXIMO_CARACTERES_APELLIDO), nullable=False)
    fecha_nacimiento = db.Column(db.Date, nullable=False)
    diagnostico = db.Column(db.Text, nullable=True)
    # Nullable a proposito: un paciente particular no tiene obra social, y al
    # dar el alta no siempre se conoce. NO es contenido clinico — es dato
    # administrativo, igual que nro_historia.
    #
    # Existe en la base desde la migracion del 2026-08-07 y hasta hoy no
    # estaba mapeada, asi que la aplicacion no la veia. Se mapea ahora porque
    # el modulo de editar paciente la necesita.
    #
    # YA ES EDITABLE (2026-08-12) y ya tiene el tratamiento completo: el
    # numero esta arriba en MAXIMO_CARACTERES_OBRA_SOCIAL y `editar_paciente`
    # lo valida antes de escribir. Queda un limite conocido: si el 1406
    # llegara igual por algun camino que esquive el servicio,
    # CAMPO_POR_FRAGMENTO lo atribuye a `descripcion`, no a este campo. Esta
    # anotado en errors.py.
    obra_social = db.Column(db.String(MAXIMO_CARACTERES_OBRA_SOCIAL), nullable=True)
    nro_historia = db.Column(
        db.String(MAXIMO_CARACTERES_NRO_HISTORIA), nullable=False, unique=True
    )
    activo = db.Column(db.Boolean, nullable=False, default=True)
    # El valor lo pone la base (DEFAULT CURRENT_DATE). Ver el comentario
    # equivalente en app/models/objetivo.py.
    fecha_alta = db.Column(
        db.Date, nullable=False, server_default=db.FetchedValue()
    )
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
        """
        Representacion SIN contenido clinico.

        No incluye diagnostico a proposito: este es el metodo por defecto y
        el default tiene que ser el seguro. Para las pantallas del terapeuta
        esta to_dict_clinico(), que hay que pedir explicitamente.
        """
        return {
            'id': self.id,
            'nombre': self.nombre,
            'apellido': self.apellido,
            'nombre_completo': self.nombre_completo,
            'fecha_nacimiento': self.fecha_nacimiento.isoformat() if self.fecha_nacimiento else None,
            'nro_historia': self.nro_historia,
            'obra_social': self.obra_social,
            'activo': bool(self.activo),
            'tiene_login': self.tiene_login,
            # Desde cuando esta en tratamiento. No es contenido clinico:
            # es la fecha administrativa del alta.
            'fecha_alta': self.fecha_alta.isoformat() if self.fecha_alta else None,
            # NULL mientras el paciente este activo. Va junto a `activo`: sin
            # la fecha, la interfaz puede decir que esta dado de baja pero no
            # desde cuando, y es el dato que la ficha necesita mostrar.
            'fecha_baja': self.fecha_baja.isoformat() if self.fecha_baja else None,
        }

    def to_dict_clinico(self):
        """
        Agrega el diagnostico. Solo para endpoints del rol terapeuta.

        El nombre es explicito para que un uso indebido salte a la vista en
        una revision: RRHH no puede ver contenido clinico (limite duro del
        CLAUDE.md) y este metodo no debe aparecer en su modulo.
        """
        datos = self.to_dict()
        datos['diagnostico'] = self.diagnostico
        return datos

    def __repr__(self):
        return f'<Paciente {self.id} {self.nro_historia}>'

# backend/app/models/objetivo.py

from app import db

# Maximo de objetivos ACTIVOS por paciente (regla 1). La autoridad es el
# trigger trg_objetivos_limite_activos_insert/_update en la base; esta
# constante solo sirve para informar el cupo en las respuestas.
MAXIMO_OBJETIVOS_ACTIVOS = 4

# Largo maximo de la descripcion. Tiene que ser EXACTAMENTE el mismo numero
# que VARCHAR(700) en schema.sql y que MAXIMO_CARACTERES_DESCRIPCION en
# frontend/src/services/objetivosService.js. Si los tres se separan vuelve el
# defecto que encontro el diagnostico del 2026-08-06: tres limites distintos
# —180 en el textarea, ninguno en el servicio, 500 en la base— y el unico que
# se aplicaba de verdad era un atributo HTML.
#
# Esto NO es duplicar una regla de negocio: es el mismo dato escrito donde
# cada capa lo necesita. La diferencia con el limite de 4 activos es que ese
# requiere una consulta para evaluarse —y por eso vive solo en el trigger—,
# mientras que este se evalua con len() sin preguntarle nada a la base.
MAXIMO_CARACTERES_DESCRIPCION = 700


class ObjetivoTerapeutico(db.Model):
    """
    Objetivo terapeutico de un paciente.

    NO se mapea la columna generada `descripcion_activa`. Es STORED y la
    calcula MySQL: si estuviera mapeada, SQLAlchemy intentaria escribirla en
    cada INSERT y la base rechazaria la sentencia. Existe solo para que la
    UNIQUE (id_paciente, descripcion_activa) permita recrear un objetivo
    archivado con la misma descripcion (los NULL no participan de una
    UNIQUE). Ver schema.sql.

    Tampoco se replican aca el limite de 4 activos ni la unicidad de la
    descripcion: los aplica la base, y duplicarlos en Python es exactamente
    la forma en que las dos versiones terminan divergiendo.
    """

    __tablename__ = 'objetivos_terapeuticos'

    id = db.Column(db.Integer, primary_key=True)
    id_paciente = db.Column(
        db.Integer, db.ForeignKey('pacientes.id'), nullable=False
    )
    descripcion = db.Column(
        db.String(MAXIMO_CARACTERES_DESCRIPCION), nullable=False
    )
    activo = db.Column(db.Boolean, nullable=False, default=True)
    # FetchedValue: el valor lo pone la base (DEFAULT CURRENT_TIMESTAMP).
    # Sin esto SQLAlchemy incluye la columna en el INSERT con NULL explicito
    # y MySQL rechaza la fila con "Column 'fecha_creacion' cannot be null":
    # un DEFAULT solo se aplica cuando la columna NO viene en la sentencia.
    fecha_creacion = db.Column(
        db.DateTime, nullable=False, server_default=db.FetchedValue()
    )
    # La escribe el trigger al archivar/desarchivar, no la aplicacion
    fecha_archivado = db.Column(db.DateTime, nullable=True)

    paciente = db.relationship('Paciente', backref='objetivos')

    def to_dict(self):
        return {
            'id': self.id,
            'id_paciente': self.id_paciente,
            'descripcion': self.descripcion,
            'activo': bool(self.activo),
            'fecha_creacion': self.fecha_creacion.isoformat() if self.fecha_creacion else None,
            'fecha_archivado': self.fecha_archivado.isoformat() if self.fecha_archivado else None,
        }

    def __repr__(self):
        return f'<ObjetivoTerapeutico {self.id} paciente={self.id_paciente} activo={self.activo}>'

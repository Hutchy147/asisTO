# backend/app/models/sesion.py

from app import db

ESTADO_COMPLETA = 'completa'
ESTADO_INCOMPLETA = 'incompleta'
ESTADO_AUSENCIA = 'ausencia'

ESTADOS = (ESTADO_COMPLETA, ESTADO_INCOMPLETA, ESTADO_AUSENCIA)

# Estados sobre los que SI se puede cargar evolucion. 'ausencia' queda
# afuera por la regla 2, y quien lo aplica es el trigger de evoluciones:
# esta constante solo sirve para filtrar listados, no para validar.
ESTADOS_CON_EVOLUCION = (ESTADO_COMPLETA, ESTADO_INCOMPLETA)

AUSENCIA_DE_PACIENTE = 'paciente'
AUSENCIA_DE_TERAPEUTA = 'terapeuta'

# Quien falto, solo cuando estado='ausencia'. Eje distinto del estado (ver
# el comentario de la columna en schema.sql): la consistencia entre los
# dos la valida el trigger, esta tupla es solo para no repetir los
# literales.
ORIGENES_AUSENCIA = (AUSENCIA_DE_PACIENTE, AUSENCIA_DE_TERAPEUTA)


def formatear_hora(valor):
    """
    TIME de MySQL a 'HH:MM:SS'.

    Segun el driver, una columna TIME puede llegar como datetime.time o
    como timedelta. Se contemplan los dos para no depender de eso.
    """
    if valor is None:
        return None
    if hasattr(valor, 'isoformat'):
        return valor.isoformat()
    total = int(valor.total_seconds())
    return f'{total // 3600:02d}:{(total % 3600) // 60:02d}:{total % 60:02d}'


class Sesion(db.Model):
    """
    Sesion de terapia.

    La regla 6 (un terapeuta no puede tener dos sesiones solapadas) NO esta
    implementada aca. La aplican p_registrar_sesion y los triggers
    trg_sesiones_solape_insert/_update. Ver CLAUDE.md.
    """

    __tablename__ = 'sesiones'

    id = db.Column(db.Integer, primary_key=True)
    id_terapeuta = db.Column(
        db.Integer, db.ForeignKey('terapeutas.id'), nullable=False
    )
    id_paciente = db.Column(
        db.Integer, db.ForeignKey('pacientes.id'), nullable=False
    )
    fecha = db.Column(db.Date, nullable=False)
    hora_inicio = db.Column(db.Time, nullable=False)
    hora_fin = db.Column(db.Time, nullable=True)
    estado = db.Column(db.Enum(*ESTADOS, name='estado_sesion'), nullable=False)
    # Quien falto. NULL fuera de 'ausencia', obligatorio dentro -- lo aplica
    # el trigger, no el ORM. Es dato de asistencia, no contenido clinico:
    # va en to_dict() sin el guardado de con_notas, a diferencia de notas.
    ausencia_de = db.Column(
        db.Enum(*ORIGENES_AUSENCIA, name='ausencia_de_sesion'), nullable=True
    )
    # notas es CONTENIDO CLINICO. RRHH no puede verlo: no incluirlo en
    # ninguna respuesta de ese modulo (limite duro del CLAUDE.md).
    notas = db.Column(db.Text, nullable=True)
    # DUPLA (Entrega 5): dos sesiones con el mismo id_dupla son UNA dupla
    # terapeutica (una terapeuta, dos ninios, mismo horario). NULL = sesion
    # individual. Las reglas las aplican los triggers y los procedimientos.
    id_dupla = db.Column(db.Integer, nullable=True)
    fecha_registro = db.Column(
        db.DateTime, nullable=False, server_default=db.FetchedValue()
    )

    terapeuta = db.relationship('Terapeuta', backref='sesiones')
    paciente = db.relationship('Paciente', backref='sesiones')

    def to_dict(self, con_notas=True):
        datos = {
            'id': self.id,
            'id_terapeuta': self.id_terapeuta,
            'id_paciente': self.id_paciente,
            'fecha': self.fecha.isoformat() if self.fecha else None,
            'hora_inicio': formatear_hora(self.hora_inicio),
            'hora_fin': formatear_hora(self.hora_fin),
            'estado': self.estado,
            'ausencia_de': self.ausencia_de,
            'id_dupla': self.id_dupla,
            'fecha_registro': self.fecha_registro.isoformat() if self.fecha_registro else None,
        }
        if con_notas:
            datos['notas'] = self.notas
        return datos

    def __repr__(self):
        return f'<Sesion {self.id} {self.fecha} {self.estado}>'

# backend/app/models/evolucion.py

from app import db

VALOR_MINIMO = 1
VALOR_MAXIMO = 5


class Evolucion(db.Model):
    """
    Evolucion de un objetivo dentro de una sesion.

    Las tres reglas que la gobiernan (sesion no ausente, objetivo del mismo
    paciente que la sesion, objetivo no archivado) las aplican los triggers
    trg_evoluciones_validar_insert/_update. Aca no se replican.

    La UNIQUE (id_sesion, id_objetivo) permite que una sesion evalue varios
    objetivos distintos, pero nunca el mismo dos veces.
    """

    __tablename__ = 'evoluciones'

    id = db.Column(db.Integer, primary_key=True)
    id_sesion = db.Column(
        db.Integer, db.ForeignKey('sesiones.id'), nullable=False
    )
    id_objetivo = db.Column(
        db.Integer, db.ForeignKey('objetivos_terapeuticos.id'), nullable=False
    )
    valor = db.Column(db.SmallInteger, nullable=False)
    observaciones = db.Column(db.Text, nullable=True)
    fecha_registro = db.Column(
        db.DateTime, nullable=False, server_default=db.FetchedValue()
    )

    sesion = db.relationship('Sesion', backref='evoluciones')
    objetivo = db.relationship('ObjetivoTerapeutico', backref='evoluciones')

    def to_dict(self):
        return {
            'id': self.id,
            'id_sesion': self.id_sesion,
            'id_objetivo': self.id_objetivo,
            'valor': self.valor,
            'observaciones': self.observaciones,
            'fecha_registro': self.fecha_registro.isoformat() if self.fecha_registro else None,
        }

    def __repr__(self):
        return f'<Evolucion {self.id} sesion={self.id_sesion} objetivo={self.id_objetivo}>'

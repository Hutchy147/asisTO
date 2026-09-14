# backend/app/models/observacion_rrhh.py

from app import db

# Tope del texto. La columna es TEXT (65.535 bytes), asi que esto NO es el
# limite de la base: es el limite de lo razonable para un comentario
# administrativo. Se valida en el servicio para dar un mensaje propio antes
# de que la base reciba algo absurdo.
MAXIMO_CARACTERES_TEXTO = 1000


class ObservacionRrhh(db.Model):
    """
    Observacion TECNICA de RRHH sobre una sesion.

    NO ES CONTENIDO CLINICO y no reemplaza a `sesiones.notas`, que es del
    terapeuta. Son dos campos distintos, de dos personas distintas, sobre el
    mismo hecho: "llego 20 minutos tarde" lo anota RRHH; que hizo el paciente
    en esos 40 minutos lo anota el terapeuta.

    NO MODIFICA LA SESION: es una fila aparte que la referencia. Por eso hay
    un modelo propio y no una columna mas en `Sesion`.

    La escritura pasa SIEMPRE por p_registrar_observacion_rrhh, nunca por
    `db.session.add()` de este modelo: es la convencion del proyecto para
    todo lo que escribe sobre datos ligados a `sesiones`. Este modelo existe
    para LEER.
    """

    __tablename__ = 'observaciones_rrhh'

    id = db.Column(db.Integer, primary_key=True)
    id_sesion = db.Column(
        db.Integer, db.ForeignKey('sesiones.id'), nullable=False
    )
    id_rrhh = db.Column(
        db.Integer, db.ForeignKey('rrhh.id'), nullable=False
    )
    texto = db.Column(db.Text, nullable=False)
    fecha_registro = db.Column(db.DateTime, nullable=False)

    sesion = db.relationship('Sesion', backref=db.backref('observaciones_rrhh', lazy='dynamic'))
    autor = db.relationship('Rrhh')

    def to_dict(self):
        """
        La forma en que viaja al cliente.

        `autor` va con NOMBRE y no solo con id: donde se muestre tiene que
        poder leerse de quien es sin pedir otra cosa. Que una observacion
        administrativa aparezca sin autor al lado de las notas del terapeuta
        es exactamente como se confunde con una nota clinica.
        """
        usuario = self.autor.usuario if self.autor else None
        return {
            'id': self.id,
            'id_sesion': self.id_sesion,
            'texto': self.texto,
            'fecha_registro': self.fecha_registro.isoformat() if self.fecha_registro else None,
            'autor': {
                'id_rrhh': self.id_rrhh,
                'nombre_completo': usuario.nombre_completo if usuario else None,
                'nro_legajo': self.autor.nro_legajo if self.autor else None,
            },
        }

    def __repr__(self):
        return f'<ObservacionRrhh {self.id} sesion={self.id_sesion}>'

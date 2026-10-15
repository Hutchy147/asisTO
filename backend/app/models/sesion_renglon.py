# backend/app/models/sesion_renglon.py
#
# Renglon de notas de campo de una sesion (Entrega 3). Solo lectura desde el
# ORM: se escribe por p_agregar_renglon, p_editar_renglon, p_cerrar_renglon y
# p_borrar_renglon, que son los que aplican las reglas.

from app import db

MOMENTO_PLAN = 'plan'
MOMENTO_REGISTRO = 'registro'
MOMENTOS = (MOMENTO_PLAN, MOMENTO_REGISTRO)
MAXIMO_CARACTERES_RENGLON = 160
MAXIMO_RENGLONES_POR_MOMENTO = 30


class SesionRenglon(db.Model):
    __tablename__ = 'sesion_renglones'

    id = db.Column(db.Integer, primary_key=True)
    id_sesion = db.Column(db.Integer, db.ForeignKey('sesiones.id'), nullable=False)
    momento = db.Column(db.Enum(*MOMENTOS, name='momento'), nullable=False)
    texto = db.Column(db.String(MAXIMO_CARACTERES_RENGLON), nullable=False)
    destacado = db.Column(db.Boolean, nullable=False, default=False)
    cierre = db.Column(db.Enum('hecho', 'descartado', name='cierre'), nullable=True)
    orden = db.Column(db.Integer, nullable=False, default=1)
    fecha_creacion = db.Column(db.DateTime, server_default=db.FetchedValue())

    def to_dict(self):
        return {
            'id': self.id,
            'id_sesion': self.id_sesion,
            'momento': self.momento,
            'texto': self.texto,
            'destacado': bool(self.destacado),
            'cierre': self.cierre,
            'orden': self.orden,
        }

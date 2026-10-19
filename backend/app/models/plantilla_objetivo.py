# backend/app/models/plantilla_objetivo.py
#
# Plantilla de objetivo por area (Entrega 5). Catalogo de textos sugeridos:
# al crear un objetivo se COPIA el texto, no queda ninguna referencia.

from app import db


class PlantillaObjetivo(db.Model):
    __tablename__ = 'plantillas_objetivos'

    id = db.Column(db.Integer, primary_key=True)
    area = db.Column(db.String(120), nullable=False)
    descripcion = db.Column(db.String(700), nullable=False)

    def to_dict(self):
        return {'id': self.id, 'area': self.area, 'descripcion': self.descripcion}

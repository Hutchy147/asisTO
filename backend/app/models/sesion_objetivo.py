# backend/app/models/sesion_objetivo.py
#
# Objetivo que se planea trabajar en una sesion (Entrega 3). Solo lectura
# desde el ORM: se escribe por p_marcar_objetivo_sesion.

from app import db


class SesionObjetivo(db.Model):
    __tablename__ = 'sesion_objetivos'

    id_sesion = db.Column(db.Integer, db.ForeignKey('sesiones.id'), primary_key=True)
    id_objetivo = db.Column(db.Integer, db.ForeignKey('objetivos_terapeuticos.id'), primary_key=True)
    fecha_creacion = db.Column(db.DateTime, server_default=db.FetchedValue())

# backend/app/models/informe.py
#
# Informes del tratamiento (Entrega 6, HDU 5 y 8). Las escrituras van por
# p_crear_informe, p_editar_informe, p_publicar_informe, p_corregir_informe y
# p_descartar_informe: las reglas (solo el terapeuta asignado, un publicado no
# se edita, nada sin resolver al publicar) viven en la base.

from app import db

TIPOS = ('mensual', 'semestral', 'pti')
ESTADOS = ('borrador', 'final', 'reemplazado')


class Informe(db.Model):
    __tablename__ = 'informes'

    id = db.Column(db.Integer, primary_key=True)
    id_paciente = db.Column(db.Integer, db.ForeignKey('pacientes.id'), nullable=False)
    id_terapeuta = db.Column(db.Integer, db.ForeignKey('terapeutas.id'), nullable=False)
    tipo = db.Column(db.String(10), nullable=False)
    periodo = db.Column(db.String(20), nullable=False)
    fecha_desde = db.Column(db.Date, nullable=False)
    fecha_hasta = db.Column(db.Date, nullable=False)
    version = db.Column(db.Integer, nullable=False)
    contenido = db.Column(db.Text, nullable=True)
    contenido_original = db.Column(db.Text, nullable=True)
    generado_con = db.Column(db.String(10), nullable=False)
    proveedor = db.Column(db.String(60), nullable=True)
    estado = db.Column(db.String(12), nullable=False)
    fecha_generacion = db.Column(db.DateTime, nullable=False)
    fecha_edicion = db.Column(db.DateTime, nullable=True)
    fecha_publicacion = db.Column(db.DateTime, nullable=True)

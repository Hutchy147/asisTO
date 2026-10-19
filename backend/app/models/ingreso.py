# backend/app/models/ingreso.py
#
# Flujo de ingreso de un paciente nuevo (Entrega 4). Las escrituras del flujo
# van por p_iniciar_ingreso, p_guardar_ingreso_etapa, p_cerrar_ingreso_etapa,
# p_reabrir_ingreso_etapa y p_completar_ingreso. Los campos del formulario
# (IngresoCampo) los administra el rol admin desde el servicio.

from app import db

ETAPAS = ('carpeta', 'evaluacion', 'entrevista', 'pti')
TIPOS_CAMPO = ('texto', 'texto_largo', 'fecha', 'opcion')


class Ingreso(db.Model):
    __tablename__ = 'ingresos'

    id = db.Column(db.Integer, primary_key=True)
    id_paciente = db.Column(db.Integer, db.ForeignKey('pacientes.id'), nullable=False, unique=True)
    id_terapeuta = db.Column(db.Integer, db.ForeignKey('terapeutas.id'), nullable=False)
    estado = db.Column(db.String(20), nullable=False)
    fecha_inicio = db.Column(db.Date, nullable=False)
    fecha_completado = db.Column(db.DateTime, nullable=True)
    historia_clinica = db.Column(db.JSON, nullable=True)


class IngresoEtapa(db.Model):
    __tablename__ = 'ingreso_etapas'

    id_ingreso = db.Column(db.Integer, db.ForeignKey('ingresos.id'), primary_key=True)
    etapa = db.Column(db.String(20), primary_key=True)
    estado = db.Column(db.String(20), nullable=False)
    fecha_cierre = db.Column(db.DateTime, nullable=True)


class IngresoCampo(db.Model):
    __tablename__ = 'ingreso_campos'

    id = db.Column(db.Integer, primary_key=True)
    etapa = db.Column(db.String(20), nullable=False)
    clave = db.Column(db.String(40), nullable=False)
    etiqueta = db.Column(db.String(150), nullable=False)
    ayuda = db.Column(db.String(300), nullable=True)
    tipo = db.Column(db.String(20), nullable=False)
    opciones = db.Column(db.String(500), nullable=True)
    obligatorio = db.Column(db.Boolean, nullable=False, default=False)
    orden = db.Column(db.Integer, nullable=False, default=100)
    activo = db.Column(db.Boolean, nullable=False, default=True)

    def lista_opciones(self):
        return [o for o in (self.opciones or '').split('|') if o]

    def to_dict(self):
        return {
            'id': self.id,
            'etapa': self.etapa,
            'clave': self.clave,
            'etiqueta': self.etiqueta,
            'ayuda': self.ayuda,
            'tipo': self.tipo,
            'opciones': self.lista_opciones(),
            'obligatorio': bool(self.obligatorio),
            'orden': self.orden,
            'activo': bool(self.activo),
        }


class IngresoRespuesta(db.Model):
    __tablename__ = 'ingreso_respuestas'

    id_ingreso = db.Column(db.Integer, db.ForeignKey('ingresos.id'), primary_key=True)
    id_campo = db.Column(db.Integer, db.ForeignKey('ingreso_campos.id'), primary_key=True)
    valor = db.Column(db.Text, nullable=False)

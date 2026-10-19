# backend/app/services/plantillas_objetivos_service.py
# Plantillas de objetivos por area (Entrega 5).
#
# Las reglas (area y descripcion obligatorias, largos, sin duplicados en el
# area) las aplican los procedimientos de la base. Aca solo se traduce el
# resultado. Lectura: terapeuta (para elegir al crear un objetivo) y
# administrador (que cura el catalogo). El catalogo no es clinico.

import logging

from sqlalchemy import text

from app import db
from app.models import PlantillaObjetivo
from app.utils.db import reintentar_en_deadlock
from app.utils.errors import ErrorAplicacion
from app.utils.textos import acentuar

logger = logging.getLogger(__name__)


def _estado_http(mensaje):
    texto = (mensaje or '').lower()
    if 'no existe' in texto:
        return 404
    if 'ya existe' in texto:
        return 409
    return 400


def _campo(mensaje):
    texto = (mensaje or '').lower()
    if 'area' in texto:
        return 'area'
    if 'descripcion' in texto:
        return 'descripcion'
    return None


def listar_plantillas():
    """-> {areas: [{area, plantillas: [{id, descripcion}]}], total}. Areas en orden alfabetico."""
    filas = PlantillaObjetivo.query.order_by(PlantillaObjetivo.area, PlantillaObjetivo.id).all()
    por_area = {}
    for f in filas:
        por_area.setdefault(f.area, []).append({'id': f.id, 'descripcion': f.descripcion})
    return {
        'areas': [{'area': a, 'plantillas': p} for a, p in sorted(por_area.items(), key=lambda x: x[0].lower())],
        'total': len(filas),
    }


def _cadena(datos, clave):
    valor = datos.get(clave)
    if valor is not None and not isinstance(valor, str):
        raise ErrorAplicacion('El dato indicado no es válido.', campo=clave)
    return valor or ''


def _fallar(mensaje):
    # El estado y el campo se deducen del texto ASCII original, antes de acentuar.
    raise ErrorAplicacion(acentuar(mensaje), http_status=_estado_http(mensaje), campo=_campo(mensaje))


@reintentar_en_deadlock()
def crear_plantilla(datos):
    db.session.execute(
        text('CALL p_crear_plantilla_objetivo(:a, :d, @p_id, @p_mensaje)'),
        {'a': _cadena(datos, 'area'), 'd': _cadena(datos, 'descripcion')},
    )
    id_plantilla, mensaje = db.session.execute(text('SELECT @p_id, @p_mensaje')).first()
    db.session.commit()
    if id_plantilla is None:
        _fallar(mensaje)
    logger.info('Plantilla de objetivo %s creada', id_plantilla)
    return db.session.get(PlantillaObjetivo, id_plantilla).to_dict()


@reintentar_en_deadlock()
def editar_plantilla(id_plantilla, datos):
    db.session.execute(
        text('CALL p_editar_plantilla_objetivo(:i, :a, :d, @p_ok, @p_mensaje)'),
        {'i': id_plantilla, 'a': _cadena(datos, 'area'), 'd': _cadena(datos, 'descripcion')},
    )
    ok, mensaje = db.session.execute(text('SELECT @p_ok, @p_mensaje')).first()
    db.session.commit()
    if not ok:
        _fallar(mensaje)
    db.session.expire_all()
    return db.session.get(PlantillaObjetivo, id_plantilla).to_dict()


@reintentar_en_deadlock()
def quitar_plantilla(id_plantilla):
    db.session.execute(
        text('CALL p_eliminar_plantilla_objetivo(:i, @p_ok, @p_mensaje)'), {'i': id_plantilla},
    )
    ok, mensaje = db.session.execute(text('SELECT @p_ok, @p_mensaje')).first()
    db.session.commit()
    if not ok:
        _fallar(mensaje)
    return acentuar(mensaje)

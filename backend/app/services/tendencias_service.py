# backend/app/services/tendencias_service.py
# Indicadores de tendencia por objetivo (Entrega 5). El criterio (cuantas
# calificaciones hacen falta, el umbral, la comparacion con el periodo
# anterior) vive en p_tendencia_paciente; aca solo se arma el periodo y se
# traduce el resultado. La escala es en palabras: no sale ningun promedio.

import datetime as dt

from sqlalchemy import text

from app import db
from app.services.pacientes_service import obtener_paciente
from app.utils.errors import ErrorAplicacion
from app.utils.textos import acentuar

PERIODOS_VALIDOS = (30, 60, 90, 180)
PERIODO_POR_DEFECTO = 30


def tendencias_de_paciente(id_paciente, dias=None):
    """
    Ultimos `dias` dias (hasta hoy) comparados con los `dias` anteriores.
    Lectura de historia clinica: incluye pacientes dados de baja.
    """
    if dias in (None, ''):
        dias = PERIODO_POR_DEFECTO
    try:
        dias = int(dias)
    except (TypeError, ValueError):
        dias = 0
    if dias not in PERIODOS_VALIDOS:
        raise ErrorAplicacion(
            'El período debe ser de 30, 60, 90 o 180 días.', campo='dias',
        )

    paciente = obtener_paciente(id_paciente, incluir_inactivos=True)
    hasta = dt.date.today()
    desde = hasta - dt.timedelta(days=dias - 1)
    previo_hasta = desde - dt.timedelta(days=1)
    previo_desde = desde - dt.timedelta(days=dias)

    filas = db.session.execute(
        text('CALL p_tendencia_paciente(:id, :desde, :hasta, @p_mensaje)'),
        {'id': paciente.id, 'desde': desde, 'hasta': hasta},
    ).all()
    mensaje = db.session.execute(text('SELECT @p_mensaje')).scalar()
    if mensaje:
        raise ErrorAplicacion(acentuar(mensaje))

    def nivel(valor):
        return int(valor) if valor is not None else None

    return {
        'paciente': {'id': paciente.id, 'nombre_completo': paciente.nombre_completo},
        'dias': dias,
        'periodo': {'desde': desde.isoformat(), 'hasta': hasta.isoformat()},
        'periodo_anterior': {'desde': previo_desde.isoformat(), 'hasta': previo_hasta.isoformat()},
        'objetivos': [
            {
                'id': int(f[0]),
                'descripcion': f[1],
                'activo': bool(f[2]),
                'calificaciones': int(f[3]),
                'calificaciones_anterior': int(f[5]),
                'nivel_actual': nivel(f[4]),
                'nivel_anterior': nivel(f[6]),
                'tendencia': f[7],
                'cambio': f[8],
            }
            for f in filas
        ],
    }

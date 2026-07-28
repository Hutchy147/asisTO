# backend/app/routes/health.py
# Endpoint de diagnostico. Sirve para verificar que la API levanta y si la
# conexion a MySQL esta operativa.

from flask import Blueprint, jsonify
from sqlalchemy import text

from app import db

health_bp = Blueprint('health', __name__)


@health_bp.get('/health')
def health():
    # La API tiene que responder 200 aunque la base todavia no exista:
    # el schema recien se crea mas adelante y el front necesita este ping.
    database_ok = False
    database_error = None
    try:
        db.session.execute(text('SELECT 1'))
        database_ok = True
    except Exception as error:  # noqa: BLE001 - se reporta, no se propaga
        db.session.rollback()
        database_error = str(error.__class__.__name__)

    return jsonify(
        {
            'estado': 'ok',
            'mensaje': 'API AsisTO operativa',
            'database': {
                'conectada': database_ok,
                'error': database_error,
            },
        }
    ), 200

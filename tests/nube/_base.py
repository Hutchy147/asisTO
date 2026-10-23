"""
tests/nube/_base.py

Arnes comun de las pruebas que corren en la nube. Requiere DB_NAME apuntando
a una base descartable armada con build_db.sh; se niega a correr contra
`asisto`. Usa el cliente de pruebas de Flask: no hace falta levantar el
backend.
"""
import datetime as dt
import os
import sys
import unittest

BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
sys.path.insert(0, BACKEND)

if os.environ.get('DB_NAME', 'asisto') == 'asisto':
    raise RuntimeError('Definir DB_NAME con una base descartable (build_db.sh).')

from app import create_app, db  # noqa: E402

CONTRASENA = 'asisto2026'
EMAILS = {
    'laura': 'laura.fernandez@asisto.local',   # terapeuta 1
    'diego': 'diego.moyano@asisto.local',      # terapeuta 2
    'rrhh': 'silvia.quiroga@asisto.local',
    'familiar': 'marta.ledesma@asisto.local',
    'paciente': 'camila.rios@asisto.local',
    'admin': 'admin@asisto.local',
    'jorge': 'jorge.bustos@asisto.local',      # familiar del paciente 2
}


def hoy():
    return dt.date.today()


def dias(n):
    """Fecha de hoy desplazada n dias (negativo = pasado), en ISO."""
    return (hoy() + dt.timedelta(days=n)).isoformat()


def dia_habil_pasado(atras):
    """Un dia de lunes a viernes, `atras` dias o mas hacia el pasado."""
    d = hoy() - dt.timedelta(days=atras)
    while d.weekday() > 4:
        d -= dt.timedelta(days=1)
    return d.isoformat()


class BaseApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config['TESTING'] = False  # que los errores salgan como en produccion
        cls.client = cls.app.test_client()
        cls._tokens = {}

    def token(self, quien):
        if quien not in self._tokens:
            r = self.client.post('/api/auth/login',
                                 json={'email': EMAILS[quien], 'contrasena': CONTRASENA})
            self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
            self._tokens[quien] = r.get_json()['token']
        return self._tokens[quien]

    def llamar(self, quien, metodo, ruta, **kw):
        headers = {}
        if quien:
            headers['Authorization'] = f'Bearer {self.token(quien)}'
        return getattr(self.client, metodo)(ruta, headers=headers, **kw)

    def sql(self, consulta, **params):
        with self.app.app_context():
            from sqlalchemy import text
            res = db.session.execute(text(consulta), params)
            filas = res.fetchall() if res.returns_rows else None
            db.session.commit()
            return filas

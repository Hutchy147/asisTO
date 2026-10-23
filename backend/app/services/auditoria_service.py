# backend/app/services/auditoria_service.py
# Consulta de la auditoria de accesos (solo lectura, rol rrhh). Las filas las
# escribe auth_service via p_registrar_acceso.

import datetime as dt

from sqlalchemy import func

from app import db
from app.models import AuditoriaAcceso
from app.models.auditoria_acceso import RESULTADOS_ACCESO
from app.utils.errors import ErrorAplicacion
from app.utils.fechas import mensaje_fecha_invalida

LIMITE_POR_DEFECTO = 100
LIMITE_MAXIMO = 500
DIAS_POR_DEFECTO = 7


def _fecha(valor, campo):
    try:
        return dt.date.fromisoformat(valor)
    except (TypeError, ValueError):
        raise ErrorAplicacion(
            mensaje_fecha_invalida(valor, campo, 'La fecha tiene que tener el formato AAAA-MM-DD.'),
            campo=campo,
        )


def listar_accesos(desde=None, hasta=None, resultado=None, email=None, limite=None):
    """
    Accesos del periodo, del mas reciente al mas viejo.

    Devuelve las filas (hasta `limite`) y un resumen POR RESULTADO sobre TODO
    el filtro, no solo sobre las filas devueltas: el recuento no puede cambiar
    porque la tabla este recortada.
    """
    hoy = dt.date.today()
    hasta_f = _fecha(hasta, 'hasta') if hasta else hoy
    desde_f = _fecha(desde, 'desde') if desde else hasta_f - dt.timedelta(days=DIAS_POR_DEFECTO)
    if desde_f > hasta_f:
        raise ErrorAplicacion('El rango de fechas esta invertido.', campo='desde')

    if resultado and resultado not in RESULTADOS_ACCESO:
        raise ErrorAplicacion(
            'El resultado tiene que ser uno de: ' + ', '.join(RESULTADOS_ACCESO) + '.',
            campo='resultado',
        )

    try:
        limite = int(limite) if limite else LIMITE_POR_DEFECTO
    except (TypeError, ValueError):
        raise ErrorAplicacion('El limite tiene que ser un numero.', campo='limite')
    limite = max(1, min(limite, LIMITE_MAXIMO))

    filtros = [
        AuditoriaAcceso.fecha >= dt.datetime.combine(desde_f, dt.time.min),
        AuditoriaAcceso.fecha < dt.datetime.combine(hasta_f + dt.timedelta(days=1), dt.time.min),
    ]
    if resultado:
        filtros.append(AuditoriaAcceso.resultado == resultado)
    if email and email.strip():
        # contains con autoescape: un '%' o '_' escrito por el usuario es literal
        filtros.append(AuditoriaAcceso.email.contains(email.strip().lower(), autoescape=True))

    filas = (
        AuditoriaAcceso.query.filter(*filtros)
        .order_by(AuditoriaAcceso.fecha.desc(), AuditoriaAcceso.id.desc())
        .limit(limite)
        .all()
    )
    conteo = dict(
        db.session.query(AuditoriaAcceso.resultado, func.count())
        .filter(*filtros)
        .group_by(AuditoriaAcceso.resultado)
        .all()
    )
    resumen = {r: int(conteo.get(r, 0)) for r in RESULTADOS_ACCESO}
    resumen['total'] = sum(resumen.values())

    return {
        'desde': desde_f.isoformat(),
        'hasta': hasta_f.isoformat(),
        'limite': limite,
        'resumen': resumen,
        'accesos': [fila.to_dict() for fila in filas],
    }

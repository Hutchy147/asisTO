# backend/app/services/pacientes_service.py
# Logica de pacientes. Las rutas solo traducen HTTP.

import logging

from sqlalchemy import text

from app import db
from app.models import ObjetivoTerapeutico, Paciente
from app.utils.db import reintentar_en_deadlock
from app.utils.errors import ErrorAplicacion

logger = logging.getLogger(__name__)


def _contar_objetivos_activos_por_paciente():
    """{id_paciente: cantidad} en una sola consulta, no una por paciente."""
    filas = (
        db.session.query(
            ObjetivoTerapeutico.id_paciente,
            db.func.count(ObjetivoTerapeutico.id),
        )
        .filter(ObjetivoTerapeutico.activo.is_(True))
        .group_by(ObjetivoTerapeutico.id_paciente)
        .all()
    )
    return {id_paciente: cantidad for id_paciente, cantidad in filas}


def listar_pacientes():
    """Pacientes activos, con su cantidad de objetivos activos."""
    pacientes = (
        Paciente.query
        .filter(Paciente.activo.is_(True))
        .order_by(Paciente.apellido, Paciente.nombre)
        .all()
    )

    conteos = _contar_objetivos_activos_por_paciente()

    resultado = []
    for paciente in pacientes:
        datos = paciente.to_dict_clinico()
        datos['objetivos_activos'] = conteos.get(paciente.id, 0)
        resultado.append(datos)

    return resultado


def obtener_paciente(id_paciente, incluir_inactivos=False):
    """
    Busca un paciente activo. Lanza ErrorAplicacion 404 si no existe.

    Un paciente dado de baja se trata como inexistente para las pantallas
    normales: sigue en la base porque su historia clinica no se borra, pero
    no aparece en el listado ni se puede operar sobre el.
    """
    paciente = Paciente.query.get(id_paciente)

    if paciente is None:
        raise ErrorAplicacion('El paciente indicado no existe.', http_status=404)

    if not paciente.activo and not incluir_inactivos:
        raise ErrorAplicacion(
            'El paciente indicado esta dado de baja.', http_status=404
        )

    return paciente


def obtener_detalle(id_paciente):
    """Paciente + sus objetivos activos."""
    paciente = obtener_paciente(id_paciente)

    objetivos = (
        ObjetivoTerapeutico.query
        .filter_by(id_paciente=paciente.id, activo=True)
        .order_by(ObjetivoTerapeutico.fecha_creacion, ObjetivoTerapeutico.id)
        .all()
    )

    return {
        'paciente': paciente.to_dict_clinico(),
        'objetivos_activos': [objetivo.to_dict() for objetivo in objetivos],
    }


@reintentar_en_deadlock()
def alta_paciente(datos):
    """
    Alta via p_alta_paciente. No se arma el INSERT a mano.

    El procedimiento es el que valida el numero de historia duplicado y el
    que resuelve la carrera contra la UNIQUE si dos altas simultaneas pasan
    su chequeo. Replicar esa validacion aca solo agregaria una segunda
    version que puede divergir.

    Devuelve (paciente, mensaje) con el p_mensaje del procedimiento.
    """
    nombre = (datos.get('nombre') or '').strip()
    apellido = (datos.get('apellido') or '').strip()
    fecha_nacimiento = (datos.get('fecha_nacimiento') or '').strip()
    nro_historia = (datos.get('nro_historia') or '').strip()
    diagnostico = datos.get('diagnostico')
    id_usuario = datos.get('id_usuario')  # opcional: paciente sin login

    faltantes = [
        etiqueta for etiqueta, valor in (
            ('nombre', nombre),
            ('apellido', apellido),
            ('fecha_nacimiento', fecha_nacimiento),
            ('nro_historia', nro_historia),
        ) if not valor
    ]
    if faltantes:
        raise ErrorAplicacion(
            'Faltan datos obligatorios: ' + ', '.join(faltantes)
        )

    db.session.execute(
        text(
            'CALL p_alta_paciente(:nombre, :apellido, :fecha_nacimiento, '
            ':diagnostico, :nro_historia, :id_usuario, @p_id_paciente, @p_mensaje)'
        ),
        {
            'nombre': nombre,
            'apellido': apellido,
            'fecha_nacimiento': fecha_nacimiento,
            'diagnostico': diagnostico,
            'nro_historia': nro_historia,
            'id_usuario': id_usuario,
        },
    )

    # Las variables de sesion sobreviven al CALL en la misma conexion
    id_creado, mensaje = db.session.execute(
        text('SELECT @p_id_paciente, @p_mensaje')
    ).first()

    # p_alta_paciente hace su propio COMMIT/ROLLBACK. Este cierra la
    # transaccion que SQLAlchemy abrio para leer las variables de salida.
    db.session.commit()

    if id_creado is None:
        # El procedimiento rechazo el alta y su p_mensaje ya explica por que
        raise ErrorAplicacion(mensaje or 'No se pudo dar de alta el paciente.')

    paciente = Paciente.query.get(int(id_creado))
    logger.info('Paciente %s dado de alta (%s)', paciente.id, paciente.nro_historia)

    return paciente, mensaje

# backend/app/services/familiares_service.py
# Vinculo familiar-paciente. Las reglas las aplica la base (p_vincular_familiar,
# p_desvincular_familiar, p_crear_familiar_y_vincular); aca se traduce.
#
# Quien puede: el administrador y la terapeuta con asignacion vigente sobre el
# paciente. Una terapeuta sin asignacion no decide quien accede a un paciente
# ajeno. El familiar nunca llega a este modulo (rol propio, portal aparte).

import logging
import re
import secrets
import string

from flask import g
from sqlalchemy import text

from app import db
from app.models import Familiar, FamiliarPaciente, Usuario
from app.services.asignaciones_service import ids_de_pacientes_asignados
from app.services.pacientes_service import obtener_paciente
from app.services.sesiones_service import terapeuta_actual
from app.utils.db import reintentar_en_deadlock
from app.utils.errors import ErrorAplicacion
from app.utils.security import hashear_contrasena

logger = logging.getLogger(__name__)

_EMAIL = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def _verificar_acceso(id_paciente):
    """Administrador, o terapeuta con asignacion vigente sobre el paciente."""
    paciente = obtener_paciente(id_paciente, incluir_inactivos=True)
    if g.usuario_actual.rol == 'admin':
        return paciente
    if paciente.id not in ids_de_pacientes_asignados(terapeuta_actual().id):
        raise ErrorAplicacion(
            'Solo el administrador o el terapeuta asignado pueden gestionar '
            'los familiares de este paciente.',
            http_status=403,
        )
    return paciente


def _serializar(familiar, usuario, vinculo=None):
    datos = {
        'id': familiar.id,
        'nombre': usuario.nombre,
        'apellido': usuario.apellido,
        'nombre_completo': f'{usuario.nombre} {usuario.apellido}',
        'email': usuario.email,
        'parentesco': familiar.parentesco,
        'telefono': familiar.telefono,
        'cuenta_activa': bool(usuario.activo),
    }
    if vinculo is not None:
        datos['fecha_vinculo'] = vinculo.fecha_vinculo.isoformat()
    return datos


def listar_de_paciente(id_paciente):
    """Familiares vinculados al paciente."""
    paciente = _verificar_acceso(id_paciente)
    filas = (
        db.session.query(Familiar, Usuario, FamiliarPaciente)
        .join(Usuario, Usuario.id == Familiar.id_usuario)
        .join(FamiliarPaciente, FamiliarPaciente.id_familiar == Familiar.id)
        .filter(FamiliarPaciente.id_paciente == paciente.id)
        .order_by(Usuario.apellido, Usuario.nombre)
        .all()
    )
    familiares = [_serializar(f, u, v) for f, u, v in filas]
    return {
        'id_paciente': paciente.id,
        'familiares': familiares,
        'total': len(familiares),
    }


def listar_candidatos(id_paciente, busqueda=None):
    """
    Cuentas de familiar activas que todavia NO estan vinculadas a este
    paciente, para elegir una existente (por ejemplo, un hermano que ya tiene
    cuenta por otro paciente).
    """
    paciente = _verificar_acceso(id_paciente)
    vinculados = (
        db.session.query(FamiliarPaciente.id_familiar)
        .filter(FamiliarPaciente.id_paciente == paciente.id)
    )
    consulta = (
        db.session.query(Familiar, Usuario)
        .join(Usuario, Usuario.id == Familiar.id_usuario)
        .filter(Usuario.activo.is_(True), ~Familiar.id.in_(vinculados))
    )
    texto = (busqueda or '').strip()
    if texto:
        patron = f'%{texto}%'
        consulta = consulta.filter(
            db.or_(
                Usuario.nombre.like(patron),
                Usuario.apellido.like(patron),
                Usuario.email.like(patron),
            )
        )
    filas = consulta.order_by(Usuario.apellido, Usuario.nombre).limit(50).all()
    return {'familiares': [_serializar(f, u) for f, u in filas]}


def _texto(datos, clave, etiqueta, maximo, obligatorio=True):
    valor = datos.get(clave)
    valor = valor.strip() if isinstance(valor, str) else ''
    if not valor:
        if obligatorio:
            raise ErrorAplicacion(f'Falta indicar {etiqueta}.', campo=clave)
        return None
    if len(valor) > maximo:
        raise ErrorAplicacion(
            f'{etiqueta.capitalize()} no puede superar los {maximo} caracteres.',
            campo=clave,
        )
    return valor


def generar_contrasena_temporal():
    """Contrasena de 10 caracteres con letras y numeros (cumple la politica)."""
    alfabeto = string.ascii_letters + string.digits
    while True:
        clave = ''.join(secrets.choice(alfabeto) for _ in range(10))
        if any(c.isalpha() for c in clave) and any(c.isdigit() for c in clave):
            return clave


def _por_codigo(mensaje, ok_texto):
    texto = (mensaje or '').lower()
    if 'no existe' in texto and 'correo' not in texto:
        return 404
    if 'ya esta vinculado' in texto or 'ya existe' in texto or 'no esta vinculado' in texto:
        return 409
    return 400


@reintentar_en_deadlock()
def _vincular_existente(id_paciente, id_familiar):
    db.session.execute(
        text('CALL p_vincular_familiar(:fam, :pac, @p_ok, @p_mensaje)'),
        {'fam': id_familiar, 'pac': id_paciente},
    )
    ok, mensaje = db.session.execute(text('SELECT @p_ok, @p_mensaje')).first()
    db.session.commit()
    if not ok:
        raise ErrorAplicacion(
            mensaje or 'No se pudo vincular al familiar.',
            http_status=_por_codigo(mensaje, False),
        )
    return mensaje


@reintentar_en_deadlock()
def _crear_y_vincular(id_paciente, datos):
    nombre = _texto(datos, 'nombre', 'el nombre', 100)
    apellido = _texto(datos, 'apellido', 'el apellido', 100)
    email = _texto(datos, 'email', 'el correo electrónico', 180).lower()
    if not _EMAIL.match(email):
        raise ErrorAplicacion(
            'El correo electrónico no tiene un formato válido.', campo='email'
        )
    parentesco = _texto(datos, 'parentesco', 'el parentesco', 60, obligatorio=False)
    telefono = _texto(datos, 'telefono', 'el teléfono', 40, obligatorio=False)

    contrasena = generar_contrasena_temporal()
    db.session.execute(
        text(
            'CALL p_crear_familiar_y_vincular(:nombre, :apellido, :email, :hash, '
            ':parentesco, :telefono, :pac, @p_id, @p_mensaje)'
        ),
        {
            'nombre': nombre, 'apellido': apellido, 'email': email,
            'hash': hashear_contrasena(contrasena),
            'parentesco': parentesco, 'telefono': telefono, 'pac': id_paciente,
        },
    )
    id_familiar, mensaje = db.session.execute(
        text('SELECT @p_id, @p_mensaje')
    ).first()
    db.session.commit()
    if id_familiar is None:
        raise ErrorAplicacion(
            mensaje or 'No se pudo crear al familiar.',
            http_status=_por_codigo(mensaje, False),
            campo='email' if 'correo' in (mensaje or '').lower() else None,
        )
    return id_familiar, contrasena, mensaje


def vincular(id_paciente, datos):
    """
    Vincula un familiar al paciente. Con `id_familiar` usa una cuenta
    existente; sin el, crea la cuenta y devuelve la contrasena temporal UNA
    sola vez (no se guarda en claro en ningun lado).
    """
    paciente = _verificar_acceso(id_paciente)
    contrasena = None
    if datos.get('id_familiar') not in (None, ''):
        try:
            id_familiar = int(datos['id_familiar'])
        except (TypeError, ValueError):
            raise ErrorAplicacion('Falta indicar el familiar.', campo='id_familiar')
        mensaje = _vincular_existente(paciente.id, id_familiar)
    else:
        id_familiar, contrasena, mensaje = _crear_y_vincular(paciente.id, datos)

    db.session.expire_all()
    fila = (
        db.session.query(Familiar, Usuario, FamiliarPaciente)
        .join(Usuario, Usuario.id == Familiar.id_usuario)
        .join(FamiliarPaciente, FamiliarPaciente.id_familiar == Familiar.id)
        .filter(Familiar.id == id_familiar, FamiliarPaciente.id_paciente == paciente.id)
        .first()
    )
    logger.info('Familiar %s vinculado al paciente %s', id_familiar, paciente.id)
    return _serializar(*fila), contrasena, mensaje


@reintentar_en_deadlock()
def desvincular(id_paciente, id_familiar):
    paciente = _verificar_acceso(id_paciente)
    db.session.execute(
        text('CALL p_desvincular_familiar(:fam, :pac, @p_ok, @p_mensaje)'),
        {'fam': id_familiar, 'pac': paciente.id},
    )
    ok, mensaje = db.session.execute(text('SELECT @p_ok, @p_mensaje')).first()
    db.session.commit()
    if not ok:
        raise ErrorAplicacion(
            mensaje or 'No se pudo desvincular al familiar.',
            http_status=_por_codigo(mensaje, False),
        )
    logger.info('Familiar %s desvinculado del paciente %s', id_familiar, paciente.id)
    return mensaje

# backend/app/services/usuarios_service.py
# Cuentas de acceso, gestionadas por el administrador: dar de alta un correo con
# su clave (que el administrador le entrega a la persona), habilitarlo o
# deshabilitarlo y restablecerle la clave. Antes solo entraban los correos
# precargados en el seed.
#
# Roles que se dan de alta aca: terapeuta, rrhh, admin y familiar. La cuenta
# del PACIENTE no: depende de su ficha clinica (pacientes.id_usuario) y se
# vincula desde el paciente. Un familiar creado aca queda sin pacientes
# vinculados; el vinculo se hace despues, desde la ficha o desde Asignaciones.
#
# Una clave que elige el administrador no es secreta para el administrador:
# por eso se pide cambiarla con «¿Olvidó su contraseña?» (ver docs/seguridad.md).

import logging
import re

from flask import g
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app import db
from app.models import Asignacion, Familiar, Rrhh, Terapeuta, Usuario
from app.services.auth_service import _validar_contrasena_nueva
from app.services.familiares_service import generar_contrasena_temporal
from app.utils.errors import ErrorAplicacion
from app.utils.security import hashear_contrasena

logger = logging.getLogger(__name__)

_EMAIL = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')

# Roles que el administrador puede dar de alta desde esta pantalla.
ROLES_CREABLES = ('terapeuta', 'rrhh', 'admin', 'familiar')


def _texto(datos, clave, etiqueta, maximo, obligatorio=True):
    valor = datos.get(clave)
    valor = valor.strip() if isinstance(valor, str) else ''
    if not valor:
        if obligatorio:
            raise ErrorAplicacion(f'Falta indicar {etiqueta}.', campo=clave)
        return None
    if len(valor) > maximo:
        raise ErrorAplicacion(
            f'{etiqueta[0].upper() + etiqueta[1:]} no puede superar los {maximo} caracteres.',
            campo=clave,
        )
    return valor


def _validar_clave(contrasena, email):
    """La política de siempre; el error apunta al campo de este formulario."""
    try:
        _validar_contrasena_nueva(contrasena, email)
    except ErrorAplicacion as error:
        raise ErrorAplicacion(error.mensaje, campo='contrasena') from None


def contrasena_sugerida():
    return generar_contrasena_temporal()


def _perfil(usuario):
    """Dato propio del rol, para mostrar en el listado."""
    if usuario.rol == 'terapeuta' and usuario.terapeuta:
        return f'Matrícula {usuario.terapeuta.matricula}'
    if usuario.rol == 'rrhh' and usuario.rrhh:
        return f'Legajo {usuario.rrhh.nro_legajo}'
    if usuario.rol == 'familiar' and usuario.familiar and usuario.familiar.parentesco:
        return usuario.familiar.parentesco
    return None


def _serializar(usuario, ultimo_ingreso=None, pacientes_a_cargo=0, ahora=None):
    # El bloqueo se escribe con NOW() de la base: se compara con su misma hora.
    ahora = ahora or db.session.execute(text('SELECT NOW()')).scalar()
    bloqueado = bool(usuario.bloqueado_hasta and usuario.bloqueado_hasta > ahora)
    return {
        'id': usuario.id,
        'nombre': usuario.nombre,
        'apellido': usuario.apellido,
        'nombre_completo': usuario.nombre_completo,
        'email': usuario.email,
        'rol': usuario.rol,
        'activo': bool(usuario.activo),
        'bloqueado': bloqueado,
        'perfil': _perfil(usuario),
        'ultimo_ingreso': ultimo_ingreso.isoformat(sep=' ') if ultimo_ingreso else None,
        'pacientes_a_cargo': pacientes_a_cargo,
        'es_usted': usuario.id == g.usuario_actual.id,
    }


def listar(rol=None, busqueda=None, estado=None):
    """Cuentas con su estado. Nunca devuelve hashes ni tokens."""
    consulta = Usuario.query
    if rol:
        if rol not in ('terapeuta', 'rrhh', 'admin', 'familiar', 'paciente'):
            raise ErrorAplicacion('El rol indicado no es válido.', campo='rol')
        consulta = consulta.filter(Usuario.rol == rol)
    if estado == 'activas':
        consulta = consulta.filter(Usuario.activo.is_(True))
    elif estado == 'deshabilitadas':
        consulta = consulta.filter(Usuario.activo.is_(False))
    elif estado:
        raise ErrorAplicacion('El estado indicado no es válido.', campo='estado')
    texto = (busqueda or '').strip()
    if texto:
        # Los comodines que escribe la persona se buscan como texto.
        escapado = texto.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        patron = f'%{escapado}%'
        consulta = consulta.filter(db.or_(
            Usuario.nombre.like(patron, escape='\\'),
            Usuario.apellido.like(patron, escape='\\'),
            Usuario.email.like(patron, escape='\\'),
        ))
    usuarios = consulta.order_by(Usuario.activo.desc(), Usuario.apellido, Usuario.nombre).all()
    ids = [u.id for u in usuarios]

    ingresos = {}
    if ids:
        filas = db.session.execute(
            text(
                "SELECT id_usuario, MAX(fecha) FROM auditoria_accesos "
                "WHERE resultado = 'exitoso' AND id_usuario IN :ids GROUP BY id_usuario"
            ).bindparams(db.bindparam('ids', expanding=True)),
            {'ids': ids},
        ).all()
        ingresos = {i: f for i, f in filas}

    a_cargo = {}
    terapeutas = {u.terapeuta.id: u.id for u in usuarios if u.rol == 'terapeuta' and u.terapeuta}
    if terapeutas:
        for id_terapeuta, cantidad in (
            db.session.query(Asignacion.id_terapeuta, db.func.count(Asignacion.id))
            .filter(Asignacion.id_terapeuta.in_(list(terapeutas)), Asignacion.fecha_hasta.is_(None))
            .group_by(Asignacion.id_terapeuta).all()
        ):
            a_cargo[terapeutas[id_terapeuta]] = int(cantidad)

    ahora = db.session.execute(text('SELECT NOW()')).scalar()
    return [_serializar(u, ingresos.get(u.id), a_cargo.get(u.id, 0), ahora) for u in usuarios]


def crear(datos):
    """Da de alta una cuenta con la clave que eligió el administrador."""
    rol = datos.get('rol')
    if rol not in ROLES_CREABLES:
        raise ErrorAplicacion(
            'Elija el rol de la cuenta: terapeuta, Recursos Humanos, administrador o familiar.',
            campo='rol',
        )
    nombre = _texto(datos, 'nombre', 'el nombre', 100)
    apellido = _texto(datos, 'apellido', 'el apellido', 100)
    email = _texto(datos, 'email', 'el correo electrónico', 180).lower()
    if not _EMAIL.match(email):
        raise ErrorAplicacion('El correo electrónico no tiene un formato válido.', campo='email')
    contrasena = datos.get('contrasena')
    _validar_clave(contrasena, email)

    # Datos propios del rol: se validan antes de tocar la base.
    if rol == 'terapeuta':
        matricula = _texto(datos, 'matricula', 'la matrícula', 50)
        especialidad = _texto(datos, 'especialidad', 'la especialidad', 120, obligatorio=False)
    elif rol == 'rrhh':
        legajo = _texto(datos, 'nro_legajo', 'el número de legajo', 50)
        sector = _texto(datos, 'sector', 'el sector', 120, obligatorio=False)
    elif rol == 'familiar':
        parentesco = _texto(datos, 'parentesco', 'el parentesco', 60, obligatorio=False)
        telefono = _texto(datos, 'telefono', 'el teléfono', 40, obligatorio=False)

    if Usuario.query.filter(db.func.lower(Usuario.email) == email).first():
        raise ErrorAplicacion('Ya existe una cuenta con ese correo electrónico.', http_status=409, campo='email')

    usuario = Usuario(
        nombre=nombre, apellido=apellido, email=email, rol=rol, activo=True,
        contrasena_hash=hashear_contrasena(contrasena),
    )
    try:
        db.session.add(usuario)
        db.session.flush()
        if rol == 'terapeuta':
            db.session.add(Terapeuta(id_usuario=usuario.id, matricula=matricula, especialidad=especialidad))
        elif rol == 'rrhh':
            db.session.add(Rrhh(id_usuario=usuario.id, nro_legajo=legajo, sector=sector))
        elif rol == 'familiar':
            db.session.add(Familiar(id_usuario=usuario.id, parentesco=parentesco, telefono=telefono))
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        detalle = str(error.orig).lower()
        if 'matricula' in detalle:
            raise ErrorAplicacion('Ya existe un terapeuta con esa matrícula.', http_status=409, campo='matricula') from None
        if 'legajo' in detalle:
            raise ErrorAplicacion('Ya existe una persona con ese número de legajo.', http_status=409, campo='nro_legajo') from None
        raise ErrorAplicacion('Ya existe una cuenta con ese correo electrónico.', http_status=409, campo='email') from None

    logger.info('Cuenta %s (%s) creada por el administrador %s', usuario.id, rol, g.usuario_actual.id)
    return _serializar(usuario)


def _cuenta(id_usuario):
    usuario = db.session.get(Usuario, id_usuario)
    if usuario is None:
        raise ErrorAplicacion('La cuenta indicada no existe.', http_status=404)
    return usuario


def _revocar_sesiones(id_usuario):
    """Los tokens ya emitidos dejan de valer (misma marca que el cierre de sesión)."""
    db.session.execute(
        text('UPDATE usuarios SET sesiones_validas_desde = NOW(6) WHERE id = :id'), {'id': id_usuario}
    )


def cambiar_estado(id_usuario, activo):
    """Habilita o deshabilita una cuenta. Deshabilitar corta sus sesiones."""
    if not isinstance(activo, bool):
        raise ErrorAplicacion('Indique si la cuenta queda habilitada o deshabilitada.', campo='activo')
    usuario = _cuenta(id_usuario)
    if not activo:
        if usuario.id == g.usuario_actual.id:
            raise ErrorAplicacion('No puede deshabilitar su propia cuenta.', http_status=409)
        if usuario.rol == 'admin' and usuario.activo:
            # Siempre tiene que quedar alguien que administre.
            otros = Usuario.query.filter(
                Usuario.rol == 'admin', Usuario.activo.is_(True), Usuario.id != usuario.id
            ).count()
            if otros == 0:
                raise ErrorAplicacion(
                    'Es la única cuenta de administrador activa: no se puede deshabilitar.', http_status=409
                )
    usuario.activo = activo
    if not activo:
        _revocar_sesiones(usuario.id)
    db.session.commit()
    logger.info('Cuenta %s %s por el administrador %s', usuario.id,
                'habilitada' if activo else 'deshabilitada', g.usuario_actual.id)
    return _serializar(usuario)


def restablecer_contrasena(id_usuario, contrasena):
    """El administrador fija una clave nueva; cierra las sesiones y desbloquea."""
    usuario = _cuenta(id_usuario)
    _validar_clave(contrasena, usuario.email)
    usuario.contrasena_hash = hashear_contrasena(contrasena)
    usuario.intentos_fallidos = 0
    usuario.bloqueado_hasta = None
    # Un enlace de recuperación pendiente no puede pisar la clave nueva.
    usuario.token_recuperacion = None
    usuario.token_expira = None
    _revocar_sesiones(usuario.id)
    db.session.commit()
    logger.info('Clave de la cuenta %s restablecida por el administrador %s', usuario.id, g.usuario_actual.id)
    return _serializar(usuario)

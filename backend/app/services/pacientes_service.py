# backend/app/services/pacientes_service.py
# Logica de pacientes. Las rutas solo traducen HTTP.

import logging

from sqlalchemy import text

from app import db
from app.models import ObjetivoTerapeutico, Paciente
from app.models.paciente import (
    MAXIMO_CARACTERES_APELLIDO, MAXIMO_CARACTERES_NOMBRE,
    MAXIMO_CARACTERES_NRO_HISTORIA, MAXIMO_CARACTERES_OBRA_SOCIAL,
)
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


# Minimo de objetivos activos de un paciente en tratamiento (Entrega 3). La
# regla vive en el trigger de objetivos; aca solo se informa cuanto falta.
MINIMO_OBJETIVOS = 3


def listar_pacientes():
    """Pacientes activos, con su cantidad de objetivos activos."""
    pacientes = (
        Paciente.query
        .filter(Paciente.activo.is_(True))
        .order_by(Paciente.apellido, Paciente.nombre)
        .all()
    )

    conteos = _contar_objetivos_activos_por_paciente()

    # Import local: asignaciones_service importa obtener_paciente de este
    # modulo, y el import de arriba formaria un ciclo.
    from app.services.asignaciones_service import (
        ids_de_pacientes_asignados, responsables_vigentes,
    )
    from app.services.sesiones_service import terapeuta_actual

    mios = ids_de_pacientes_asignados(terapeuta_actual().id)
    responsables = responsables_vigentes()

    resultado = []
    for paciente in pacientes:
        datos = paciente.to_dict_clinico()
        datos['objetivos_activos'] = conteos.get(paciente.id, 0)
        datos['faltan_objetivos'] = max(0, MINIMO_OBJETIVOS - datos['objetivos_activos'])
        # HDU 11: la escritura clinica solo es de quien tiene asignado al
        # paciente. La lectura sigue abierta, asi que el listado trae a todos
        # y marca cuales son "mios".
        datos['asignado_a_mi'] = paciente.id in mios
        datos['responsables'] = responsables.get(paciente.id, [])
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


def _contar_asignaciones_vigentes(id_paciente):
    """
    Cuantas asignaciones vigentes tiene el paciente. Vigente es
    `fecha_hasta IS NULL` y nada mas, igual que en el trigger y en
    p_baja_paciente: si esta definicion se duplicara con otro criterio, la
    interfaz anunciaria un numero y la base cerraria otro.

    Va con SQL directo porque `asignaciones` todavia no tiene modelo: la tabla
    entro en la migracion del 2026-08-07 y su modulo no existe. Mapearla
    entera para un COUNT seria construir la mitad de un modulo que no se pidio.
    """
    return db.session.execute(
        text(
            'SELECT COUNT(*) FROM asignaciones '
            'WHERE id_paciente = :id AND fecha_hasta IS NULL'
        ),
        {'id': id_paciente},
    ).scalar()


def obtener_detalle(id_paciente):
    """
    Paciente + sus objetivos activos.

    Incluye a los pacientes dados de baja A PROPOSITO, y es un cambio de
    comportamiento del 2026-08-12. Antes esta ficha devolvia 404 para un
    paciente inactivo, y con eso su historia clinica quedaba inaccesible por
    la API: 404 en la ficha, 404 en el historial y 404 en sus objetivos. Un
    paciente dado de baja no es un paciente que no existe — es uno que ya no
    esta en tratamiento, y sus registros tienen que poder consultarse.

    Lo que NO cambia es la escritura: `obtener_paciente` sigue rechazando por
    defecto a los inactivos, asi que crear un objetivo o registrar una sesion
    sobre un paciente de baja sigue dando 404. La lectura se abre; la
    escritura no. Es la misma forma de la decision 8.

    `activo` y `fecha_baja` viajan en el to_dict(), asi que la interfaz tiene
    con que dibujar la ficha en modo lectura.
    """
    paciente = obtener_paciente(id_paciente, incluir_inactivos=True)

    objetivos = (
        ObjetivoTerapeutico.query
        .filter_by(id_paciente=paciente.id, activo=True)
        .order_by(ObjetivoTerapeutico.fecha_creacion, ObjetivoTerapeutico.id)
        .all()
    )

    return {
        'paciente': paciente.to_dict_clinico(),
        'objetivos_activos': [objetivo.to_dict() for objetivo in objetivos],
        # La interfaz necesita saber que esta en modo lectura ANTES de dibujar
        # los botones, no cuando el servidor le rechace la accion.
        'solo_lectura': not paciente.activo,
        'minimo_objetivos': MINIMO_OBJETIVOS,
        'faltan_objetivos': (
            max(0, MINIMO_OBJETIVOS - len(objetivos)) if paciente.activo else 0
        ),
        # Que va a arrastrar la baja, para poder decirlo ANTES de pedir la
        # confirmacion. Sin estos dos numeros el dialogo tendria que hablar en
        # abstracto ("se van a archivar sus objetivos") y el terapeuta se
        # entera de lo que hizo despues de hacerlo.
        #
        # Se calcula al pedirlo y no se guarda: entre que se abre la ficha y
        # se aprieta el boton pueden pasar minutos, y un numero viejo en un
        # dialogo de confirmacion es peor que ninguno.
        'baja_arrastra': {
            'objetivos_activos': len(objetivos),
            'asignaciones_vigentes': _contar_asignaciones_vigentes(paciente.id),
        },
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

    # HDU 11: sin terapeuta asignado nadie puede registrarle sesiones, asi que
    # el alta deja al paciente asignado a quien lo da de alta. Elegir otro
    # responsable es potestad del administrador (por eso se ignora un
    # `id_terapeuta` del cuerpo). Si la asignacion falla, el paciente YA
    # existe: no se deshace, se avisa en el mensaje y lo resuelve el
    # administrador.
    from app.services import asignaciones_service
    from app.services.sesiones_service import terapeuta_actual

    id_terapeuta = terapeuta_actual().id
    try:
        asignaciones_service.abrir_asignacion(
            paciente.id, {'id_terapeuta': id_terapeuta}
        )
    except ErrorAplicacion as error:
        db.session.rollback()
        mensaje = (
            f'{mensaje} Pero no se pudo asignar el terapeuta responsable: '
            f'{error.mensaje} Solicite la asignación al administrador.'
        )

    return paciente, mensaje


def _texto_valido(datos, clave, etiqueta, maximo, obligatorio=True):
    """
    Valida un campo de texto contra su tope y lo devuelve ya recortado.

    Una sola funcion para todos los campos, por la misma razon que
    `_descripcion_valida` en objetivos: si cada campo se valida en su propia
    linea, en algun momento uno queda sin validar y nadie lo nota.

    El largo se mide DESPUES del strip(): los espacios de los extremos no se
    guardan, asi que no tiene sentido que consuman cupo.
    """
    valor = (datos.get(clave) or '').strip()

    if obligatorio and not valor:
        raise ErrorAplicacion('Falta indicar %s.' % etiqueta, campo=clave)

    if len(valor) > maximo:
        raise ErrorAplicacion(
            'El campo %s no puede superar los %s caracteres.' % (etiqueta, maximo),
            campo=clave,
        )

    return valor or None


@reintentar_en_deadlock()
def _exigir_responsable(id_paciente, accion, **opciones):
    """404 si el paciente no existe; 403 si el terapeuta no es el responsable."""
    from app.services.asignaciones_service import exigir_responsable
    obtener_paciente(id_paciente, incluir_inactivos=True)
    exigir_responsable(id_paciente, accion, **opciones)


def editar_paciente(id_paciente, datos):
    """
    Edicion via p_editar_paciente. NO toca id_usuario ni el estado de baja.

    El procedimiento valida el numero de historia duplicado y rechaza editar
    a un paciente dado de baja; aca no se replica ninguna de las dos. Lo que
    SI vive aca es el largo de los campos, porque el unico limite en la base
    es el VARCHAR y llega como errno 1406 sin marcar el campo.

    Devuelve (paciente, mensaje).
    """
    _exigir_responsable(id_paciente, 'editar sus datos', omitir_si_de_baja=True)

    nombre = _texto_valido(datos, 'nombre', 'nombre', MAXIMO_CARACTERES_NOMBRE)
    apellido = _texto_valido(datos, 'apellido', 'apellido', MAXIMO_CARACTERES_APELLIDO)
    nro_historia = _texto_valido(
        datos, 'nro_historia', 'numero de historia', MAXIMO_CARACTERES_NRO_HISTORIA
    )
    # Los dos opcionales: un paciente particular no tiene obra social y el
    # diagnostico puede no estar cargado todavia.
    obra_social = _texto_valido(
        datos, 'obra_social', 'obra social', MAXIMO_CARACTERES_OBRA_SOCIAL,
        obligatorio=False,
    )
    fecha_nacimiento = (datos.get('fecha_nacimiento') or '').strip()
    if not fecha_nacimiento:
        raise ErrorAplicacion(
            'Falta indicar la fecha de nacimiento.', campo='fecha_nacimiento'
        )

    diagnostico = datos.get('diagnostico')
    if diagnostico is not None:
        diagnostico = diagnostico.strip() or None

    db.session.execute(
        text(
            'CALL p_editar_paciente(:id_paciente, :nombre, :apellido, '
            ':fecha_nacimiento, :diagnostico, :obra_social, :nro_historia, '
            '@p_editado, @p_mensaje)'
        ),
        {
            'id_paciente': id_paciente,
            'nombre': nombre,
            'apellido': apellido,
            'fecha_nacimiento': fecha_nacimiento,
            'diagnostico': diagnostico,
            'obra_social': obra_social,
            'nro_historia': nro_historia,
        },
    )

    editado, mensaje = db.session.execute(
        text('SELECT @p_editado, @p_mensaje')
    ).first()

    db.session.commit()

    if editado is None:
        raise ErrorAplicacion(mensaje or 'No se pudo editar el paciente.')

    paciente = Paciente.query.get(id_paciente)
    logger.info('Paciente %s editado', id_paciente)

    return paciente, mensaje


def baja_paciente(id_paciente, datos=None):
    """
    Cierra el tratamiento. `datos['tipo']` es obligatorio (Entrega 3):
      - 'pausa': baja reversible, con motivo (p_pausar_paciente).
      - 'alta' : egreso, archiva objetivos y cierra asignaciones
                 (p_baja_paciente).

    Devuelve (paciente, resumen). Para la pausa los conteos son 0: no toca
    nada mas que al paciente.
    """
    datos = datos or {}
    tipo = datos.get('tipo')
    if tipo not in ('pausa', 'alta'):
        raise ErrorAplicacion(
            "Indique si se trata de una pausa o del alta del tratamiento.", campo='tipo'
        )

    _exigir_responsable(
        id_paciente,
        'pausar el tratamiento' if tipo == 'pausa' else 'dar el alta',
        omitir_si_de_baja=True,
    )
    if tipo == 'pausa':
        return _pausar(id_paciente, datos.get('motivo'))
    return _alta(id_paciente)


@reintentar_en_deadlock()
def _pausar(id_paciente, motivo):
    motivo = (motivo or '').strip() if isinstance(motivo, str) else ''
    if not motivo:
        raise ErrorAplicacion('La baja necesita un motivo', campo='motivo')
    if len(motivo) > 200:
        raise ErrorAplicacion(
            'El motivo de la baja no puede superar los 200 caracteres', campo='motivo'
        )

    db.session.execute(
        text('CALL p_pausar_paciente(:id, :motivo, @p_pausado, @p_mensaje)'),
        {'id': id_paciente, 'motivo': motivo},
    )
    pausado, mensaje = db.session.execute(
        text('SELECT @p_pausado, @p_mensaje')
    ).first()
    db.session.commit()

    # NULL = rechazo. No se compara el texto de p_mensaje.
    if pausado is None:
        raise ErrorAplicacion(mensaje or 'No se pudo pausar el tratamiento.')

    paciente = Paciente.query.get(id_paciente)
    db.session.refresh(paciente)
    logger.info('Paciente %s pausado', id_paciente)
    return paciente, {
        'objetivos_archivados': 0,
        'asignaciones_cerradas': 0,
        'mensaje': mensaje,
    }


@reintentar_en_deadlock()
def _alta(id_paciente):
    """Cierre via p_baja_paciente. Nunca borra. Ver schema.sql."""
    db.session.execute(
        text(
            'CALL p_baja_paciente(:id_paciente, @p_objetivos, '
            '@p_asignaciones, @p_mensaje)'
        ),
        {'id_paciente': id_paciente},
    )

    objetivos, asignaciones, mensaje = db.session.execute(
        text('SELECT @p_objetivos, @p_asignaciones, @p_mensaje')
    ).first()
    db.session.commit()

    if objetivos is None:
        raise ErrorAplicacion(mensaje or 'No se pudo dar de alta el paciente.')

    paciente = Paciente.query.get(id_paciente)
    db.session.refresh(paciente)
    logger.info(
        'Paciente %s dado de alta (%s objetivos archivados, %s asignaciones cerradas)',
        id_paciente, objetivos, asignaciones,
    )
    return paciente, {
        'objetivos_archivados': int(objetivos),
        'asignaciones_cerradas': int(asignaciones),
        'mensaje': mensaje,
    }


@reintentar_en_deadlock()
def reactivar_paciente(id_paciente):
    """
    Deshace la baja. NO desarchiva objetivos ni reabre asignaciones.

    Ver p_reactivar_paciente en schema.sql para el porque de cada una de esas
    dos omisiones: las dos son decisiones, no simplificaciones.

    Lo puede hacer el terapeuta responsable (la pausa no cierra la
    asignacion) o, si el alta dejo al paciente sin responsable, cualquier
    terapeuta: de otro modo nadie podria volver a abrirlo.
    """
    _exigir_responsable(
        id_paciente, 'reactivar el tratamiento', permitir_sin_responsable=True
    )
    db.session.execute(
        text('CALL p_reactivar_paciente(:id_paciente, @p_reactivado, @p_mensaje)'),
        {'id_paciente': id_paciente},
    )

    reactivado, mensaje = db.session.execute(
        text('SELECT @p_reactivado, @p_mensaje')
    ).first()

    db.session.commit()

    if reactivado is None:
        raise ErrorAplicacion(mensaje or 'No se pudo reactivar el paciente.')

    paciente = Paciente.query.get(id_paciente)
    logger.info('Paciente %s reactivado', id_paciente)

    return paciente, mensaje

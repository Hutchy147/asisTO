# backend/app/services/informes_service.py
# Informes del tratamiento (Entrega 6, HDU 5): generar, revisar, publicar,
# corregir, historial, diarios del periodo y control mensual.
#
# LAS REGLAS VIVEN EN LA BASE (p_crear_informe, p_editar_informe,
# p_publicar_informe, p_corregir_informe, p_descartar_informe): solo escribe
# el terapeuta asignado en el periodo del informe, un informe publicado no se
# edita, y no se publica con marcas [COMPLETAR] sin resolver. Aca se arma el
# periodo, se recolectan los datos, se llama al generador y se traducen las
# respuestas.
#
# LECTURA: cualquier terapeuta (misma politica que la ficha clinica). RRHH y
# el administrador no leen informes: es contenido clinico.
#
# AVISO AL FAMILIAR: al publicar se llama avisar_informe, despues del commit y
# a mejor esfuerzo. Un fallo del aviso nunca deshace la publicacion.

import datetime as dt
import logging

from sqlalchemy import or_, text

from app import db
from app.models import (
    Asignacion, Informe, Ingreso, ObjetivoTerapeutico, Paciente, Sesion, Terapeuta, Usuario,
)
from app.services import informes_generador as generador
from app.services.ingreso_service import obtener_ingreso
from app.services.notificaciones_service import avisar_informe
from app.services.pacientes_service import obtener_paciente
from app.services.sesiones_service import terapeuta_actual
from app.utils.db import reintentar_en_deadlock
from app.utils.errors import ErrorAplicacion
from app.utils.textos import acentuar

logger = logging.getLogger(__name__)

TIPOS = ('mensual', 'semestral', 'pti')
PERIODO_PTI = 'pti'
ORDEN_TIPO = {'semestral': 0, 'mensual': 1, 'pti': 2}


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def _estado_http(mensaje):
    texto = (mensaje or '').lower()
    if 'no existe' in texto:
        return 404
    if 'no tiene asignado' in texto:
        return 403
    if 'ya existe' in texto or 'ya hay' in texto or 'ya esta' in texto:
        return 409
    return 400


def _llamar(procedimiento, entradas, salidas):
    """
    CALL con OUT variables. `salidas` es la lista de OUT en orden, y el ULTIMO
    es siempre p_mensaje. Devuelve la tupla de OUT con el mensaje ya acentuado
    y hace commit (el CALL ya cerro su propia transaccion).
    """
    marcadores = ', '.join(f':{k}' for k in entradas)
    variables = ', '.join(f'@o_{i}' for i in range(len(salidas)))
    db.session.execute(text(f'CALL {procedimiento}({marcadores}, {variables})'), entradas)
    fila = db.session.execute(text('SELECT ' + variables)).first()
    db.session.commit()
    resultado = list(fila)
    resultado[-1] = acentuar(resultado[-1])
    return tuple(resultado)


def _informe_o_404(id_informe):
    informe = Informe.query.get(id_informe)
    if informe is None:
        raise ErrorAplicacion('El informe indicado no existe.', http_status=404)
    return informe


def _nombres_terapeutas(ids):
    if not ids:
        return {}
    filas = (
        db.session.query(Terapeuta.id, Usuario.nombre, Usuario.apellido)
        .join(Usuario, Usuario.id == Terapeuta.id_usuario)
        .filter(Terapeuta.id.in_(set(ids))).all()
    )
    return {i: f'{n} {a}' for i, n, a in filas}


def _iso(valor):
    return valor.isoformat() if valor else None


def serializar(informe, autores=None, con_contenido=False):
    autores = autores if autores is not None else _nombres_terapeutas([informe.id_terapeuta])
    datos = {
        'id': informe.id,
        'id_paciente': informe.id_paciente,
        'tipo': informe.tipo,
        'tipo_etiqueta': generador.ETIQUETA_TIPO.get(informe.tipo, informe.tipo),
        'periodo': informe.periodo,
        'periodo_etiqueta': generador.etiqueta_periodo(informe.tipo, informe.periodo),
        'fecha_desde': _iso(informe.fecha_desde),
        'fecha_hasta': _iso(informe.fecha_hasta),
        'version': informe.version,
        'estado': informe.estado,
        'generado_con': informe.generado_con,
        'proveedor': informe.proveedor,
        'autor': autores.get(informe.id_terapeuta),
        'fecha_generacion': _iso(informe.fecha_generacion),
        'fecha_edicion': _iso(informe.fecha_edicion),
        'fecha_publicacion': _iso(informe.fecha_publicacion),
        'editado': (informe.contenido or '') != (informe.contenido_original or ''),
    }
    if con_contenido:
        datos['contenido'] = informe.contenido if informe.contenido is not None else informe.contenido_original
        datos['contenido_original'] = informe.contenido_original
    return datos


# ---------------------------------------------------------------------------
# Lectura
# ---------------------------------------------------------------------------
def listar_de_paciente(id_paciente):
    """Historial completo del paciente: todas las versiones, de la mas reciente a la mas vieja."""
    paciente = obtener_paciente(id_paciente, incluir_inactivos=True)
    informes = (
        Informe.query.filter_by(id_paciente=paciente.id)
        .order_by(Informe.fecha_hasta.desc(), Informe.periodo.desc(), Informe.version.desc())
        .all()
    )
    autores = _nombres_terapeutas([i.id_terapeuta for i in informes])
    return {
        'paciente': {'id': paciente.id, 'nombre_completo': paciente.nombre_completo},
        'informes': [serializar(i, autores) for i in informes],
        'total': len(informes),
        'ia_disponible': generador.ia_disponible(),
    }


def obtener(id_informe):
    informe = _informe_o_404(id_informe)
    paciente = Paciente.query.get(informe.id_paciente)
    datos = serializar(informe, con_contenido=True)
    datos['paciente'] = {'id': paciente.id, 'nombre_completo': paciente.nombre_completo}
    return datos


def _periodo_de_consulta(paciente, tipo, periodo):
    """(clave, desde, hasta) segun el tipo. El PTI cubre desde el inicio del ingreso."""
    if tipo not in TIPOS:
        raise ErrorAplicacion('El tipo de informe debe ser mensual, semestral o PTI.', campo='tipo')
    if tipo == 'pti':
        ingreso = Ingreso.query.filter_by(id_paciente=paciente.id).first()
        if ingreso is None:
            raise ErrorAplicacion(
                'El PTI se arma desde el ingreso del paciente, y todavía no tiene un ingreso iniciado.',
                http_status=409,
            )
        desde = ingreso.fecha_inicio.date() if hasattr(ingreso.fecha_inicio, 'date') else ingreso.fecha_inicio
        return PERIODO_PTI, desde, dt.date.today()
    return generador.calcular_periodo(tipo, periodo)


def diarios(id_paciente, tipo, periodo):
    """Los diarios del periodo, para consultarlos al revisar o antes de generar."""
    paciente = obtener_paciente(id_paciente, incluir_inactivos=True)
    clave, desde, hasta = _periodo_de_consulta(paciente, tipo, periodo)
    return {
        'paciente': {'id': paciente.id, 'nombre_completo': paciente.nombre_completo},
        'tipo': tipo,
        'periodo': clave,
        'periodo_etiqueta': generador.etiqueta_periodo(tipo, clave),
        'desde': desde.isoformat(),
        'hasta': hasta.isoformat(),
        'diarios': generador.diarios_del_periodo(paciente.id, desde, hasta),
    }


def diarios_de_informe(id_informe):
    informe = _informe_o_404(id_informe)
    return diarios(informe.id_paciente, informe.tipo, informe.periodo)


# ---------------------------------------------------------------------------
# Escritura
# ---------------------------------------------------------------------------
@reintentar_en_deadlock()
def _crear(id_paciente, id_terapeuta, tipo, clave, desde, hasta, contenido, generado_con, proveedor):
    id_informe, mensaje = _llamar(
        'p_crear_informe',
        {'pac': id_paciente, 'ter': id_terapeuta, 'tipo': tipo, 'per': clave,
         'desde': desde, 'hasta': hasta, 'cont': contenido, 'gen': generado_con, 'prov': proveedor},
        ['id', 'mensaje'],
    )
    if not id_informe:
        raise ErrorAplicacion(mensaje or 'No se pudo generar el informe.', http_status=_estado_http(mensaje))
    return id_informe, mensaje


def generar(id_paciente, datos):
    """
    Genera (o regenera, si ya hay un borrador) el informe de un periodo. La
    IA se usa solo si el centro la configuro y la terapeuta no la apago.
    """
    datos = datos or {}
    for campo in ('tipo', 'periodo'):
        if not isinstance(datos.get(campo) or '', str):
            raise ErrorAplicacion(f'El campo {campo} debe ser un texto.', campo=campo)
    tipo = (datos.get('tipo') or '').strip().lower()
    paciente = obtener_paciente(id_paciente, incluir_inactivos=True)
    terapeuta = terapeuta_actual()
    clave, desde, hasta = _periodo_de_consulta(paciente, tipo, (datos.get('periodo') or '').strip())

    # Antes de gastar una llamada a la IA se confirma lo que la base va a
    # confirmar igual: que esta asignada en el periodo.
    asignado = (
        Asignacion.query.filter(
            Asignacion.id_paciente == paciente.id, Asignacion.id_terapeuta == terapeuta.id,
            Asignacion.fecha_desde <= hasta,
            or_(Asignacion.fecha_hasta.is_(None), Asignacion.fecha_hasta >= desde),
        ).first()
    )
    if asignado is None:
        raise ErrorAplicacion(
            'Solo el terapeuta asignado al paciente en el período puede generar su informe.',
            http_status=403,
        )

    pti = None
    if tipo == 'pti':
        pti = _datos_del_ingreso_pti(paciente)
    recolectados = generador.recolectar(paciente, tipo, desde, hasta, pti=pti)
    recolectados['clave'] = clave
    usar_ia = datos.get('usar_ia', True) not in (False, 'false', '0', 0)
    contenido, generado_con, proveedor, advertencia = generador.generar_contenido(recolectados, usar_ia=usar_ia)

    id_informe, mensaje = _crear(
        paciente.id, terapeuta.id, tipo, clave, desde, hasta, contenido, generado_con, proveedor
    )
    resultado = obtener(id_informe)
    resultado['mensaje'] = mensaje
    resultado['advertencia'] = advertencia
    return resultado


def _datos_del_ingreso_pti(paciente):
    ingreso = obtener_ingreso(paciente.id)
    ingreso['objetivos'] = [
        o.descripcion for o in
        ObjetivoTerapeutico.query.filter_by(id_paciente=paciente.id, activo=True)
        .order_by(ObjetivoTerapeutico.id).all()
    ]
    return ingreso


@reintentar_en_deadlock()
def editar(id_informe, contenido):
    if not isinstance(contenido, str):
        raise ErrorAplicacion('El contenido del informe es obligatorio.', campo='contenido')
    _informe_o_404(id_informe)
    terapeuta = terapeuta_actual()
    ok, mensaje = _llamar(
        'p_editar_informe', {'inf': id_informe, 'ter': terapeuta.id, 'cont': contenido}, ['ok', 'mensaje']
    )
    if not ok:
        raise ErrorAplicacion(mensaje or 'No se pudo guardar el informe.', http_status=_estado_http(mensaje))
    resultado = obtener(id_informe)
    resultado['mensaje'] = mensaje
    return resultado


@reintentar_en_deadlock()
def _publicar(id_informe, id_terapeuta):
    ok, id_paciente, mensaje = _llamar(
        'p_publicar_informe', {'inf': id_informe, 'ter': id_terapeuta}, ['ok', 'pac', 'mensaje']
    )
    if not ok:
        raise ErrorAplicacion(mensaje or 'No se pudo publicar el informe.', http_status=_estado_http(mensaje))
    return id_paciente, mensaje


def publicar(id_informe):
    _informe_o_404(id_informe)
    terapeuta = terapeuta_actual()
    id_paciente, mensaje = _publicar(id_informe, terapeuta.id)
    # Despues del commit y a mejor esfuerzo: el aviso no puede deshacer la publicacion.
    avisados = 0
    try:
        avisados = avisar_informe(id_paciente) or 0
    except Exception:  # noqa: BLE001 - cualquier fallo del aviso se registra y se sigue
        db.session.rollback()
        logger.exception('No se pudo avisar la publicacion del informe %s', id_informe)
    resultado = obtener(id_informe)
    resultado['mensaje'] = mensaje
    resultado['familiares_avisados'] = avisados
    return resultado


@reintentar_en_deadlock()
def corregir(id_informe):
    _informe_o_404(id_informe)
    terapeuta = terapeuta_actual()
    id_nuevo, mensaje = _llamar(
        'p_corregir_informe', {'inf': id_informe, 'ter': terapeuta.id}, ['id', 'mensaje']
    )
    if not id_nuevo:
        raise ErrorAplicacion(mensaje or 'No se pudo preparar la corrección.', http_status=_estado_http(mensaje))
    resultado = obtener(id_nuevo)
    resultado['mensaje'] = mensaje
    return resultado


@reintentar_en_deadlock()
def descartar(id_informe):
    _informe_o_404(id_informe)
    terapeuta = terapeuta_actual()
    ok, mensaje = _llamar(
        'p_descartar_informe', {'inf': id_informe, 'ter': terapeuta.id}, ['ok', 'mensaje']
    )
    if not ok:
        raise ErrorAplicacion(mensaje or 'No se pudo descartar el borrador.', http_status=_estado_http(mensaje))
    return {'mensaje': mensaje}


# ---------------------------------------------------------------------------
# Control mensual
# ---------------------------------------------------------------------------
def _mejor(informes):
    """El publicado si hay; si no, el borrador. Nunca los reemplazados."""
    finales = [i for i in informes if i.estado == 'final']
    if finales:
        elegido = max(finales, key=lambda i: i.version)
        pendiente = [i for i in informes if i.estado == 'borrador']
        return {'estado': 'publicado', 'id': elegido.id, 'version': elegido.version,
                'hay_borrador': bool(pendiente),
                # Correccion en curso: el borrador que reemplazara al publicado.
                'id_borrador': max(pendiente, key=lambda i: i.version).id if pendiente else None}
    borradores = [i for i in informes if i.estado == 'borrador']
    if borradores:
        elegido = max(borradores, key=lambda i: i.version)
        return {'estado': 'borrador', 'id': elegido.id, 'version': elegido.version, 'hay_borrador': True}
    return None


def control_mensual(mes=None):
    """
    La hoja del ritual mensual: los pacientes de la terapeuta en el mes y, para
    cada uno, que informes estan hechos. El semestral solo se pide en los meses
    de cierre (junio y diciembre) y el PTI solo si el paciente tiene ingreso.
    """
    terapeuta = terapeuta_actual()
    hoy = dt.date.today()
    clave, desde, hasta = generador.calcular_periodo('mensual', mes or generador.clave_mensual(hoy))
    fin_de_mes = (desde.replace(day=28) + dt.timedelta(days=4))
    fin_de_mes = fin_de_mes - dt.timedelta(days=fin_de_mes.day)
    clave_sem = generador.clave_semestral(desde)

    pacientes = (
        db.session.query(Paciente)
        .join(Asignacion, Asignacion.id_paciente == Paciente.id)
        .filter(
            Asignacion.id_terapeuta == terapeuta.id,
            Asignacion.fecha_desde <= fin_de_mes,
            or_(Asignacion.fecha_hasta.is_(None), Asignacion.fecha_hasta >= desde),
            or_(Paciente.activo.is_(True), Paciente.fecha_baja >= desde),
        )
        .order_by(Paciente.apellido, Paciente.nombre)
        .distinct().all()
    )
    ids = [p.id for p in pacientes]
    por_paciente = {i: [] for i in ids}
    con_ingreso = set()
    sesiones = {}
    if ids:
        for informe in Informe.query.filter(
            Informe.id_paciente.in_(ids), Informe.estado.in_(('borrador', 'final')),
            or_(
                (Informe.tipo == 'mensual') & (Informe.periodo == clave),
                (Informe.tipo == 'semestral') & (Informe.periodo == clave_sem),
                Informe.tipo == 'pti',
            ),
        ).all():
            por_paciente[informe.id_paciente].append(informe)
        con_ingreso = {i for (i,) in db.session.query(Ingreso.id_paciente).filter(Ingreso.id_paciente.in_(ids)).all()}
        filas = (
            db.session.query(Sesion.id_paciente, db.func.count(Sesion.id))
            .filter(Sesion.id_paciente.in_(ids), Sesion.fecha >= desde, Sesion.fecha <= hasta,
                    Sesion.estado.in_(('completa', 'ausencia')))
            .group_by(Sesion.id_paciente).all()
        )
        sesiones = {i: n for i, n in filas}

    cierra_semestre = desde.month in (6, 12)
    filas_control = []
    resumen = {'publicados': 0, 'borradores': 0, 'pendientes': 0, 'en_borrador_total': 0}
    for p in pacientes:
        propios = por_paciente[p.id]
        mensual = _mejor([i for i in propios if i.tipo == 'mensual'])
        semestral = _mejor([i for i in propios if i.tipo == 'semestral'])
        pti = _mejor([i for i in propios if i.tipo == 'pti'])
        # Cuenta todo lo que sigue abierto (mensual, semestral, PTI y
        # correcciones de publicados), no solo el borrador mensual.
        resumen['en_borrador_total'] += sum(1 for i in propios if i.estado == 'borrador')
        sin_actividad = (not p.activo) and int(sesiones.get(p.id, 0)) == 0
        if mensual is None and sin_actividad:
            # De baja y sin sesiones en el mes: no hay nada que informar.
            mensual = {'estado': 'no_corresponde'}
        elif mensual is None:
            mensual = {'estado': 'pendiente'}
            resumen['pendientes'] += 1
        elif mensual['estado'] == 'publicado':
            resumen['publicados'] += 1
        else:
            resumen['borradores'] += 1
        if semestral is None:
            semestral = {'estado': 'pendiente' if cierra_semestre else 'no_corresponde'}
        if pti is None:
            pti = {'estado': 'pendiente' if p.id in con_ingreso else 'no_corresponde'}
        filas_control.append({
            'id_paciente': p.id,
            'paciente': p.nombre_completo,
            'sesiones_registradas': int(sesiones.get(p.id, 0)),
            'mensual': mensual,
            'semestral': semestral,
            'pti': pti,
        })
    return {
        'mes': clave,
        'mes_etiqueta': generador.etiqueta_periodo('mensual', clave),
        'semestre': clave_sem,
        'cierra_semestre': cierra_semestre,
        'pacientes': filas_control,
        'total': len(filas_control),
        'resumen': resumen,
    }

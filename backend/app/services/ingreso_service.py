# backend/app/services/ingreso_service.py
# Flujo de ingreso de un paciente nuevo (Entrega 4): revision de la carpeta,
# evaluacion inicial, entrevista a la familia y PTI; al completarlo queda la
# historia clinica del centro.
#
# Las reglas (solo el terapeuta asignado escribe, etapa cerrada no se toca,
# obligatorios para cerrar, minimo de objetivos para completar) las aplican
# los procedimientos de la base. Aca se traduce y se validan formatos
# (fecha, opcion, largo), que la base no conoce.
#
# LECTURA: cualquier terapeuta (misma politica que la ficha clinica: el
# equipo puede ver a un paciente que no es suyo). El administrador NO lee
# respuestas: solo configura el formulario.

import datetime as dt
import json
import logging
import re

from sqlalchemy import text

from app import db
from app.models import (
    Asignacion, Ingreso, IngresoCampo, IngresoEtapa, IngresoRespuesta,
    ObjetivoTerapeutico, Terapeuta, Usuario,
)
from app.models.ingreso import ETAPAS, TIPOS_CAMPO
from app.services.pacientes_service import obtener_paciente
from app.services.sesiones_service import terapeuta_actual
from app.utils.db import reintentar_en_deadlock
from app.utils.errors import ErrorAplicacion

logger = logging.getLogger(__name__)

MINIMO_OBJETIVOS = 3
MAXIMO_RESPUESTA = 4000

NOMBRES_ETAPA = {
    'carpeta': 'Revisión de la carpeta',
    'evaluacion': 'Evaluación inicial',
    'entrevista': 'Entrevista a la familia',
    'pti': 'Plan terapéutico integral (PTI)',
}
DESCRIPCIONES_ETAPA = {
    'carpeta': 'Análisis de la historia clínica y los estudios que trae el paciente.',
    'evaluacion': 'Evaluación inicial del paciente según el criterio del centro.',
    'entrevista': 'Entrevista con la familia: qué observa, qué espera y cómo es su rutina.',
    'pti': 'Plan terapéutico integral: áreas a trabajar, frecuencia y coordinación.',
}


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def _estado_http(mensaje):
    texto = (mensaje or '').lower()
    if 'no existe' in texto:
        return 404
    if 'asignado' in texto and 'no tiene' in texto or 'solo el terapeuta asignado' in texto:
        return 403
    if 'ya ' in texto or 'completado' in texto or 'cerrada' in texto or 'no esta cerrada' in texto:
        return 409
    return 400


def _etapa_valida(etapa):
    if etapa not in ETAPAS:
        raise ErrorAplicacion('La etapa indicada no existe.', http_status=404)
    return etapa


def _ingreso_de(id_paciente):
    return Ingreso.query.filter_by(id_paciente=id_paciente).first()


def _ingreso_obligatorio(id_paciente):
    obtener_paciente(id_paciente, incluir_inactivos=True)
    ingreso = _ingreso_de(id_paciente)
    if ingreso is None:
        raise ErrorAplicacion('El paciente todavía no tiene un ingreso iniciado.', http_status=404)
    return ingreso


# Los mensajes de los procedimientos son ASCII (los archivos SQL no llevan
# tildes); acá se restituyen las que corresponden antes de mostrarlos.
_TILDES = {
    'clinica': 'clínica', 'quedo': 'quedó', 'esta': 'está', 'reabrala': 'reábrala',
    'interno': 'interno', 'terapeutico': 'terapéutico', 'tambien': 'también',
    'minimo': 'mínimo', 'sesion': 'sesión', 'asignacion': 'asignación',
}


def _acentuar(mensaje):
    if not mensaje:
        return mensaje
    def cambiar(m):
        palabra = m.group(0)
        nueva = _TILDES.get(palabra.lower())
        if nueva is None:
            return palabra
        return nueva.capitalize() if palabra[0].isupper() else nueva
    return re.sub(r'[A-Za-z]+', cambiar, mensaje)


def _llamar(procedimiento, argumentos, salidas):
    """CALL con OUT (@p_ok, @p_mensaje) -> (ok_o_id, mensaje). Hace commit."""
    marcadores = ', '.join(f':{k}' for k in argumentos)
    db.session.execute(
        text(f'CALL {procedimiento}({marcadores}, @p_1, @p_mensaje)'),
        argumentos,
    )
    resultado, mensaje = db.session.execute(text('SELECT @p_1, @p_mensaje')).first()
    mensaje = _acentuar(mensaje)
    db.session.commit()
    return resultado, mensaje


# ---------------------------------------------------------------------------
# Lectura del ingreso
# ---------------------------------------------------------------------------
def _campos_activos_por_etapa():
    campos = (
        IngresoCampo.query.filter_by(activo=True)
        .order_by(IngresoCampo.etapa, IngresoCampo.orden, IngresoCampo.id).all()
    )
    por_etapa = {e: [] for e in ETAPAS}
    for c in campos:
        por_etapa[c.etapa].append(c)
    return por_etapa


def _objetivos_activos(id_paciente):
    return ObjetivoTerapeutico.query.filter_by(id_paciente=id_paciente, activo=True).count()


def _nombre_terapeuta(id_terapeuta):
    fila = (
        db.session.query(Usuario.nombre, Usuario.apellido)
        .join(Terapeuta, Terapeuta.id_usuario == Usuario.id)
        .filter(Terapeuta.id == id_terapeuta).first()
    )
    return f'{fila[0]} {fila[1]}' if fila else None


def _resumen_ingreso(ingreso):
    return {
        'id': ingreso.id,
        'estado': ingreso.estado,
        'fecha_inicio': ingreso.fecha_inicio.isoformat(),
        'fecha_completado': ingreso.fecha_completado.isoformat() if ingreso.fecha_completado else None,
        'terapeuta': _nombre_terapeuta(ingreso.id_terapeuta),
    }


def obtener_ingreso(id_paciente):
    """
    Estado del ingreso con el formulario de cada etapa y lo respondido.
    Sin ingreso iniciado devuelve `ingreso: null` (no es un error: el
    paciente puede ser anterior a esta funcionalidad).
    """
    paciente = obtener_paciente(id_paciente, incluir_inactivos=True)
    ingreso = _ingreso_de(paciente.id)
    if ingreso is None:
        return {
            'ingreso': None, 'etapas': [],
            'minimo_objetivos': MINIMO_OBJETIVOS,
            'objetivos_activos': _objetivos_activos(paciente.id),
        }

    etapas_db = {
        e.etapa: e for e in IngresoEtapa.query.filter_by(id_ingreso=ingreso.id).all()
    }
    respuestas = {
        r.id_campo: r.valor
        for r in IngresoRespuesta.query.filter_by(id_ingreso=ingreso.id).all()
    }
    campos = _campos_activos_por_etapa()

    etapas = []
    for clave in ETAPAS:
        fila = etapas_db.get(clave)
        lista = []
        faltantes = 0
        for c in campos[clave]:
            datos = c.to_dict()
            datos['valor'] = respuestas.get(c.id)
            if c.obligatorio and not datos['valor']:
                faltantes += 1
            lista.append(datos)
        etapas.append({
            'etapa': clave,
            'nombre': NOMBRES_ETAPA[clave],
            'descripcion': DESCRIPCIONES_ETAPA[clave],
            'estado': fila.estado if fila else 'pendiente',
            'fecha_cierre': fila.fecha_cierre.isoformat() if fila and fila.fecha_cierre else None,
            'campos': lista,
            'obligatorios_faltantes': faltantes,
        })
    return {
        'ingreso': _resumen_ingreso(ingreso),
        'etapas': etapas,
        'minimo_objetivos': MINIMO_OBJETIVOS,
        'objetivos_activos': _objetivos_activos(paciente.id),
    }


# ---------------------------------------------------------------------------
# Escritura del flujo
# ---------------------------------------------------------------------------
@reintentar_en_deadlock()
def iniciar_ingreso(id_paciente):
    paciente = obtener_paciente(id_paciente, incluir_inactivos=True)
    terapeuta = terapeuta_actual()
    id_ingreso, mensaje = _llamar(
        'p_iniciar_ingreso', {'pac': paciente.id, 'ter': terapeuta.id}, None
    )
    if id_ingreso is None:
        raise ErrorAplicacion(mensaje or 'No se pudo iniciar el ingreso.', http_status=_estado_http(mensaje))
    logger.info('Ingreso %s iniciado para el paciente %s', id_ingreso, paciente.id)
    return obtener_ingreso(paciente.id), mensaje


def _validar_respuestas(etapa, respuestas):
    if not isinstance(respuestas, dict):
        raise ErrorAplicacion('Las respuestas tienen que enviarse como un objeto clave-valor.')
    campos = {c.clave: c for c in IngresoCampo.query.filter_by(etapa=etapa, activo=True).all()}
    lista = []
    for clave, valor in respuestas.items():
        campo = campos.get(clave)
        if campo is None:
            raise ErrorAplicacion('Hay campos que no pertenecen a esta etapa.', campo=clave)
        valor = '' if valor is None else str(valor).strip()
        if len(valor) > MAXIMO_RESPUESTA:
            raise ErrorAplicacion(
                f'"{campo.etiqueta}" no puede superar los {MAXIMO_RESPUESTA} caracteres.', campo=clave
            )
        if valor and campo.tipo == 'fecha':
            try:
                dt.date.fromisoformat(valor)
            except ValueError:
                raise ErrorAplicacion(
                    f'"{campo.etiqueta}" tiene que ser una fecha válida (AAAA-MM-DD).', campo=clave
                )
        if valor and campo.tipo == 'opcion' and valor not in campo.lista_opciones():
            raise ErrorAplicacion(f'"{campo.etiqueta}": elija una de las opciones disponibles.', campo=clave)
        lista.append({'clave': clave, 'valor': valor})
    return lista


@reintentar_en_deadlock()
def guardar_etapa(id_paciente, etapa, respuestas):
    _etapa_valida(etapa)
    ingreso = _ingreso_obligatorio(id_paciente)
    lista = _validar_respuestas(etapa, respuestas)
    terapeuta = terapeuta_actual()
    ok, mensaje = _llamar(
        'p_guardar_ingreso_etapa',
        {'ing': ingreso.id, 'ter': terapeuta.id, 'etapa': etapa,
         'resp': json.dumps(lista, ensure_ascii=False)},
        None,
    )
    if not ok:
        raise ErrorAplicacion(mensaje or 'No se pudo guardar la etapa.', http_status=_estado_http(mensaje))
    return obtener_ingreso(id_paciente), mensaje


def _transicion(procedimiento, id_paciente, etapa):
    _etapa_valida(etapa)
    ingreso = _ingreso_obligatorio(id_paciente)
    terapeuta = terapeuta_actual()
    ok, mensaje = _llamar(
        procedimiento, {'ing': ingreso.id, 'ter': terapeuta.id, 'etapa': etapa}, None
    )
    if not ok:
        raise ErrorAplicacion(mensaje or 'No se pudo completar la operación.', http_status=_estado_http(mensaje))
    return obtener_ingreso(id_paciente), mensaje


@reintentar_en_deadlock()
def cerrar_etapa(id_paciente, etapa):
    return _transicion('p_cerrar_ingreso_etapa', id_paciente, etapa)


@reintentar_en_deadlock()
def reabrir_etapa(id_paciente, etapa):
    return _transicion('p_reabrir_ingreso_etapa', id_paciente, etapa)


@reintentar_en_deadlock()
def completar_ingreso(id_paciente):
    ingreso = _ingreso_obligatorio(id_paciente)
    terapeuta = terapeuta_actual()
    ok, mensaje = _llamar(
        'p_completar_ingreso', {'ing': ingreso.id, 'ter': terapeuta.id}, None
    )
    if not ok:
        raise ErrorAplicacion(mensaje or 'No se pudo completar el ingreso.', http_status=_estado_http(mensaje))
    logger.info('Ingreso %s completado (paciente %s)', ingreso.id, id_paciente)
    return obtener_ingreso(id_paciente), mensaje


# ---------------------------------------------------------------------------
# Historia clinica del centro
# ---------------------------------------------------------------------------
def historia_clinica(id_paciente):
    """
    Historia clinica generada al completar el ingreso: datos del paciente,
    responsables, secciones con lo respondido (copia del momento de
    completar) y los objetivos activos de hoy.
    """
    paciente = obtener_paciente(id_paciente, incluir_inactivos=True)
    ingreso = _ingreso_de(paciente.id)
    if ingreso is None or ingreso.estado != 'completado':
        raise ErrorAplicacion(
            'La historia clínica se genera al completar el ingreso del paciente.',
            http_status=404,
        )

    items = ingreso.historia_clinica
    if isinstance(items, str):
        items = json.loads(items)
    items = items or []

    secciones = []
    for etapa in ETAPAS:
        propios = sorted(
            (i for i in items if i['etapa'] == etapa and i.get('valor')),
            key=lambda i: i['orden'],
        )
        secciones.append({
            'etapa': etapa,
            'nombre': NOMBRES_ETAPA[etapa],
            'campos': [
                {'clave': i['clave'], 'etiqueta': i['etiqueta'], 'tipo': i['tipo'], 'valor': i['valor']}
                for i in propios
            ],
        })

    objetivos = (
        ObjetivoTerapeutico.query.filter_by(id_paciente=paciente.id, activo=True)
        .order_by(ObjetivoTerapeutico.id).all()
    )
    responsables = (
        db.session.query(Usuario.nombre, Usuario.apellido)
        .join(Terapeuta, Terapeuta.id_usuario == Usuario.id)
        .join(Asignacion, Asignacion.id_terapeuta == Terapeuta.id)
        .filter(Asignacion.id_paciente == paciente.id, Asignacion.fecha_hasta.is_(None))
        .all()
    )
    return {
        'paciente': paciente.to_dict_clinico(),
        'ingreso': _resumen_ingreso(ingreso),
        'responsables': [f'{n} {a}' for n, a in responsables],
        'secciones': secciones,
        'objetivos': [{'id': o.id, 'descripcion': o.descripcion} for o in objetivos],
    }


# ---------------------------------------------------------------------------
# Configuracion del formulario (administrador)
# ---------------------------------------------------------------------------
_CLAVE = re.compile(r'^[a-z][a-z0-9_]{0,39}$')


def listar_campos_admin():
    campos = IngresoCampo.query.order_by(IngresoCampo.etapa, IngresoCampo.orden, IngresoCampo.id).all()
    usados = {
        fila[0] for fila in db.session.query(IngresoRespuesta.id_campo).distinct().all()
    }
    etapas = []
    for etapa in ETAPAS:
        etapas.append({
            'etapa': etapa,
            'nombre': NOMBRES_ETAPA[etapa],
            'campos': [dict(c.to_dict(), con_respuestas=c.id in usados) for c in campos if c.etapa == etapa],
        })
    return {'etapas': etapas}


def _texto(datos, clave, etiqueta, maximo, obligatorio=False):
    valor = datos.get(clave)
    valor = valor.strip() if isinstance(valor, str) else ''
    if not valor:
        if obligatorio:
            raise ErrorAplicacion(f'Falta indicar {etiqueta}.', campo=clave)
        return None
    if len(valor) > maximo:
        raise ErrorAplicacion(f'{etiqueta.capitalize()} no puede superar los {maximo} caracteres.', campo=clave)
    return valor


def _opciones(datos, tipo):
    if tipo != 'opcion':
        return None
    bruto = datos.get('opciones')
    if isinstance(bruto, str):
        bruto = [o for o in bruto.split('|')]
    lista = [str(o).strip() for o in (bruto or []) if str(o).strip()]
    if len(lista) < 2 or any('|' in o for o in lista):
        raise ErrorAplicacion('Indique al menos dos opciones.', campo='opciones')
    unido = '|'.join(lista)
    if len(unido) > 500:
        raise ErrorAplicacion('Las opciones no pueden superar los 500 caracteres en total.', campo='opciones')
    return unido


def _orden(datos, por_defecto):
    valor = datos.get('orden')
    if valor in (None, ''):
        return por_defecto
    try:
        numero = int(valor)
    except (TypeError, ValueError):
        raise ErrorAplicacion('El orden tiene que ser un número.', campo='orden')
    if not 0 <= numero <= 65000:
        raise ErrorAplicacion('El orden tiene que estar entre 0 y 65000.', campo='orden')
    return numero


def crear_campo(datos):
    etapa = _etapa_valida((datos.get('etapa') or '').strip())
    clave = (datos.get('clave') or '').strip()
    if not _CLAVE.match(clave):
        raise ErrorAplicacion(
            'La clave debe empezar con una letra minúscula y usar solo minúsculas, números y guion bajo (hasta 40 caracteres).',
            campo='clave',
        )
    etiqueta = _texto(datos, 'etiqueta', 'la etiqueta', 150, obligatorio=True)
    tipo = (datos.get('tipo') or 'texto_largo').strip()
    if tipo not in TIPOS_CAMPO:
        raise ErrorAplicacion('El tipo de campo no es válido.', campo='tipo')
    if IngresoCampo.query.filter_by(etapa=etapa, clave=clave).first():
        raise ErrorAplicacion('Ya existe un campo con esa clave en esta etapa.', http_status=409, campo='clave')

    ultimo = db.session.query(db.func.max(IngresoCampo.orden)).filter_by(etapa=etapa).scalar() or 0
    campo = IngresoCampo(
        etapa=etapa, clave=clave, etiqueta=etiqueta,
        ayuda=_texto(datos, 'ayuda', 'la ayuda', 300),
        tipo=tipo, opciones=_opciones(datos, tipo),
        obligatorio=bool(datos.get('obligatorio', False)),
        orden=_orden(datos, ultimo + 10), activo=True,
    )
    db.session.add(campo)
    db.session.commit()
    return campo.to_dict()


def editar_campo(id_campo, datos):
    campo = db.session.get(IngresoCampo, id_campo)
    if campo is None:
        raise ErrorAplicacion('El campo indicado no existe.', http_status=404)
    if 'etiqueta' in datos:
        campo.etiqueta = _texto(datos, 'etiqueta', 'la etiqueta', 150, obligatorio=True)
    if 'ayuda' in datos:
        campo.ayuda = _texto(datos, 'ayuda', 'la ayuda', 300)
    if 'opciones' in datos and campo.tipo == 'opcion':
        campo.opciones = _opciones(datos, 'opcion')
    for booleano in ('obligatorio', 'activo'):
        if booleano in datos:
            if not isinstance(datos[booleano], bool):
                raise ErrorAplicacion('El valor indicado no es válido.', campo=booleano)
            setattr(campo, booleano, datos[booleano])
    if 'orden' in datos:
        campo.orden = _orden(datos, campo.orden)
    db.session.commit()
    return campo.to_dict()

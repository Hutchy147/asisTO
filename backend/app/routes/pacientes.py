# backend/app/routes/pacientes.py
# Endpoints de pacientes. Solo el rol terapeuta.

from flask import Blueprint, jsonify, request

from app.services.pacientes_service import (
    alta_paciente, baja_paciente, editar_paciente, listar_pacientes,
    obtener_detalle, reactivar_paciente,
)
from app.services.evoluciones_service import evolucion_de_paciente
from app.services.tendencias_service import tendencias_de_paciente
from app.services.sesiones_service import listar_por_paciente as listar_sesiones_de_paciente
from app.utils.security import requiere_rol

pacientes_bp = Blueprint('pacientes', __name__)


@pacientes_bp.get('/pacientes')
@requiere_rol('terapeuta')
def listar():
    pacientes = listar_pacientes()
    return jsonify({'pacientes': pacientes, 'total': len(pacientes)}), 200


@pacientes_bp.post('/pacientes')
@requiere_rol('terapeuta')
def crear():
    datos = request.get_json(silent=True) or {}
    paciente, mensaje = alta_paciente(datos)

    return jsonify({
        'paciente': paciente.to_dict_clinico(),
        # p_mensaje del procedimiento, propagado tal cual
        'mensaje': mensaje,
    }), 201


@pacientes_bp.get('/pacientes/<int:id_paciente>')
@requiere_rol('terapeuta')
def detalle(id_paciente):
    return jsonify(obtener_detalle(id_paciente)), 200


@pacientes_bp.put('/pacientes/<int:id_paciente>')
@requiere_rol('terapeuta')
def editar(id_paciente):
    """
    Edita los datos del paciente.

    PUT y no PATCH: el formulario manda la ficha entera, no un delta. Aceptar
    PATCH obligaria a distinguir "el campo no vino" de "el campo vino vacio",
    y con `obra_social` y `diagnostico` —los dos opcionales y los dos
    borrables— esa distincion decide si se limpia el dato o se lo deja como
    estaba. Con PUT no hay ambiguedad: lo que llega es el estado final.

    NO cambia el estado de baja ni el login: para eso estan /baja,
    /reactivacion, y una operacion de vinculo que todavia no existe.
    """
    datos = request.get_json(silent=True) or {}
    paciente, mensaje = editar_paciente(id_paciente, datos)

    return jsonify({
        'paciente': paciente.to_dict_clinico(),
        'mensaje': mensaje,
    }), 200


@pacientes_bp.post('/pacientes/<int:id_paciente>/baja')
@requiere_rol('terapeuta')
def baja(id_paciente):
    """
    Baja logica del paciente.

    POST y no DELETE a proposito: DELETE anuncia que el recurso deja de
    existir, y aca no desaparece nada — el paciente sigue estando, con su
    historia entera, y hasta se puede reactivar. Un DELETE que no borra es
    una promesa falsa en el contrato de la API.
    """
    # Entrega 3: el cuerpo dice si es pausa (con motivo) o alta.
    paciente, resumen = baja_paciente(
        id_paciente, request.get_json(silent=True) or {}
    )

    return jsonify({
        'paciente': paciente.to_dict_clinico(),
        # Cuantos objetivos y asignaciones arrastro la baja. La interfaz lo
        # muestra: son efectos que el usuario no pidio explicitamente.
        'objetivos_archivados': resumen['objetivos_archivados'],
        'asignaciones_cerradas': resumen['asignaciones_cerradas'],
        'mensaje': resumen['mensaje'],
    }), 200


@pacientes_bp.post('/pacientes/<int:id_paciente>/reactivacion')
@requiere_rol('terapeuta')
def reactivacion(id_paciente):
    """
    Deshace la baja. Los objetivos archivados NO vuelven solos.

    Es un sub-recurso propio y no un PUT sobre el paciente con activo=true:
    reactivar es una operacion con reglas propias, no la edicion de un campo.
    """
    paciente, mensaje = reactivar_paciente(id_paciente)

    return jsonify({
        'paciente': paciente.to_dict_clinico(),
        'mensaje': mensaje,
    }), 200


@pacientes_bp.get('/pacientes/<int:id_paciente>/evolucion')
@requiere_rol('terapeuta')
def evolucion(id_paciente):
    """
    Serie de evolución del paciente, para el gráfico de progreso.

    Vive en este blueprint por el mismo motivo que el historial de sesiones:
    el recurso es "la evolución de este paciente", que es donde alguien la va
    a buscar. La lógica sigue estando en evoluciones_service.

    Sin `desde`/`hasta` devuelve el tratamiento entero.
    """
    return jsonify(evolucion_de_paciente(
        id_paciente,
        desde=request.args.get('desde'),
        hasta=request.args.get('hasta'),
    )), 200


@pacientes_bp.get('/pacientes/<int:id_paciente>/sesiones')
@requiere_rol('terapeuta')
def sesiones_del_paciente(id_paciente):
    """
    Historial de sesiones del paciente, de TODOS los terapeutas.

    La ruta vive en este blueprint y no en el de sesiones porque el recurso
    es "las sesiones de este paciente": es donde alguien las va a buscar.
    La logica sigue estando en sesiones_service.
    """
    return jsonify(listar_sesiones_de_paciente(id_paciente)), 200


@pacientes_bp.get('/pacientes/<int:id_paciente>/tendencias')
@requiere_rol('terapeuta')
def tendencias(id_paciente):
    """
    Tendencia por objetivo, en palabras: los últimos `dias` (30, 60, 90 o 180)
    contra los `dias` anteriores. Lectura abierta entre terapeutas.
    """
    return jsonify(tendencias_de_paciente(id_paciente, request.args.get('dias'))), 200

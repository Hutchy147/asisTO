// frontend/src/services/pacientesService.js
// Contrato: docs/api-pacientes-objetivos.md

import { construirQuery, get, post } from './api.js';

/**
 * Pacientes activos, con su cantidad de objetivos activos.
 * -> { pacientes: [...], total }
 */
export function listarPacientes() {
  return get('/pacientes');
}

/**
 * Alta de paciente.
 *
 * `id_usuario` es opcional y puede ser null: un paciente SIN login es un
 * estado valido y frecuente (menores). No es un dato faltante.
 *
 * -> { paciente, mensaje }  (mensaje = p_mensaje del procedimiento)
 */
export function crearPaciente({
  nombre,
  apellido,
  fecha_nacimiento: fechaNacimiento,
  diagnostico = null,
  nro_historia: nroHistoria,
  id_usuario: idUsuario = null,
}) {
  return post('/pacientes', {
    nombre,
    apellido,
    fecha_nacimiento: fechaNacimiento,
    diagnostico,
    nro_historia: nroHistoria,
    id_usuario: idUsuario,
  });
}

/**
 * Ficha del paciente con sus objetivos activos.
 * -> { paciente, objetivos_activos: [...] }
 *
 * 404 tanto si no existe como si esta dado de baja, con mensajes distintos.
 */
export function obtenerPaciente(idPaciente) {
  return get(`/pacientes/${idPaciente}`);
}

/**
 * Historial completo de sesiones del paciente.
 * -> { paciente, sesiones: [...], total }
 *
 * Trae las de TODOS los terapeutas, no solo las del logueado: la lectura
 * es abierta y lo restringido es cargar evolucion. Media historia clinica
 * seria peor que la historia entera.
 */
export function listarSesionesDePaciente(idPaciente) {
  return get(`/pacientes/${idPaciente}/sesiones`);
}

// Reservado para cuando el listado acepte filtros de servidor. Hoy el
// backend no los recibe, asi que se filtra en el cliente.
export function listarPacientesConFiltros(filtros = {}) {
  return get(`/pacientes${construirQuery(filtros)}`);
}

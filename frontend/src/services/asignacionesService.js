// frontend/src/services/asignacionesService.js
// HDU 11 — asignación paciente–terapeuta. Contrato: docs/api-asignaciones.md

import { get, post } from './api.js';

/** Terapeutas activos, para el selector. -> { terapeutas: [...], total } */
export function listarTerapeutas() {
  return get('/terapeutas');
}

/** Pacientes con sus asignaciones vigentes (solo administrador). */
export function listarPacientesAdmin() {
  return get('/admin/pacientes');
}

/** Historial de asignaciones del paciente. -> { id_paciente, asignaciones, vigentes } */
export function listarAsignacionesDePaciente(idPaciente) {
  return get(`/pacientes/${idPaciente}/asignaciones`);
}

/**
 * Abre una asignación. `fechaDesde` opcional (AAAA-MM-DD, sin futuro).
 * -> { asignacion, mensaje }
 */
export function abrirAsignacion(idPaciente, { idTerapeuta, fechaDesde = null }) {
  return post(`/pacientes/${idPaciente}/asignaciones`, {
    id_terapeuta: idTerapeuta,
    fecha_desde: fechaDesde || null,
  });
}

/** Cierra una asignación. `fechaHasta` opcional (por omisión, hoy). */
export function cerrarAsignacion(idAsignacion, { fechaHasta = null } = {}) {
  return post(`/asignaciones/${idAsignacion}/cierre`, {
    fecha_hasta: fechaHasta || null,
  });
}

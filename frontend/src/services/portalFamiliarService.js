// frontend/src/services/portalFamiliarService.js
// Portal del familiar (Entrega 4). Contrato: docs/api-portal-familiar.md

import { descargarArchivo, get } from './api.js';

/** Pacientes vinculados a la cuenta. -> { pacientes, total } */
export function listarPacientesVinculados() {
  return get('/familiar/pacientes');
}

/**
 * Evolución reducida de un paciente vinculado. Fechas AAAA-MM-DD opcionales;
 * sin ellas, todo el tratamiento hasta hoy.
 */
export function obtenerEvolucionVinculada(idPaciente, { desde = '', hasta = '' } = {}) {
  const parametros = new URLSearchParams();
  if (desde) parametros.set('desde', desde);
  if (hasta) parametros.set('hasta', hasta);
  const consulta = parametros.toString();
  return get(`/familiar/pacientes/${idPaciente}/evolucion${consulta ? `?${consulta}` : ''}`);
}

// --- Informes publicados (Entrega 6) ---------------------------------------

/** Informes publicados de un paciente vinculado. -> { paciente, informes, total } */
export function listarInformesVinculados(idPaciente) {
  return get(`/familiar/pacientes/${idPaciente}/informes`);
}

/** Un informe publicado, con su contenido. */
export function obtenerInformeVinculado(idPaciente, idInforme) {
  return get(`/familiar/pacientes/${idPaciente}/informes/${idInforme}`);
}

export function descargarPdfInformeVinculado(idPaciente, idInforme) {
  return descargarArchivo(`/familiar/pacientes/${idPaciente}/informes/${idInforme}/pdf`);
}

// frontend/src/services/portalFamiliarService.js
// Portal del familiar (Entrega 4). Contrato: docs/api-portal-familiar.md

import { get } from './api.js';

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

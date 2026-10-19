// frontend/src/services/portalPacienteService.js
// Portal del paciente (Entrega 6, HDU 10). Contrato: docs/api-portal-paciente.md

import { construirQuery, get } from './api.js';

/** Objetivos y progreso propios. La identidad sale del token. */
export function obtenerMiProgreso({ desde = '', hasta = '' } = {}) {
  return get(`/paciente/mi-progreso${construirQuery({ desde, hasta })}`);
}

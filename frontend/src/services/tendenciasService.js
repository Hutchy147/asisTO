// frontend/src/services/tendenciasService.js
// Tendencia por objetivo (Entrega 5). Contrato: docs/api-consulta-sesiones.md
// Todo en palabras: el servidor no devuelve promedios ni porcentajes.

import { get } from './api.js';

export const PERIODOS_TENDENCIA = [30, 60, 90, 180];
export const PERIODO_TENDENCIA_POR_DEFECTO = 30;

/**
 * Últimos `dias` días contra los `dias` anteriores.
 * -> { paciente, dias, periodo, periodo_anterior, objetivos: [{
 *      id, descripcion, activo, nivel_actual, nivel_anterior, tendencia, cambio }] }
 */
export function obtenerTendencias(idPaciente, dias = PERIODO_TENDENCIA_POR_DEFECTO) {
  return get(`/pacientes/${idPaciente}/tendencias?dias=${dias}`);
}

/** Palabra de la tendencia dentro del período. */
export const ETIQUETA_TENDENCIA = {
  mejora: 'Mejora',
  se_mantiene: 'Se mantiene',
  retrocede: 'Retrocede',
  sin_datos: 'Sin datos suficientes',
};

/** Palabra del cambio respecto del período anterior. */
export const ETIQUETA_CAMBIO = {
  mejoro: 'Mejoró',
  igual: 'Sin cambios',
  retrocedio: 'Retrocedió',
  // Mismo texto que la tendencia para el mismo caso de pocos datos (H31).
  sin_datos: 'Sin datos suficientes',
};

// frontend/src/services/objetivosService.js
// Contrato: docs/api-pacientes-objetivos.md

import { del, get, post, put } from './api.js';

export const MAXIMO_OBJETIVOS_ACTIVOS = 4;

/**
 * Objetivos del paciente separados en activos y archivados, con el cupo.
 * -> { paciente, activos: [...], archivados: [...], cupo: {maximo, usados, disponibles} }
 */
export function listarObjetivosDePaciente(idPaciente) {
  return get(`/objetivos/paciente/${idPaciente}`);
}

/**
 * Crea un objetivo activo.
 *
 * Errores esperables, los dos con mensaje ya redactado por el servidor:
 * - 400 si el paciente llego al tope de 4 activos (mensaje del trigger)
 * - 409 si ya hay otro objetivo ACTIVO con esa descripcion
 *
 * Repetir la descripcion de uno ARCHIVADO si esta permitido: es el caso
 * clinico de retomar un objetivo viejo.
 */
export function crearObjetivo({ id_paciente: idPaciente, descripcion }) {
  return post('/objetivos', { id_paciente: idPaciente, descripcion });
}

/**
 * Edita la descripcion. Solo sobre objetivos ACTIVOS.
 *
 * Un objetivo archivado tiene evoluciones historicas puntuando contra ese
 * texto, asi que su descripcion es inmutable y el servidor rechaza el
 * cambio. La interfaz no deberia ofrecer la accion sobre un archivado.
 */
export function editarObjetivo(idObjetivo, descripcion) {
  return put(`/objetivos/${idObjetivo}`, { descripcion });
}

/**
 * ARCHIVA el objetivo. No lo borra.
 *
 * Las evoluciones ya cargadas se conservan: son historia clinica. Archivar
 * libera cupo. En la interfaz la accion se llama "Archivar", nunca
 * "Eliminar" — no hay endpoint de borrado y no va a haberlo.
 */
export function archivarObjetivo(idObjetivo) {
  return del(`/objetivos/${idObjetivo}`);
}

// Habia un helper `cupoCompleto(cupo)` aca. Se borro: la ficha y el modal
// leen `cupo.disponibles <= 0` directo, que es la misma pregunta escrita
// una sola vez y en el lugar donde se usa. Tener las dos versiones era
// justamente el riesgo de duplicar en vez de traducir.

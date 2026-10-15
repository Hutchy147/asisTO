// frontend/src/services/renglonesService.js
// Notas de campo en renglones (Entrega 3). Contrato: docs/api-renglones.md

import { del, get, post, put } from './api.js';

export const MOMENTO_PLAN = 'plan';
export const MOMENTO_REGISTRO = 'registro';
export const MAXIMO_CARACTERES_RENGLON = 160;

/** Plan, registro y arrastre de una sesión. -> { plan, registro, arrastre, es_propia } */
export function listarRenglones(idSesion) {
  return get(`/sesiones/${idSesion}/renglones`);
}

export function agregarRenglon(idSesion, { momento, texto, destacado = false }) {
  return post(`/sesiones/${idSesion}/renglones`, { momento, texto, destacado });
}

export function editarRenglon(idRenglon, { texto, destacado = false }) {
  return put(`/renglones/${idRenglon}`, { texto, destacado });
}

/** `cierre`: 'hecho' | 'descartado' | null (reabrir). */
export function cerrarRenglon(idRenglon, cierre) {
  return post(`/renglones/${idRenglon}/cierre`, { cierre });
}

export function borrarRenglon(idRenglon) {
  return del(`/renglones/${idRenglon}`);
}

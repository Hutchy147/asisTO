// frontend/src/services/notificacionesService.js
// Avisos del tratamiento para el familiar (Entrega 4).
// Contrato: docs/api-notificaciones.md

import { get, post, put } from './api.js';

/** Cantidad de avisos sin leer. -> { no_leidas } */
export function contarNoLeidas() {
  return get('/familiar/notificaciones/no-leidas');
}

/**
 * Historial de avisos, del más reciente al más antiguo.
 * Filtros opcionales: tipo, leida ('0' | '1'), idPaciente.
 * -> { notificaciones, total, no_leidas }
 */
export function listarNotificaciones({ tipo = '', leida = '', idPaciente = '', limite = 50, desplazamiento = 0 } = {}) {
  const parametros = new URLSearchParams();
  if (tipo) parametros.set('tipo', tipo);
  if (leida !== '') parametros.set('leida', leida);
  if (idPaciente) parametros.set('id_paciente', idPaciente);
  parametros.set('limite', limite);
  parametros.set('desplazamiento', desplazamiento);
  return get(`/familiar/notificaciones?${parametros.toString()}`);
}

/** Marca un aviso como leído o no leído. */
export function marcarNotificacion(id, leida = true) {
  return post(`/familiar/notificaciones/${id}/lectura`, { leida });
}

/** Marca todos los avisos como leídos. */
export function marcarTodasLeidas() {
  return post('/familiar/notificaciones/lectura-masiva', {});
}

/** Tipos de aviso con su estado. -> { preferencias: [{tipo, etiqueta, descripcion, habilitada}] } */
export function obtenerPreferencias() {
  return get('/familiar/notificaciones/preferencias');
}

/** Activa o desactiva un tipo de aviso. */
export function guardarPreferencia(tipo, habilitada) {
  return put(`/familiar/notificaciones/preferencias/${tipo}`, { habilitada });
}

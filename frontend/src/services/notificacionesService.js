// frontend/src/services/notificacionesService.js
// Avisos del tratamiento para el familiar (Entrega 4).
// Contrato: docs/api-notificaciones.md

import { get } from './api.js';

/** Cantidad de avisos sin leer. -> { no_leidas } */
export function contarNoLeidas() {
  return get('/familiar/notificaciones/no-leidas');
}

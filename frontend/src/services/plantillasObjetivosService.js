// frontend/src/services/plantillasObjetivosService.js
// Plantillas de objetivos por área (Entrega 5). Contrato: docs/api-plantillas-objetivos.md

import { del, get, post, put } from './api.js';

/** -> { areas: [{ area, plantillas: [{ id, descripcion }] }], total } */
export function listarPlantillas() {
  return get('/plantillas-objetivos');
}

export function crearPlantilla({ area, descripcion }) {
  return post('/plantillas-objetivos', { area, descripcion });
}

export function editarPlantilla(id, { area, descripcion }) {
  return put(`/plantillas-objetivos/${id}`, { area, descripcion });
}

export function quitarPlantilla(id) {
  return del(`/plantillas-objetivos/${id}`);
}

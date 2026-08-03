// frontend/src/services/evolucionesService.js
// Contrato: docs/api-sesiones-evoluciones.md

import { get, post } from './api.js';

export const VALOR_MINIMO = 1;
export const VALOR_MAXIMO = 5;

/** Escala de valoracion. Las etiquetas son provisorias, faltan del diseño. */
export const ESCALA_VALORES = [
  { valor: 1, etiqueta: 'Sin logro' },
  { valor: 2, etiqueta: 'Logro inicial' },
  { valor: 3, etiqueta: 'Logro parcial' },
  { valor: 4, etiqueta: 'Logro avanzado' },
  { valor: 5, etiqueta: 'Logrado' },
];

/**
 * Registra una evolucion.
 *
 * Errores esperables, todos con el mensaje ya redactado por el servidor —
 * los tres primeros salen de los triggers y se muestran tal cual:
 * - 400 sesion en ausencia (regla 2)
 * - 400 objetivo de otro paciente (regla 3)
 * - 400 objetivo archivado (regla 4)
 * - 400 ya existe una evolucion para ese objetivo en esa sesion
 * - 409 el paciente no tiene objetivos activos
 * - 403 la sesion es de otro terapeuta
 */
export function registrarEvolucion({
  id_sesion: idSesion,
  id_objetivo: idObjetivo,
  valor,
  observaciones = null,
}) {
  return post('/evoluciones', {
    id_sesion: idSesion,
    id_objetivo: idObjetivo,
    valor,
    observaciones,
  });
}

/**
 * Evoluciones de una sesion, con la descripcion del objetivo incluida.
 * -> { id_sesion, evoluciones: [...], total }
 *
 * objetivo.activo puede ser false: se archivo DESPUES de cargar la
 * evolucion. Es historico, no un error.
 */
export function listarEvolucionesDeSesion(idSesion) {
  return get(`/evoluciones/sesion/${idSesion}`);
}

/** Valida el rango antes de mandar. El servidor tambien lo valida. */
export function valorEsValido(valor) {
  const numero = Number(valor);
  return Number.isInteger(numero) && numero >= VALOR_MINIMO && numero <= VALOR_MAXIMO;
}

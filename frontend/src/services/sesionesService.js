// frontend/src/services/sesionesService.js
// Contrato: docs/api-sesiones-evoluciones.md

import { construirQuery, get, post } from './api.js';

export const ESTADO_COMPLETA = 'completa';
export const ESTADO_INCOMPLETA = 'incompleta';
export const ESTADO_AUSENCIA = 'ausencia';

export const ESTADOS_SESION = [ESTADO_COMPLETA, ESTADO_INCOMPLETA, ESTADO_AUSENCIA];

// Tope que aplica el servidor. Se replica aca solo para avisar antes de
// mandar una request que ya se sabe que va a fallar; la validacion real es
// del backend.
export const MAXIMO_DIAS_RANGO = 366;

/**
 * Sesiones del terapeuta logueado en el rango.
 * -> { desde, hasta, sesiones: [...], total }
 *
 * Sin fechas devuelve desde hoy y 7 dias hacia adelante.
 * Un rango invertido devuelve 400, NO una lista vacia.
 */
export function listarSesiones({ desde, hasta } = {}) {
  return get(`/sesiones${construirQuery({ desde, hasta })}`);
}

/** Sesiones del dia. -> { fecha, sesiones: [...], total } */
export function listarSesionesDeHoy() {
  return get('/sesiones/hoy');
}

/**
 * Sesiones ya ocurridas, en completa o incompleta, sin ninguna evolucion.
 * Es la lista de trabajo pendiente del terapeuta.
 *
 * Las sesiones en ausencia NUNCA aparecen: no les falta evolucion, es que
 * no pueden tenerla.
 */
export function listarPendientesDeEvolucion() {
  return get('/sesiones/pendientes-evolucion');
}

/**
 * Registra una sesion.
 *
 * El terapeuta es SIEMPRE el logueado: mandar id_terapeuta no sirve de
 * nada, el servidor lo ignora.
 *
 * Si no se manda hora_fin se asume una hora de duracion.
 * El error de superposicion (regla 6) viene con la cantidad de sesiones en
 * conflicto y conviene mostrarlo junto al campo de horario.
 */
export function registrarSesion({
  id_paciente: idPaciente,
  fecha,
  hora_inicio: horaInicio,
  hora_fin: horaFin = null,
  estado = ESTADO_INCOMPLETA,
  notas = null,
}) {
  return post('/sesiones', {
    id_paciente: idPaciente,
    fecha,
    hora_inicio: horaInicio,
    hora_fin: horaFin,
    estado,
    notas,
  });
}

/**
 * Detalle con todo lo necesario para la pantalla de carga de evolucion.
 * -> { sesion, paciente, terapeuta, evoluciones, objetivos_activos }
 *
 * sesion.es_propia dice si el terapeuta logueado la atendio. Si es false,
 * la pantalla es de solo lectura.
 * objetivos_activos vacio = el paciente no tiene contra que calificar.
 */
export function obtenerSesion(idSesion) {
  return get(`/sesiones/${idSesion}`);
}

/** Estado visual de una sesion, segun la tabla del contrato. */
export function estadoDeCarga(sesion) {
  if (!sesion.admite_evolucion) return 'no_corresponde';
  return sesion.tiene_evolucion ? 'completa' : 'pendiente';
}

/** true si el terapeuta logueado puede cargarle evolucion a esta sesion. */
export function puedeCargarEvolucion(sesion) {
  return Boolean(sesion?.admite_evolucion) && sesion?.es_propia !== false;
}

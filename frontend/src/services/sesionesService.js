// frontend/src/services/sesionesService.js
// Contrato: docs/api-sesiones-evoluciones.md

import { construirQuery, get, post } from './api.js';

export const ESTADO_COMPLETA = 'completa';
export const ESTADO_INCOMPLETA = 'incompleta';
export const ESTADO_AUSENCIA = 'ausencia';

// Se borraron de aca:
//
//   ESTADOS_SESION
//     El array de los tres estados. Lo que se usa en la practica es
//     ETIQUETA_ESTADO (mas abajo), que ademas trae el texto para mostrar.
//
//   MAXIMO_DIAS_RANGO
//     Copiaba el tope de 366 dias del servidor para avisar antes de mandar
//     una request condenada. Ninguna pantalla arma un rango tan amplio: el
//     calendario pide de a una semana. El tope real lo aplica el backend.

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

// Se borraron de aca, y el segundo importa:
//
//   estadoDeCarga(sesion)
//     Categorizacion de tres vias, superada por el booleano faltaEvolucion.
//
//   puedeCargarEvolucion(sesion)
//     NO era solo codigo sin usar: estaba MAL. Devolvia true para una
//     sesion cuyo paciente no tiene ningun objetivo activo, cuando en los
//     hechos no se puede cargar nada ahi. La pregunta "puedo cargar
//     evolucion aca?" tiene una sola respuesta valida y vive en
//     ModalCargarEvolucion, que ademas necesita saber CUAL de los tres
//     motivos aplica para mostrar el aviso correcto — un booleano no
//     alcanza. Dejar la version equivocada disponible era esperar a que
//     alguien la reusara en una pantalla nueva.

/**
 * Sesion ocurrida, con estado que admite evolucion, y sin ninguna cargada:
 * es trabajo pendiente.
 *
 * Vive acá y no en cada pantalla para que el calendario y el panel usen la
 * MISMA definicion. Si una de las dos la calcula por su cuenta, en algun
 * momento van a mostrar cosas distintas sobre la misma sesion.
 */
export function faltaEvolucion(sesion) {
  return Boolean(sesion?.admite_evolucion) && !sesion?.tiene_evolucion;
}

/** Etiqueta de un estado de sesion. */
export const ETIQUETA_ESTADO = {
  [ESTADO_COMPLETA]: 'Completa',
  [ESTADO_INCOMPLETA]: 'Incompleta',
  [ESTADO_AUSENCIA]: 'Ausencia',
};

// frontend/src/services/sesionesService.js
// Contrato: docs/api-sesiones-evoluciones.md

import { construirQuery, get, post, put } from './api.js';

// No exportadas: desde que ModalRegistrarSesion y ModalEditarSesion pasaron
// a iterar OPCIONES_ESTADO_SESION en vez de armar su propio array, ningun
// archivo fuera de este las necesita. ESTADO_AUSENCIA si se exporta: los
// dos modales todavia comparan el estado elegido contra ella para decidir
// si mostrar el aviso y el label de "motivo de la ausencia".
const ESTADO_COMPLETA = 'completa';
const ESTADO_INCOMPLETA = 'incompleta';
export const ESTADO_AUSENCIA = 'ausencia';

// Quien faltó, solo cuando estado = ESTADO_AUSENCIA. Eje distinto del
// estado (ver la columna en schema.sql): ESTADOS_SESION dice QUÉ pasó,
// esto dice QUIÉN de los dos no estuvo. No exportados, mismo criterio que
// ESTADO_COMPLETA/ESTADO_INCOMPLETA: los modales no comparan contra el
// valor directo, solo iteran OPCIONES_AUSENCIA_DE (más abajo).
const AUSENCIA_DE_PACIENTE = 'paciente';
const AUSENCIA_DE_TERAPEUTA = 'terapeuta';

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
  ausencia_de: ausenciaDe = null,
  notas = null,
}) {
  return post('/sesiones', {
    id_paciente: idPaciente,
    fecha,
    hora_inicio: horaInicio,
    hora_fin: horaFin,
    estado,
    ausencia_de: ausenciaDe,
    notas,
  });
}

/**
 * Edita una sesion ya registrada.
 *
 * Editable: estado, ausencia_de, notas, fecha, hora_inicio, hora_fin.
 * id_paciente e id_terapeuta NO viajan: el endpoint los ignora por diseño
 * (el terapeuta es siempre el logueado, y no puede ser otro).
 *
 * PUT y no PATCH: el formulario manda la sesion entera. Si no se manda
 * hora_fin se asume una hora de duracion, igual que al registrar.
 *
 * Solo el terapeuta que atendio puede editar (403 si no). Contrato:
 * docs/api-sesiones-evoluciones.md.
 */
export function editarSesion(idSesion, {
  estado,
  ausencia_de: ausenciaDe = null,
  notas = null,
  fecha,
  hora_inicio: horaInicio,
  hora_fin: horaFin = null,
}) {
  return put(`/sesiones/${idSesion}`, {
    estado,
    ausencia_de: ausenciaDe,
    notas,
    fecha,
    hora_inicio: horaInicio,
    hora_fin: horaFin,
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

/**
 * Las tres opciones del radio "Estado de la sesion", con su descripcion,
 * en UN solo lugar para que ModalRegistrarSesion y ModalEditarSesion no
 * puedan divergir en el vocabulario.
 *
 * ESTE VOCABULARIO NO SE TOCA sin que lo pida un encargo explicito: se
 * rediseña en la V3, y cambiarlo antes mezclaría dos motivos distintos en
 * la misma diferencia de números (hallazgo A de AUDITORIA.md).
 */
export const OPCIONES_ESTADO_SESION = [
  {
    valor: ESTADO_COMPLETA,
    etiqueta: 'Completa',
    descripcion: 'El paciente asistió y se trabajaron los objetivos previstos.',
  },
  {
    valor: ESTADO_INCOMPLETA,
    etiqueta: 'Incompleta',
    descripcion: 'El paciente asistió pero la sesión se interrumpió o se acortó.',
  },
  {
    valor: ESTADO_AUSENCIA,
    etiqueta: 'Ausencia',
    descripcion: 'El paciente no asistió, con o sin aviso previo.',
  },
];

/**
 * Las dos opciones del radio "Quién faltó", que solo se muestra cuando el
 * estado elegido es ESTADO_AUSENCIA. Mismo criterio que
 * OPCIONES_ESTADO_SESION: un solo lugar para que los dos modales no
 * diverjan en el vocabulario.
 */
export const OPCIONES_AUSENCIA_DE = [
  { valor: AUSENCIA_DE_PACIENTE, etiqueta: 'El paciente' },
  { valor: AUSENCIA_DE_TERAPEUTA, etiqueta: 'El terapeuta' },
];

/** Etiqueta de quién faltó, para mostrar en el detalle de una sesión. */
export const ETIQUETA_AUSENCIA_DE = {
  [AUSENCIA_DE_PACIENTE]: 'el paciente',
  [AUSENCIA_DE_TERAPEUTA]: 'el terapeuta',
};

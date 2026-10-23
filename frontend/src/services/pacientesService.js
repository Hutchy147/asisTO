// frontend/src/services/pacientesService.js
// Contrato: docs/api-pacientes-objetivos.md

import { construirQuery, get, post, put } from './api.js';

// Topes de largo de los campos de texto del paciente.
//
// EL MISMO NUMERO VIVE EN TRES LUGARES y los tres se mueven en el mismo
// commit: el VARCHAR de schema.sql, MAXIMO_CARACTERES_* en
// backend/app/models/paciente.py, y esta constante. Ya nos paso con la
// descripcion de los objetivos: 180 en el formulario, nada en el servicio y
// 500 en la base, y el resultado fue que una terapeuta no podia cargar un
// objetivo real, cortado a mitad de frase y sin aviso.
export const MAXIMO_CARACTERES_NOMBRE = 100;
export const MAXIMO_CARACTERES_APELLIDO = 100;
export const MAXIMO_CARACTERES_OBRA_SOCIAL = 120;
export const MAXIMO_CARACTERES_NRO_HISTORIA = 30;

/**
 * Pacientes activos, con su cantidad de objetivos activos.
 * -> { pacientes: [...], total }
 */
export function listarPacientes() {
  return get('/pacientes');
}

/**
 * Alta de paciente.
 *
 * `id_usuario` es opcional y puede ser null: un paciente SIN login es un
 * estado valido y frecuente (menores). No es un dato faltante.
 *
 * -> { paciente, mensaje }  (mensaje = p_mensaje del procedimiento)
 */
export function crearPaciente({
  nombre,
  apellido,
  fecha_nacimiento: fechaNacimiento,
  diagnostico = null,
  nro_historia: nroHistoria,
  id_usuario: idUsuario = null,
}) {
  return post('/pacientes', {
    nombre,
    apellido,
    fecha_nacimiento: fechaNacimiento,
    diagnostico,
    nro_historia: nroHistoria,
    id_usuario: idUsuario,
  });
}

/**
 * Ficha del paciente con sus objetivos activos.
 * -> { paciente, objetivos_activos, solo_lectura, baja_arrastra }
 *
 * 404 solo si NO EXISTE. Desde el 2026-08-12 un paciente dado de baja se
 * devuelve igual, con `solo_lectura: true`: su historia clinica tiene que
 * poder consultarse. Lo que sigue rechazado es escribir sobre el.
 *
 * `baja_arrastra` trae cuantos objetivos activos y cuantas asignaciones
 * vigentes se van a tocar si se lo da de baja. Se pide JUSTO ANTES de
 * confirmar, no al abrir la ficha: entre una cosa y la otra pueden pasar
 * minutos y un numero viejo en un dialogo de confirmacion miente.
 */
export function obtenerPaciente(idPaciente) {
  return get(`/pacientes/${idPaciente}`);
}

/**
 * Edicion de los datos del paciente.
 *
 * PUT y no PATCH: se manda la ficha entera. Con `obra_social` y
 * `diagnostico`, los dos opcionales y los dos borrables, un PATCH obligaria
 * a distinguir "no vino" de "vino vacio", y esa distincion decide si se
 * limpia el dato o se lo deja como estaba.
 *
 * NO cambia el estado de baja ni el login: para eso estan darDeBajaPaciente,
 * reactivarPaciente, y una operacion de vinculo que todavia no existe.
 *
 * -> { paciente, mensaje }
 */
export function editarPaciente(idPaciente, {
  nombre,
  apellido,
  fecha_nacimiento: fechaNacimiento,
  diagnostico = null,
  obra_social: obraSocial = null,
  nro_historia: nroHistoria,
}) {
  return put(`/pacientes/${idPaciente}`, {
    nombre,
    apellido,
    fecha_nacimiento: fechaNacimiento,
    diagnostico,
    obra_social: obraSocial,
    nro_historia: nroHistoria,
  });
}

/**
 * Cierra el tratamiento. `tipo` es obligatorio desde la Entrega 3:
 *  - 'alta'  : egreso. Cierra las asignaciones vigentes y archiva los
 *              objetivos activos (la respuesta los devuelve contados).
 *  - 'pausa' : baja reversible, con `motivo` obligatorio. No toca objetivos
 *              ni asignaciones.
 * El valor por defecto es 'alta' porque es lo que hacia la baja antes.
 *
 * -> { paciente, objetivos_archivados, asignaciones_cerradas, mensaje }
 */
export function darDeBajaPaciente(idPaciente, { tipo = 'alta', motivo } = {}) {
  return post(`/pacientes/${idPaciente}/baja`, { tipo, motivo });
}

/**
 * Deshace la baja. Los objetivos archivados NO vuelven solos: los elige la
 * terapeuta al retomar el tratamiento.
 *
 * -> { paciente, mensaje }
 */
export function reactivarPaciente(idPaciente) {
  return post(`/pacientes/${idPaciente}/reactivacion`);
}

/**
 * Serie de evolución del paciente, para los gráficos de progreso.
 * -> { paciente, periodo: {desde, hasta, completo}, objetivos: [...],
 *      total_puntos, total_calificados, mensaje }
 *
 * Cada objetivo trae sus `puntos`, uno por sesión del período. Un punto con
 * `valor: null` significa "esa sesión ocurrió y este objetivo no se
 * calificó", que NO es lo mismo que que no haya habido sesión: por eso
 * viajan los dos en la misma lista y no en dos.
 *
 * Las series son los objetivos que estaban vivos en cada sesión, no los
 * activos de hoy. Si fueran los de hoy, una sesión de marzo que calificó un
 * objetivo archivado en mayo no tendría línea a la que pertenecer.
 *
 * Sin `desde`/`hasta` devuelve el tratamiento entero.
 */
export function obtenerEvolucionDePaciente(idPaciente, { desde, hasta } = {}) {
  return get(`/pacientes/${idPaciente}/evolucion${construirQuery({ desde, hasta })}`);
}

/**
 * Historial completo de sesiones del paciente.
 * -> { paciente, sesiones: [...], total }
 *
 * Trae las de TODOS los terapeutas, no solo las del logueado: la lectura
 * es abierta y lo restringido es cargar evolucion. Media historia clinica
 * seria peor que la historia entera.
 */
export function listarSesionesDePaciente(idPaciente) {
  return get(`/pacientes/${idPaciente}/sesiones`);
}

// Filtro de servidor: `estado` ('activos' | 'inactivos'). La busqueda por
// texto se sigue haciendo en el cliente.
export function listarPacientesConFiltros(filtros = {}) {
  return get(`/pacientes${construirQuery(filtros)}`);
}

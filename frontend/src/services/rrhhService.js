// frontend/src/services/rrhhService.js
// Contrato: docs/api-rrhh.md
//
// CASI SOLO LECTURA, y el "casi" es de una sola cosa.
//
// Hasta el 2026-09-14 este archivo decía SOLO LECTURA y era cierto. Hoy
// exporta UN post: la observación técnica sobre una sesión, que es el único
// camino de escritura que tiene el rol rrhh en todo el sistema.
//
// Lo que sigue sin poder escribir: pacientes, sesiones, objetivos y
// evoluciones. No es una afirmación de diseño, está medida — los diez
// endpoints de escritura le contestan 403 al rol rrhh, verificado por HTTP
// el mismo día que se abrió esta puerta.

import { construirQuery, get, post } from './api.js';

// Los tres orígenes de una ausencia, con el texto que se muestra.
//
// `sin_declarar` NO es un origen: es la ausencia de origen. Va en la misma
// tabla que los otros dos para que la pantalla los recorra igual, pero su
// texto dice explícitamente que no se atribuye a nadie. Son las ausencias
// cargadas antes de que existiera la columna `ausencia_de` (2026-09-10) y
// ese dato no se puede reponer.
export const ORIGENES_AUSENCIA = [
  {
    clave: 'paciente',
    etiqueta: 'Faltó el paciente',
    descripcion: 'El paciente no asistió.',
  },
  {
    clave: 'terapeuta',
    etiqueta: 'Faltó el terapeuta',
    descripcion: 'La sesión no se dio por ausencia del terapeuta.',
  },
  {
    clave: 'sin_declarar',
    etiqueta: 'Sin declarar',
    descripcion: 'No se registró quién faltó. No se atribuye a ninguno de los dos.',
  },
];

/**
 * Reporte de asistencias del período.
 * -> { desde, hasta, id_terapeuta, sesiones: [...], resumen: {...}, mensaje }
 *
 * `desde` y `hasta` son OBLIGATORIOS (el backend responde 400 sin ellos) y
 * van como AAAA-MM-DD. `idTerapeuta` vacío = todos.
 */
export function obtenerReporteSesiones({ desde, hasta, idTerapeuta } = {}) {
  return get(
    `/rrhh/reporte-sesiones${construirQuery({
      desde,
      hasta,
      id_terapeuta: idTerapeuta,
    })}`
  );
}

/**
 * Los terapeutas que aparecen en un reporte ya traído, para poblar el
 * filtro.
 *
 * POR QUÉ SE DERIVAN DEL REPORTE Y NO SE PIDE LA LISTA DE TERAPEUTAS: no
 * existe un endpoint de terapeutas que el rol `rrhh` pueda llamar — se
 * verificó que los 15 endpoints no-RRHH le contestan 403 — y construir uno
 * sería ampliar el alcance de RRHH sin una HDU que lo respalde. Derivarlos
 * del propio reporte alcanza para el filtro y no agrega superficie.
 *
 * La consecuencia, dicha: sólo aparecen los terapeutas CON sesiones en el
 * período. Uno que no atendió a nadie no es filtrable, y es correcto —
 * filtrar por él daría la misma lista vacía que ya se ve.
 */
export function terapeutasDelReporte(sesiones = []) {
  const porId = new Map();
  sesiones.forEach((sesion) => {
    if (sesion.id_terapeuta != null && !porId.has(sesion.id_terapeuta)) {
      porId.set(sesion.id_terapeuta, sesion.terapeuta);
    }
  });
  return [...porId.entries()]
    .map(([id, nombre]) => ({ id, nombre }))
    .sort((a, b) => a.nombre.localeCompare(b.nombre, 'es'));
}

// ---------------------------------------------------------------------
// OBSERVACIONES TECNICAS — el unico camino de ESCRITURA del modulo.
//
// El encabezado de este archivo decia "SOLO LECTURA" y dejo de ser cierto el
// 2026-09-14. Lo que NO cambio: sigue habiendo un solo POST, y es este. RRHH
// no escribe en pacientes, sesiones, objetivos ni evoluciones — verificado
// por HTTP contra los diez endpoints de escritura, que le contestan 403.
// ---------------------------------------------------------------------

/** Observaciones de una sesion, de la mas nueva a la mas vieja. */
export function listarObservaciones(idSesion) {
  return get(`/rrhh/sesiones/${idSesion}/observaciones`);
}

/**
 * Registra una observacion administrativa sobre la sesion.
 *
 * El AUTOR no se manda: lo resuelve el servidor desde el token. Mandarlo
 * dejaria que cualquiera con rol rrhh firme con el legajo de otro.
 */
export function registrarObservacion(idSesion, texto) {
  return post(`/rrhh/sesiones/${idSesion}/observaciones`, { texto });
}

/**
 * Auditoría de accesos (Entrega 3). Solo lectura.
 * -> { desde, hasta, limite, resumen: {exitoso, fallido, bloqueado, total}, accesos: [...] }
 */
export function obtenerAuditoriaAccesos({ desde, hasta, resultado, email, limite } = {}) {
  return get(`/rrhh/auditoria-accesos${construirQuery({ desde, hasta, resultado, email, limite })}`);
}

// frontend/src/utils/fechas.js
// Formateo de fechas. El backend siempre manda ISO (AAAA-MM-DD); en
// pantalla se lee dd/mm/aaaa.

/** "2026-03-02" -> "02/03/2026" */
export function formatearFecha(iso) {
  if (!iso) return null;
  const [anio, mes, dia] = iso.slice(0, 10).split('-');
  return `${dia}/${mes}/${anio}`;
}

/** "2026-03-02" -> "02/03" — para cuando el año se sobreentiende */
export function formatearFechaCorta(iso) {
  if (!iso) return null;
  const [, mes, dia] = iso.slice(0, 10).split('-');
  return `${dia}/${mes}`;
}

/** "2026-03" -> "03/2026" — desde cuándo está en tratamiento */
export function formatearMes(iso) {
  if (!iso) return null;
  const [anio, mes] = iso.slice(0, 10).split('-');
  return `${mes}/${anio}`;
}

/** Edad en años. `null` si no hay fecha. */
export function edadDesde(iso) {
  if (!iso) return null;
  const [anio, mes, dia] = iso.slice(0, 10).split('-').map(Number);
  const hoy = new Date();
  let edad = hoy.getFullYear() - anio;
  const mesActual = hoy.getMonth() + 1;
  if (mesActual < mes || (mesActual === mes && hoy.getDate() < dia)) edad -= 1;
  return edad;
}

/**
 * "7 años" y, para los menores de un año, "8 meses".
 *
 * En pediatría la edad en meses es el dato relevante hasta el año; decir
 * "0 años" no le sirve a nadie.
 */
export function textoEdad(iso) {
  const edad = edadDesde(iso);
  if (edad === null) return '';
  if (edad >= 1) return `${edad} ${edad === 1 ? 'año' : 'años'}`;

  // Con las partes del texto y no con new Date('AAAA-MM-DD'), que se lee en
  // UTC y en Argentina corre la fecha al dia anterior (y de mes, el dia 1).
  const [anio, mes, dia] = iso.slice(0, 10).split('-').map(Number);
  const hoy = new Date();
  let meses = (hoy.getFullYear() - anio) * 12 + (hoy.getMonth() + 1 - mes);
  if (hoy.getDate() < dia) meses -= 1; // el mes en curso todavia no se cumplio
  meses = Math.max(0, meses);
  return `${meses} ${meses === 1 ? 'mes' : 'meses'}`;
}

/**
 * Date -> "AAAA-MM-DD" en la hora LOCAL. toISOString() la pasa a UTC: en
 * Argentina, despues de las 21 devuelve el dia siguiente.
 */
export function aIsoLocal(fecha) {
  const p = (n) => String(n).padStart(2, '0');
  return `${fecha.getFullYear()}-${p(fecha.getMonth() + 1)}-${p(fecha.getDate())}`;
}

/**
 * Hora de la API -> "HH:MM". El backend puede mandar "8:00:00" (TIME de MySQL
 * sin cero adelante): cortar los primeros 5 caracteres daba "8:00:".
 */
export function formatearHora(hora) {
  if (!hora) return '';
  const [h, m = '00'] = String(hora).split(':');
  return `${h.padStart(2, '0')}:${m.padStart(2, '0')}`;
}

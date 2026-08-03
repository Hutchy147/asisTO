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

  const nacimiento = new Date(iso.slice(0, 10));
  const hoy = new Date();
  const meses = Math.max(
    0,
    (hoy.getFullYear() - nacimiento.getFullYear()) * 12 + hoy.getMonth() - nacimiento.getMonth()
  );
  return `${meses} ${meses === 1 ? 'mes' : 'meses'}`;
}

// frontend/src/services/api.js
// Cliente HTTP base contra la API de Flask. En desarrollo la ruta relativa
// /api la resuelve el proxy de Vite; en produccion se define VITE_API_URL.

const BASE_URL = import.meta.env.VITE_API_URL ?? '/api';

/**
 * Ejecuta una request contra la API y devuelve el JSON parseado.
 * Lanza Error con el mensaje del backend cuando la respuesta no es 2xx.
 */
export async function request(path, options = {}) {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });

  // Algunos errores (502, timeouts del proxy) no devuelven JSON valido
  let payload = null;
  const text = await response.text();
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = { mensaje: text };
    }
  }

  if (!response.ok) {
    throw new Error(payload?.mensaje ?? `Error ${response.status}`);
  }

  return payload;
}

// Ping de vida del backend. Sirve para validar que el proxy esta OK.
export function getHealth() {
  return request('/health');
}

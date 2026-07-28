// frontend/src/services/api.js
// Cliente HTTP base contra la API de Flask. En desarrollo la ruta relativa
// /api la resuelve el proxy de Vite; en produccion se define VITE_API_URL.

const BASE_URL = import.meta.env.VITE_API_URL ?? '/api';

const CLAVE_TOKEN = 'asisto_token';

// Codigos que el backend devuelve cuando la sesion ya no sirve. Se
// comparan por codigo y no por texto del mensaje: el texto puede cambiar.
const CODIGOS_SESION_INVALIDA = [
  'token_expirado',
  'token_invalido',
  'token_faltante',
  'usuario_inactivo',
];

// AuthContext se registra aca al montarse. Se guarda una sola funcion en
// vez de importar el contexto: el modulo de red no debe depender de React.
let alPerderSesion = null;

export function registrarManejadorDeSesion(callback) {
  alPerderSesion = callback;
}

export function getToken() {
  return localStorage.getItem(CLAVE_TOKEN);
}

export function setToken(token) {
  if (token) localStorage.setItem(CLAVE_TOKEN, token);
  else localStorage.removeItem(CLAVE_TOKEN);
}

/**
 * Ejecuta una request contra la API y devuelve el JSON parseado.
 * Lanza Error con el mensaje del backend cuando la respuesta no es 2xx.
 */
export async function request(path, options = {}) {
  const { omitirAuth = false, ...resto } = options;

  const headers = { 'Content-Type': 'application/json', ...resto.headers };

  const token = getToken();
  if (token && !omitirAuth) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${BASE_URL}${path}`, { ...resto, headers });

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
    const codigo = payload?.codigo;

    // Sesion vencida o invalida: se limpia el estado y se manda al login
    // UNA sola vez. omitirAuth cubre el login: si el 401 viniera de ahi,
    // avisar "sesion expirada" dispararia una redireccion sobre la
    // pantalla en la que ya estamos, que es como se arma un loop.
    if (response.status === 401 && !omitirAuth && CODIGOS_SESION_INVALIDA.includes(codigo)) {
      setToken(null);
      if (alPerderSesion) alPerderSesion(codigo);
    }

    const error = new Error(payload?.mensaje ?? `Error ${response.status}`);
    error.codigo = codigo;
    error.status = response.status;
    throw error;
  }

  return payload;
}

// Ping de vida del backend. Sirve para validar que el proxy esta OK.
export function getHealth() {
  return request('/health');
}

// --- Autenticacion -------------------------------------------------------

export function login(email, contrasena) {
  return request('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, contrasena }),
    omitirAuth: true, // todavia no hay token, y un 401 aca es normal
  });
}

export function logout() {
  return request('/auth/logout', { method: 'POST' });
}

export function getMe() {
  return request('/auth/me');
}

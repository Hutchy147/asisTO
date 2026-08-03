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

/**
 * Error de la API.
 *
 * `message` es el texto que devolvio el servidor, y se muestra TAL CUAL.
 * El backend redacta sus mensajes en castellano y para una persona —
 * varios salen directamente de los triggers de la base ("El paciente ya
 * tiene 4 objetivos activos...", "No se puede cargar evolucion: la sesion
 * esta marcada como ausencia"). Reescribirlos en el frontend solo puede
 * empeorarlos, y ademas los desincroniza cuando cambian en la base.
 */
export class ErrorApi extends Error {
  constructor(mensaje, { codigo, status, datos } = {}) {
    super(mensaje);
    this.name = 'ErrorApi';
    this.codigo = codigo ?? null;
    this.status = status ?? null;
    this.datos = datos ?? null;
  }

  // La sesion dejo de servir: el manejador global ya limpio el token
  get esDeSesion() {
    return CODIGOS_SESION_INVALIDA.includes(this.codigo);
  }

  // El rol no alcanza. NO se manda al login: la sesion es valida
  get esDePermisos() {
    return this.status === 403;
  }

  get esNoEncontrado() {
    return this.status === 404;
  }

  // Datos rechazados o estado incompatible: se muestra junto al formulario
  get esDeValidacion() {
    return this.status === 400 || this.status === 409;
  }

  // No hubo respuesta del servidor (backend caido, proxy, red)
  get esDeRed() {
    return this.status === null;
  }
}

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

/** Arma la query string ignorando los parametros vacios o nulos. */
export function construirQuery(parametros = {}) {
  const query = new URLSearchParams();
  Object.entries(parametros).forEach(([clave, valor]) => {
    if (valor !== undefined && valor !== null && valor !== '') {
      query.append(clave, valor);
    }
  });
  const texto = query.toString();
  return texto ? `?${texto}` : '';
}

/**
 * Ejecuta una request contra la API y devuelve el JSON parseado.
 * Lanza ErrorApi cuando la respuesta no es 2xx.
 */
export async function request(path, options = {}) {
  const { omitirAuth = false, ...resto } = options;

  const headers = { 'Content-Type': 'application/json', ...resto.headers };

  const token = getToken();
  if (token && !omitirAuth) {
    headers.Authorization = `Bearer ${token}`;
  }

  let response;
  try {
    response = await fetch(`${BASE_URL}${path}`, { ...resto, headers });
  } catch (fallo) {
    // fetch solo rechaza por fallo de red, no por status de error
    throw new ErrorApi(
      'No se pudo conectar con el servidor. Revisá que el backend esté levantado.',
      { codigo: 'sin_conexion' }
    );
  }

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

    throw new ErrorApi(payload?.mensaje ?? `Error ${response.status}`, {
      codigo,
      status: response.status,
      datos: payload,
    });
  }

  return payload;
}

export const get = (path) => request(path);
export const post = (path, cuerpo) =>
  request(path, { method: 'POST', body: JSON.stringify(cuerpo ?? {}) });
export const put = (path, cuerpo) =>
  request(path, { method: 'PUT', body: JSON.stringify(cuerpo ?? {}) });
export const del = (path) => request(path, { method: 'DELETE' });

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

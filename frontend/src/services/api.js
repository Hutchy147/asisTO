// frontend/src/services/api.js
// Cliente HTTP base contra la API de Flask. En desarrollo la ruta relativa
// /api la resuelve el proxy de Vite; en produccion se define VITE_API_URL.

const BASE_URL = import.meta.env.VITE_API_URL ?? '/api';

// LA SESION VIAJA EN UNA COOKIE HttpOnly que pone el backend al iniciar
// sesion: el JavaScript de la pagina no puede leerla, asi que un XSS no se
// lleva la sesion. Antes el JWT vivia en localStorage, al alcance de
// cualquier script. Aca solo queda una MARCA sin valor (si hay sesion
// abierta), para no consultar /auth/me al abrir la pantalla de login.
const CLAVE_SESION = 'asisto_sesion_abierta';
try {
  // Limpieza del esquema anterior: el token ya no se guarda en el navegador.
  localStorage.removeItem('asisto_token');
} catch { /* almacenamiento bloqueado: nada que limpiar */ }

// Cabecera propia del frontend: la defensa contra CSRF del backend la exige
// en todo pedido que modifica datos con la sesion en cookie.
const CABECERAS_CLIENTE = { 'X-AsisTO': '1' };

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
  constructor(mensaje, { codigo, campo, status, datos } = {}) {
    super(mensaje);
    this.name = 'ErrorApi';
    this.codigo = codigo ?? null;
    // Campo del formulario responsable, cuando el servidor lo pudo
    // determinar. Es metadato al lado del mensaje: el cliente NO deduce
    // nada mirando el texto, que es lo que hacía antes y se rompía si el
    // mensaje de un trigger cambiaba.
    this.campo = campo ?? null;
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

/** ¿Quedó una sesión abierta en este navegador? (la cookie la valida el servidor) */
export function haySesionGuardada() {
  try { return localStorage.getItem(CLAVE_SESION) === '1'; } catch { return false; }
}

export function marcarSesion(abierta) {
  try {
    if (abierta) localStorage.setItem(CLAVE_SESION, '1');
    else localStorage.removeItem(CLAVE_SESION);
  } catch { /* almacenamiento bloqueado: se consulta al servidor igual */ }
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

  const headers = { 'Content-Type': 'application/json', ...CABECERAS_CLIENTE, ...resto.headers };

  let response;
  try {
    // include: la cookie de sesión viaja también si la API está en otro origen.
    response = await fetch(`${BASE_URL}${path}`, { ...resto, headers, credentials: 'include' });
  } catch (fallo) {
    // fetch solo rechaza por fallo de red, no por status de error
    throw new ErrorApi(
      'No se pudo conectar con el servidor. Verifique que el servidor esté en funcionamiento.',
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
      marcarSesion(false);
      if (alPerderSesion) alPerderSesion(codigo);
    }

    throw new ErrorApi(payload?.mensaje ?? `Error ${response.status}`, {
      codigo,
      campo: payload?.campo,
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

/**
 * Descarga un archivo (PDF) que la API sirve con autenticacion. Se pide con
 * fetch (con la cookie de sesion), se arma un Blob y se dispara la descarga.
 * El nombre sale de Content-Disposition.
 */
export async function descargarArchivo(path, nombrePorOmision = 'informe.pdf') {
  let response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      headers: CABECERAS_CLIENTE,
      credentials: 'include',
    });
  } catch {
    throw new ErrorApi(
      'No se pudo conectar con el servidor. Verifique que el servidor esté en funcionamiento.',
      { codigo: 'sin_conexion' }
    );
  }
  if (!response.ok) {
    let payload = null;
    try { payload = JSON.parse(await response.text()); } catch { /* sin cuerpo JSON */ }
    if (response.status === 401 && CODIGOS_SESION_INVALIDA.includes(payload?.codigo)) {
      marcarSesion(false);
      if (alPerderSesion) alPerderSesion(payload.codigo);
    }
    throw new ErrorApi(payload?.mensaje ?? `Error ${response.status}`, {
      codigo: payload?.codigo, campo: payload?.campo, status: response.status, datos: payload,
    });
  }
  const coincidencia = /filename="?([^";]+)"?/i.exec(response.headers.get('Content-Disposition') ?? '');
  const nombre = coincidencia ? coincidencia[1] : nombrePorOmision;
  const url = URL.createObjectURL(await response.blob());
  const enlace = document.createElement('a');
  enlace.href = url;
  enlace.download = nombre;
  document.body.appendChild(enlace);
  enlace.click();
  enlace.remove();
  URL.revokeObjectURL(url);
  return nombre;
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

// Recuperacion de contrasena (Entrega 3). Publicas: no llevan token.
export function pedirRecuperacion(email) {
  return request('/auth/recuperar', {
    method: 'POST',
    body: JSON.stringify({ email }),
    omitirAuth: true,
  });
}

/** -> { vigente: bool }. Se consulta al abrir la pantalla del enlace. */
export function verificarEnlaceRecuperacion(token) {
  return request('/auth/restablecer/verificar', {
    method: 'POST',
    body: JSON.stringify({ token }),
    omitirAuth: true,
  });
}

export function restablecerContrasena(token, contrasenaNueva) {
  return request('/auth/restablecer', {
    method: 'POST',
    body: JSON.stringify({ token, contrasena_nueva: contrasenaNueva }),
    omitirAuth: true,
  });
}

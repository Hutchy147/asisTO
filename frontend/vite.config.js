// frontend/vite.config.js
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

// Puerto de Vite y destino del proxy, los dos configurables.
//
// POR QUE. Hasta el 2026-08-21 los dos valores estaban fijos en este archivo,
// y eso ataba la sonda de UI de auditoria
// (tests/frontend/test_observacion_en_pantalla.ps1) a ocupar exactamente los
// puertos 5173 y 5000. La sonda levanta su PROPIO backend contra una base
// descartable —apuntarla a la de desarrollo seria escribir en `asisto`—, asi
// que no podia convivir con un entorno de desarrollo ya levantado: o una o la
// otra.
//
// Con esto la sonda puede correr en otro par de puertos sin tocar nada de la
// aplicacion. Que FALLE cuando el puerto esta ocupado sigue estando bien y no
// se cambia: es la garantia de que nunca corre contra la base equivocada.
//
// LOS VALORES DE HOY SON LOS PREDETERMINADOS. Quien no configura nada ve
// exactamente el comportamiento anterior: Vite en 5173 y /api hacia
// 127.0.0.1:5000.
const PUERTO_VITE = 5173;
const DESTINO_API = 'http://127.0.0.1:5000';

// --- Endurecimiento de la pagina ---
// Politica de contenido: solo scripts propios (un XSS no puede cargar codigo
// de afuera ni mandar datos a otro servidor), estilos propios + los que
// inyecta MUI en linea, y las fuentes de Google. `connect-src` suma el origen
// de la API si se publica aparte (VITE_API_URL).
function politicaDeContenido(urlApi) {
  let origenApi = '';
  try { origenApi = urlApi && /^https?:/.test(urlApi) ? new URL(urlApi).origin : ''; } catch { origenApi = ''; }
  return [
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
    "font-src 'self' https://fonts.gstatic.com",
    "img-src 'self' data: blob:",
    `connect-src 'self'${origenApi ? ` ${origenApi}` : ''}`,
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
  ].join('; ');
}

// Cabeceras para el servidor de desarrollo y la vista previa del build. En
// produccion las tiene que poner el servidor web (ver docs/seguridad.md).
const CABECERAS_SEGURIDAD = {
  'X-Frame-Options': 'DENY',
  'X-Content-Type-Options': 'nosniff',
  'Referrer-Policy': 'no-referrer',
  'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
};

// La CSP va como <meta> en el build (asi viaja con los archivos aunque el
// servidor no la configure). En desarrollo no: Vite inyecta un script en
// linea para la recarga en caliente y la politica lo bloquearia.
// frame-ancestors no vale en <meta>: se saca de esa copia.
function cspEnElBuild(urlApi) {
  return {
    name: 'asisto-csp',
    apply: 'build',
    transformIndexHtml(html) {
      const meta = politicaDeContenido(urlApi).replace(/; frame-ancestors 'none'/, '');
      return html.replace('<meta charset="UTF-8" />', `<meta charset="UTF-8" />\n    <meta http-equiv="Content-Security-Policy" content="${meta}" />`);
    },
  };
}

export default defineConfig(({ mode }) => {
  // loadEnv y no process.env a secas: asi los valores tambien se pueden dejar
  // escritos en un .env del front, que es donde alguien los va a buscar.
  // El tercer argumento vacio levanta TODAS las variables y no solo las
  // VITE_*, porque estas dos son de la herramienta y nunca viajan al browser.
  const env = loadEnv(mode, process.cwd(), '');

  const puerto = Number(env.ASISTO_PUERTO_VITE) || PUERTO_VITE;
  const destino = env.ASISTO_API_URL || DESTINO_API;

  return {
    plugins: [react(), cspEnElBuild(env.VITE_API_URL)],
    preview: {
      headers: { ...CABECERAS_SEGURIDAD, 'Content-Security-Policy': politicaDeContenido(env.VITE_API_URL) },
    },
    server: {
      headers: CABECERAS_SEGURIDAD,
      port: puerto,
      // NO se pone `strictPort: true`, y es una decision. Seria mejor para
      // quien automatiza —pedir 5175 y recibir 5176 es hablarle a un servidor
      // ajeno— pero CAMBIARIA el comportamiento de hoy: Vite salta al
      // siguiente puerto libre y asi viene funcionando. La condicion de este
      // cambio era que quien no configura nada vea exactamente lo de antes.
      // Si la sonda lo necesita, que lo pida ella.
      // Proxy hacia Flask en desarrollo: el front llama /api y Vite reenvia.
      // Evita problemas de CORS y de URLs absolutas hardcodeadas.
      proxy: {
        '/api': {
          target: destino,
          changeOrigin: true,
        },
      },
    },
  };
});

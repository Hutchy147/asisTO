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

export default defineConfig(({ mode }) => {
  // loadEnv y no process.env a secas: asi los valores tambien se pueden dejar
  // escritos en un .env del front, que es donde alguien los va a buscar.
  // El tercer argumento vacio levanta TODAS las variables y no solo las
  // VITE_*, porque estas dos son de la herramienta y nunca viajan al browser.
  const env = loadEnv(mode, process.cwd(), '');

  const puerto = Number(env.ASISTO_PUERTO_VITE) || PUERTO_VITE;
  const destino = env.ASISTO_API_URL || DESTINO_API;

  return {
    plugins: [react()],
    server: {
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

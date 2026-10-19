// frontend/src/config/rutas.js
//
// QUIEN PUEDE VER QUE RUTA. Declaracion unica.
//
// POR QUE EXISTE ESTE ARCHIVO (2026-09-13). Hasta hoy esta tabla vivia
// adentro de `App.jsx`, que es el unico lugar que la necesitaba. Dejo de
// alcanzar cuando aparecio este defecto:
//
//   1. A un terapeuta se le vence la sesion parado en `/rrhh` (o sale desde
//      ahi). `RutaProtegida` manda al login guardando `state.desde = '/rrhh'`.
//   2. Entra, y `Login` mandaba al destino guardado SIN mirar el rol.
//   3. `/rrhh` no es del terapeuta -> pantalla 403, recien iniciada la sesion.
//
// Para decidir eso, `Login` necesita saber que roles alcanzan cada ruta. Y
// no puede importarlo de `App.jsx`, porque `App.jsx` importa `Login`: seria
// un ciclo. Copiar la tabla en los dos lados era la otra salida, y es
// exactamente la clase de declaracion repartida que en este proyecto ya
// divergio una vez (los tres topes de 180/500/700 de un objetivo).
//
// Asi que la tabla vive ACA, una sola vez, y la leen los dos:
//   * `App.jsx` arma sus <Route> recorriendola — no puede renderizar una
//     ruta que no este declarada, porque no tiene otra lista.
//   * `Login.jsx` la consulta con `rolPuedeVer` antes de usar el destino
//     guardado.
//
// LO QUE ESTE ARCHIVO NO ES: no es un control de acceso. El control lo hace
// `RutaProtegida` en cada navegacion y, de verdad, el backend con el rol del
// JWT. Esto solo evita mandar al usuario a una pantalla que ya sabemos que
// le va a contestar 403 — o que no existe en la entrega que se muestra.

import { hayCapacidad } from './entregas.js';

/**
 * Las rutas con dueño. `/login`, `/`, `/403` y el catch-all no estan: no
 * pertenecen a ningun rol y no se protegen.
 *
 * `capacidad` sale de la tabla de src/config/entregas.js y NO es opcional:
 * `validarRutas` hace fallar el arranque si falta o si no existe.
 */
export const RUTAS_PROTEGIDAS = [
  { ruta: '/panel', roles: ['terapeuta'], capacidad: 'panel' },
  { ruta: '/pacientes', roles: ['terapeuta'], capacidad: 'pacientes.listado' },
  { ruta: '/pacientes/:id', roles: ['terapeuta'], capacidad: 'pacientes.listado' },
  { ruta: '/calendario', roles: ['terapeuta'], capacidad: 'calendario' },
  { ruta: '/sesiones', roles: ['terapeuta'], capacidad: 'sesiones.consultar' },
  { ruta: '/informes', roles: ['terapeuta'], capacidad: 'informes.control' },
  { ruta: '/rrhh', roles: ['rrhh'], capacidad: 'rrhh.consulta' },
  { ruta: '/rrhh/auditoria', roles: ['rrhh'], capacidad: 'auditoria.accesos' },
  { ruta: '/admin', roles: ['admin'], capacidad: 'admin.asignaciones' },
  { ruta: '/admin/formularios', roles: ['admin'], capacidad: 'ingreso.configurar' },
  { ruta: '/admin/plantillas', roles: ['admin'], capacidad: 'objetivos.plantillas' },
  { ruta: '/familiar', roles: ['familiar'], capacidad: 'familiar.portal' },
  { ruta: '/familiar/notificaciones', roles: ['familiar'], capacidad: 'notificaciones' },
  { ruta: '/familiar/informes', roles: ['familiar'], capacidad: 'familiar.informes' },
  { ruta: '/paciente', roles: ['paciente'], capacidad: 'paciente.portal' },
];

/**
 * ¿El patron de una ruta declarada casa con un pathname concreto?
 *
 * Hace falta por `/pacientes/:id`: el destino guardado es `/pacientes/7`, no
 * el patron. Se compara segmento a segmento y un `:loQueSea` casa con
 * cualquier segmento NO vacio. No se usa una regex armada por concatenacion
 * para no tener que escapar el pathname, que viene de la URL.
 */
function casa(patron, pathname) {
  const esperados = patron.split('/').filter(Boolean);
  const recibidos = pathname.split('/').filter(Boolean);
  if (esperados.length !== recibidos.length) return false;
  return esperados.every((segmento, i) => (
    segmento.startsWith(':') ? recibidos[i].length > 0 : segmento === recibidos[i]
  ));
}

/**
 * ¿Un rol puede ver esa ruta EN LA ENTREGA QUE SE ESTA MOSTRANDO?
 *
 * Son las dos condiciones y hacen falta las dos:
 *
 *   1. El rol tiene que estar entre los dueños de la ruta. Si no, el destino
 *      guardado termina en la pantalla 403.
 *   2. La capacidad tiene que existir en la entrega activa. Si no, termina en
 *      "Esta pantalla todavia no existe", que para quien acaba de entrar se
 *      lee igual de roto que el 403.
 *
 * La (2) se agrego el 2026-09-13, despues de la (1) y por el mismo motivo:
 * el destino que arrastra la sesion anterior no tiene por que servir para la
 * sesion nueva. Una demostracion que cambia de usuario con `VITE_ENTREGA`
 * puesto es justo el caso donde las dos se cruzan.
 *
 * Una ruta que NO esta en la tabla devuelve `false`, y es a proposito: si no
 * sabemos de quien es, no mandamos a nadie ahi despues del login. El costo
 * de equivocarse para este lado es que el usuario entra a su propio inicio,
 * que siempre es correcto. Para el otro lado el costo es una pantalla que no
 * puede ver, que es el defecto que esto viene a cerrar.
 */
export function rolPuedeVer(rol, pathname) {
  if (!rol || typeof pathname !== 'string' || !pathname.startsWith('/')) return false;
  // Se compara contra el pathname pelado: un `desde` con query o hash no
  // tiene por que cambiar de dueño.
  const limpio = pathname.split(/[?#]/)[0];
  const declarada = RUTAS_PROTEGIDAS.find((r) => casa(r.ruta, limpio));
  if (!declarada) return false;
  return declarada.roles.includes(rol) && hayCapacidad(declarada.capacidad);
}

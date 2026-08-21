// frontend/src/config/entregas.js
//
// QUÉ PANTALLA Y QUÉ CONTROL NACE EN QUÉ ENTREGA. Este archivo es el ÚNICO
// lugar donde eso está declarado.
//
// El proyecto entrega cuatro versiones incrementales que se mapean sobre las
// versiones del User Story Map. Para mostrar una entrega vieja no se sacan
// ramas ni se duplica código: se arranca el front con `VITE_ENTREGA=1` y la
// aplicación se muestra como estaba en esa versión.
//
// POR QUÉ UNA TABLA Y NO UN `if` EN CADA COMPONENTE. Repartida, la declaración
// diverge. Es exactamente el episodio de los tres límites de 180, 500 y 700
// que costó una ronda entera: tres lugares que decían el largo máximo de un
// objetivo y ya decían cosas distintas. Acá el número vive una vez.
//
// POR QUÉ UNA VARIABLE DE ENTORNO Y NO UN SELECTOR EN LA INTERFAZ. Esto es un
// modo de DEMOSTRACIÓN, no una preferencia del usuario: nadie que use el
// sistema para trabajar tiene que poder cambiarlo sin querer. Y al no estar
// seteada por defecto, quien no configura nada —desarrollo y las cuatro
// suites— ve la versión completa sin enterarse de que esto existe.
//
// ============================================================================
// LO QUE ESTE MECANISMO **NO** CUBRE. Leerlo antes de confiar en él.
// ============================================================================
//
//   1. ES SOLO DEL LADO DEL NAVEGADOR. La API sigue respondiendo TODO en
//      cualquier modo: `PUT /api/pacientes/<id>` contesta igual con
//      VITE_ENTREGA=1. Un `curl`, la consola del navegador o un cliente viejo
//      llegan a lo que la pantalla esconde. Esto sirve para MOSTRAR una
//      entrega, no para restringir a nadie: lo que restringe de verdad son los
//      roles y las reglas de la base, que no dependen de esta tabla.
//
//   2. LA BASE ES SIEMPRE LA COMPLETA. Las 18 tablas, los 8 triggers y las 8
//      rutinas están puestas en cualquier modo. Un paciente dado de baja en
//      modo 4 sigue dado de baja si se reinicia en modo 1, y la pantalla de
//      modo 1 no tiene con qué mostrar ese estado.
//
//   3. NO HAY TEST QUE LO CUBRA. `tests/frontend` son dos barridos estáticos
//      que no montan componentes, así que nada verifica que en modo 1
//      desaparezca lo que corresponde. Se verificó a mano en el navegador; si
//      alguien cambia una clave de esta tabla, ninguna suite se va a poner en
//      rojo.
//
// ============================================================================

/** La entrega en la que el sistema está completo. Es el valor por omisión. */
export const ENTREGA_COMPLETA = 4;

/** Nombre de cada entrega, para poder decirlo en pantalla. */
export const NOMBRE_DE_ENTREGA = {
  1: 'Entrega 1 — Módulo Clínico',
  2: 'Entrega 2 — Módulo Gestión',
  3: 'Entrega 3 — Portal Familiar',
  4: 'Entrega 4 — IA y PDF',
};

/**
 * LA DECLARACIÓN. Cada capacidad, con la entrega en la que aparece.
 *
 * `nombre` es la redacción del User Story Map, no una reescritura: cuando haya
 * que discutir si algo está en la versión que corresponde, la discusión tiene
 * que ser contra el documento y no contra nuestra paráfrasis.
 *
 * Hay claves de capacidades que TODAVÍA NO EXISTEN en el código. Están a
 * propósito: cuando se construyan, la etiqueta ya está puesta y nadie tiene
 * que volver atrás a etiquetarlas. Es el caso de RRHH, del portal familiar y
 * de todo lo de la Entrega 4.
 */
export const CAPACIDADES = {
  // --- Versión 1 ---
  'auth.login': { entrega: 1, nombre: 'auth básica' },
  'pacientes.alta': { entrega: 1, nombre: 'alta de paciente' },
  'pacientes.listado': { entrega: 1, nombre: 'listado de paciente' },
  'objetivos.crud': { entrega: 1, nombre: 'CRUD de objetivos' },
  'calendario': { entrega: 1, nombre: 'calendario y marcar sesión' },
  'sesiones.registrar': { entrega: 1, nombre: 'marcar sesión' },
  'evoluciones.cargar': { entrega: 1, nombre: 'evolución básica' },
  // El panel del día NO figura en el mapa con nombre propio. Va en 1 porque
  // es la pantalla de entrada del terapeuta y sin ella la V1 no arranca en
  // ningún lado. DECISIÓN MÍA: si el mapa lo ubica en otra versión, se
  // cambia acá y en ningún otro lugar.
  'panel': { entrega: 1, nombre: 'panel del día (no figura en el mapa)' },

  // --- Versión 2 ---
  'pacientes.editar': { entrega: 2, nombre: 'editar paciente' },
  'pacientes.baja': { entrega: 2, nombre: 'dar de baja paciente' },
  'objetivos.asociar': { entrega: 2, nombre: 'asociar objetivo' },
  'sesiones.editar': { entrega: 2, nombre: 'editar sesión' },
  'evoluciones.historial': { entrega: 2, nombre: 'historial de evolución' },
  // El historial de sesiones de la ficha tampoco figura con nombre propio.
  // DECISIÓN MÍA: va con el historial de evolución, en 2, porque es la misma
  // pestaña de consulta de la ficha y en V1 no había nada que consultar.
  'sesiones.historial': { entrega: 2, nombre: 'historial de sesiones (no figura en el mapa)' },

  // --- Versión 3 ---
  'auth.recuperar': { entrega: 3, nombre: 'recuperar contraseña y bloqueo de intentos' },
  'familiar.vincular': { entrega: 3, nombre: 'vincular familiar' },
  'familiar.portal': { entrega: 3, nombre: 'portal del familiar' },
  'notas.campo': { entrega: 3, nombre: 'notas de campo' },

  // --- Versión 4 ---
  'auditoria.accesos': { entrega: 4, nombre: 'auditoría de accesos' },
  'duplas.vincular': { entrega: 4, nombre: 'vincular dupla terapéutica' },
  'objetivos.plantillas': { entrega: 4, nombre: 'plantillas de objetivos' },
  'sesiones.consultar': { entrega: 4, nombre: 'consultar sesiones registradas' },
  'notificaciones': { entrega: 4, nombre: 'notificaciones completas' },
  // RRHH NACE ETIQUETADO Y TODAVÍA NO EXISTE. Va en 4 siguiendo "consultar
  // sesiones registradas" del User Story Map.
  //
  // ⚠ CONTRADICCIÓN ANOTADA, NO RESUELTA: `CLAUDE.md` ubica el "módulo RRHH
  // con export" en la Entrega 2, y el User Story Map lo pone en la 4. Los dos
  // documentos dicen cosas distintas. No lo decido por mi cuenta; queda acá,
  // en un renglón, para que se corrija en un solo lugar cuando se defina.
  'rrhh.consulta': { entrega: 4, nombre: 'consulta de asistencias de RRHH' },
  'rrhh.export': { entrega: 4, nombre: 'export de RRHH' },
  // El portal del paciente no figura en el mapa en ninguna versión. Va en 4
  // por ser lo último que queda. DECISIÓN MÍA.
  'paciente.portal': { entrega: 4, nombre: 'portal del paciente (no figura en el mapa)' },
};

/**
 * Entrega activa. Sale de `VITE_ENTREGA` y por omisión es la completa.
 *
 * Un valor invalido NO apaga nada: cae en la completa, que es el lado seguro
 * —lo peor que puede pasar es mostrar de más en una demostración, no esconder
 * una pantalla que alguien necesita—. Pero avisa, porque un typo que muestra
 * todo en silencio se descubre delante de la gente.
 */
function resolverEntrega() {
  const crudo = import.meta.env?.VITE_ENTREGA;
  if (crudo === undefined || crudo === '') return ENTREGA_COMPLETA;

  const numero = Number.parseInt(crudo, 10);
  if (Number.isInteger(numero) && numero >= 1 && numero <= ENTREGA_COMPLETA) {
    return numero;
  }

  console.warn(
    `[entregas] VITE_ENTREGA="${crudo}" no es una entrega válida (1 a ` +
    `${ENTREGA_COMPLETA}). Se muestra la versión completa.`
  );
  return ENTREGA_COMPLETA;
}

export const ENTREGA_ACTIVA = resolverEntrega();

/** `true` si no se está mostrando una entrega recortada. */
export const ES_VERSION_COMPLETA = ENTREGA_ACTIVA >= ENTREGA_COMPLETA;

/**
 * ¿La capacidad existe en la entrega activa?
 *
 * Una clave desconocida devuelve `true` —se muestra— y grita. El criterio es
 * el mismo que arriba: fallar mostrando de más y no escondiendo. Lo que
 * impide que una pantalla nueva quede sin etiquetar no es esta función sino
 * `validarRutas`, que corre al arrancar.
 */
export function hayCapacidad(clave) {
  const capacidad = CAPACIDADES[clave];
  if (!capacidad) {
    console.error(
      `[entregas] la capacidad "${clave}" no está declarada en ` +
      'src/config/entregas.js. Se muestra igual. Agregala a la tabla.'
    );
    return true;
  }
  return capacidad.entrega <= ENTREGA_ACTIVA;
}

/**
 * Control de arranque: toda ruta tiene que declarar una capacidad, y esa
 * capacidad tiene que existir en la tabla.
 *
 * ES LO QUE HACE QUE RRHH NAZCA ETIQUETADO. Sin esto, agregar una pantalla
 * nueva sin `capacidad` la deja visible en las cuatro entregas y nadie se
 * entera hasta la demostración. Con esto, la aplicación no arranca en
 * desarrollo hasta que la etiqueta esté puesta.
 *
 * En build de producción no tira: avisa por consola. Romper una demostración
 * en vivo por una etiqueta faltante sería peor que la etiqueta faltante.
 */
export function validarRutas(rutas) {
  const problemas = rutas
    .filter((r) => !r.capacidad || !CAPACIDADES[r.capacidad])
    .map((r) => `  ${r.ruta} -> ${r.capacidad ? `capacidad "${r.capacidad}" inexistente` : 'sin capacidad'}`);

  if (problemas.length === 0) return;

  const mensaje =
    'Rutas sin etiqueta de entrega en src/config/entregas.js:\n' +
    problemas.join('\n') +
    '\n\nToda ruta declara a qué entrega pertenece. Ver el encabezado de ese archivo.';

  if (import.meta.env?.PROD) {
    console.error(`[entregas] ${mensaje}`);
    return;
  }
  throw new Error(`[entregas] ${mensaje}`);
}

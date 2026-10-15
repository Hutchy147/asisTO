// frontend/src/config/entregas.js
//
// QUÉ PANTALLA Y QUÉ CONTROL NACE EN QUÉ ENTREGA. Este archivo es el ÚNICO
// lugar donde eso está declarado.
//
// El proyecto entrega SEIS versiones incrementales, una por sprint, que se
// mapean sobre las versiones del User Story Map. Para mostrar una entrega
// vieja no se sacan ramas ni se duplica código: se arranca el front con
// `VITE_ENTREGA=1` y la aplicación se muestra como estaba en esa versión.
//
// EL REPARTO DE LAS SEIS VERSIONES Y SU CALENDARIO VIVEN EN `CLAUDE.md`, que
// es la fuente de verdad y la leen las tres terminales. Acá está sólo la
// traducción de ese reparto a claves. Si los dos difieren, manda `CLAUDE.md`
// y esta tabla está mal.
//
// REMAPEO DE CUATRO A SEIS (2026-09-08). El plan pasó de cuatro entregas a
// seis sprints. Las 26 claves se revisaron UNA POR UNA contra el reparto
// nuevo, no por traducción mecánica: NUEVE cambiaron de versión y diecisiete
// se quedaron donde estaban. La tabla completa del remapeo —valor viejo,
// valor nuevo y motivo— está en `ESTADO.md`, para poder auditarlo sin abrir
// código.
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
// suites de tests— ve la versión completa sin enterarse de que esto existe.
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
//      modo 6 sigue dado de baja si se reinicia en modo 1, y la pantalla de
//      modo 1 no tiene con qué mostrar ese estado.
//
//   3. NO HAY TEST QUE LO CUBRA. `tests/frontend` son dos barridos estáticos
//      que no montan componentes, así que nada verifica que en modo 1
//      desaparezca lo que corresponde. Se verificó a mano en el navegador; si
//      alguien cambia una clave de esta tabla, ninguna suite se va a poner en
//      rojo. Lo único falsado a mano es `validarRutas` (ver abajo).
//
// ============================================================================

/**
 * La entrega en la que el sistema está completo. Es el valor por omisión.
 *
 * TAMBIÉN FIJA EL RANGO VÁLIDO de `VITE_ENTREGA`, que es `1..ENTREGA_COMPLETA`.
 * El rango se deriva de esta constante y no está escrito aparte a propósito:
 * cuando el plan pasó de cuatro versiones a seis, mover este 4 a 6 fue lo
 * único que hizo falta para que 5 y 6 dejaran de ser valores inválidos.
 */
export const ENTREGA_COMPLETA = 6;

/**
 * Nombre de cada entrega, para poder decirlo en pantalla.
 *
 * Los nombres de la 1 a la 4 vienen del plan de cuatro versiones; los de la 5
 * y la 6 los redacté yo a partir del reparto de `CLAUDE.md`, porque el reparto
 * enumera funcionalidades y no le pone título a cada sprint. DECISIÓN MÍA: si
 * el documento de diseño les da otro nombre, se cambia acá y en ningún otro
 * lugar.
 */
export const NOMBRE_DE_ENTREGA = {
  1: 'Entrega 1 — Módulo Clínico',
  2: 'Entrega 2 — Gestión y RRHH',
  3: 'Entrega 3 — Seguridad y corrección del flujo',
  4: 'Entrega 4 — Portal Familiar',
  5: 'Entrega 5 — Duplas y plantillas',
  6: 'Entrega 6 — Informes con IA y portal del paciente',
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
 * de todo lo de la V4 en adelante.
 *
 * Al revés también pasa: hay funcionalidades del reparto que TODAVÍA NO TIENEN
 * CLAVE acá —la agenda semanal recurrente y la separación de calendario y
 * carga de la V3, y los informes con IA de la V6—. No se las inventé: no hay
 * ninguna ruta ni ningún control que las necesite todavía, y una clave que no
 * usa nadie no protege nada. Se agregan cuando se construyan.
 */
export const CAPACIDADES = {
  // --- Versión 1 (07/09, entregada) ---
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
  //
  // OJO CON LA V3: el reparto de seis mueve el registro y el análisis diario
  // AL panel del día. Eso es trabajo nuevo DENTRO de esta pantalla, no una
  // pantalla nueva, así que la clave se queda en 1. Cuando se construya, lo
  // que se etiquete será el control que se mueva, no el panel.
  'panel': { entrega: 1, nombre: 'panel del día (no figura en el mapa)' },

  // --- Versión 2 (21/09) ---
  'pacientes.editar': { entrega: 2, nombre: 'editar paciente' },
  'pacientes.baja': { entrega: 2, nombre: 'dar de baja paciente' },
  'objetivos.asociar': { entrega: 2, nombre: 'asociar objetivo' },
  'sesiones.editar': { entrega: 2, nombre: 'editar sesión' },
  'evoluciones.historial': { entrega: 2, nombre: 'historial de evolución' },
  // El historial de sesiones de la ficha tampoco figura con nombre propio.
  // DECISIÓN MÍA: va con el historial de evolución, en 2, porque es la misma
  // pestaña de consulta de la ficha y en V1 no había nada que consultar.
  'sesiones.historial': { entrega: 2, nombre: 'historial de sesiones (no figura en el mapa)' },
  // RRHH NACE ETIQUETADO Y TODAVÍA NO EXISTE.
  //
  // VENÍA EN 4 Y PASA A 2, y esto CIERRA la contradicción que estaba anotada
  // acá desde el 2026-08-21: `CLAUDE.md` lo ponía en la Entrega 2 y el mapa
  // en la 4. Quedó resuelto a favor de la 2 — la HDU6 está en el Sprint 2 —,
  // así que los dos documentos dicen ahora lo mismo y el renglón de la
  // contradicción se saca en vez de arrastrarse.
  'rrhh.consulta': { entrega: 2, nombre: 'consulta de asistencias de RRHH' },
  'rrhh.export': { entrega: 2, nombre: 'export de RRHH' },

  // --- Versión 3 (05/10) ---
  'calendario.agenda': { entrega: 3, nombre: 'calendario solo para agendar, lunes a viernes, 45 minutos' },
  // Agenda semanal recurrente: los turnos fijos de la semana y su generación.
  'pacientes.pausa': { entrega: 3, nombre: 'pausar tratamiento (baja con motivo) y dar el alta' },
  'objetivos.minimo': { entrega: 3, nombre: 'aviso de mínimo de 3 objetivos activos' },
  'agenda.recurrente': { entrega: 3, nombre: 'agenda semanal recurrente' },
  'auth.recuperar': { entrega: 3, nombre: 'recuperar contraseña y bloqueo de intentos' },
  'notas.campo': { entrega: 3, nombre: 'notas de campo' },
  // VENÍA EN 4 Y PASA A 3: el reparto de seis pone la auditoría de accesos en
  // el Sprint 3, junto con la recuperación de contraseña y el bloqueo por
  // intentos. Las tres son del mismo bloque de seguridad, así que el
  // agrupamiento se sostiene solo.
  'auditoria.accesos': { entrega: 3, nombre: 'auditoría de accesos' },
  // HDU 11 (nueva en la V3): asignación paciente–terapeuta. Cubre la pestaña
  // "Asignación" de la ficha, el responsable en el listado y el selector del
  // alta. La regla 8 (escribir solo sobre pacientes asignados) vive en la
  // base y rige en cualquier modo; esta clave solo muestra u oculta pantallas.
  'asignaciones.gestionar': { entrega: 3, nombre: 'asignación de pacientes a terapeuta responsable (HDU 11)' },

  // --- Versión 4 (19/10) ---
  // LAS DOS DEL FAMILIAR VENÍAN EN 3 Y PASAN A 4. En el plan de cuatro, el
  // portal familiar era la V3 entera; en el de seis, la V3 es seguridad y
  // agenda, y el familiar se corre un sprint.
  'familiar.vincular': { entrega: 4, nombre: 'vincular familiar' },
  // `familiar.portal` es la superficie donde el familiar consulta la
  // evolución, que es lo que el reparto pone en la V4. El acceso del familiar
  // a los INFORMES es otra cosa y llega en la V6: cuando se construya va a
  // necesitar su propia clave, no ésta.
  'familiar.portal': { entrega: 4, nombre: 'portal del familiar' },
  'notificaciones': { entrega: 4, nombre: 'notificaciones completas' },

  // --- Versión 5 (02/11) ---
  // LAS TRES VENÍAN EN 4. No es que se hayan movido "más adelante": la V4 del
  // plan viejo era la última y se repartió entre la 5 y la 6 del nuevo.
  'duplas.vincular': { entrega: 5, nombre: 'vincular dupla terapéutica' },
  'objetivos.plantillas': { entrega: 5, nombre: 'plantillas de objetivos' },
  'sesiones.consultar': { entrega: 5, nombre: 'consultar sesiones registradas' },

  // --- Versión 6 (16/11) ---
  // VENÍA EN 4 Y PASA A 6, Y YA NO ES DECISIÓN MÍA. Antes decía "no figura en
  // el mapa, va en 4 por ser lo último que queda"; el reparto de seis nombra
  // el portal del paciente explícitamente en el Sprint 6. Se saca la marca de
  // decisión propia porque ahora hay documento que lo respalda.
  'paciente.portal': { entrega: 6, nombre: 'portal del paciente' },
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
 * nueva sin `capacidad` la deja visible en las seis entregas y nadie se
 * entera hasta la demostración. Con esto, la aplicación no arranca en
 * desarrollo hasta que la etiqueta esté puesta.
 *
 * En build de producción no tira: avisa por consola. Romper una demostración
 * en vivo por una etiqueta faltante sería peor que la etiqueta faltante.
 *
 * FALSADA A MANO el 2026-08-21 y otra vez el 2026-09-08, las dos en Chrome
 * real: se agrega una ruta sin `capacidad` a `App.jsx`, la aplicación se
 * niega a arrancar y el mensaje nombra la ruta ofensora. Es el único control
 * de este archivo del que se sabe que puede ponerse en rojo.
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

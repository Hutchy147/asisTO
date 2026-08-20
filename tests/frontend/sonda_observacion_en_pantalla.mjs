// tests/frontend/sonda_observacion_en_pantalla.mjs
//
// UNA sola afirmacion: un texto guardado en la base APARECE EN LA PANTALLA.
//
// Es la asercion que habria estado en rojo desde julio. `sesiones.notas` y
// `evoluciones.observaciones` se guardaban desde la Entrega 1 y no se
// mostraban en ninguna pantalla: el dato llegaba al navegador y se
// descartaba antes del DOM. Una terapeuta ocupacional externa cargo un
// evolutivo completo y despues no encontro donde leerlo.
//
// NO ES UN FRAMEWORK Y NO TIENE QUE SERLO. Abre el navegador, entra, mira y
// afirma. Los otros seis casos que hacen falta -- la palabra clinica en vez
// del numero, el objetivo archivado, la sesion ajena, la ausencia, el token
// irrompible y la regresion lectura-vs-carga -- NO estan aca. Se agregan
// despues, cuando meter uno cueste diez renglones.
//
// El navegador es el Chrome YA INSTALADO (channel: 'chrome'), asi que
// playwright-core no descarga nada. No depende de ninguna extension ni de
// una sesion abierta a mano.
//
// Todo lo que necesita llega por variables de entorno; quien arma el mundo
// es test_observacion_en_pantalla.ps1. Este archivo no toca la base.

import { chromium } from 'playwright-core';

const BASE = process.env.SONDA_BASE_URL ?? 'http://127.0.0.1:5173';
const EMAIL = process.env.SONDA_EMAIL;
const CONTRASENA = process.env.SONDA_CONTRASENA;
const ID_PACIENTE = process.env.SONDA_ID_PACIENTE;
const TEXTO = process.env.SONDA_TEXTO;
const TIMEOUT = Number(process.env.SONDA_TIMEOUT ?? 15000);

for (const [nombre, valor] of Object.entries({
  SONDA_EMAIL: EMAIL,
  SONDA_CONTRASENA: CONTRASENA,
  SONDA_ID_PACIENTE: ID_PACIENTE,
  SONDA_TEXTO: TEXTO,
})) {
  if (!valor) {
    console.error(`FALTA la variable de entorno ${nombre}.`);
    process.exit(2);
  }
}

function paso(texto) {
  console.log(`  · ${texto}`);
}

let navegador;
try {
  // --- LOGIN POR LA API, no por el formulario ------------------------------
  // Es la parte que mas se puede complicar y esta es la forma robusta: se
  // pide el token con las credenciales del seed (publicas dentro del repo,
  // no son un secreto real) y se deja puesto en localStorage con la misma
  // clave que usa la app (`asisto_token`, services/api.js:7). Manejar el
  // formulario agrega dos selectores mas que se pueden romper por motivos
  // que no tienen nada que ver con lo que este archivo mide.
  const respuesta = await fetch(`${BASE}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: EMAIL, contrasena: CONTRASENA }),
  });
  if (!respuesta.ok) {
    console.error(`FALLO EL LOGIN: HTTP ${respuesta.status} — ${await respuesta.text()}`);
    process.exit(1);
  }
  const { token } = await respuesta.json();
  if (!token) {
    console.error('El login contesto 200 pero sin token en el cuerpo.');
    process.exit(1);
  }
  paso('token obtenido por la API');

  navegador = await chromium.launch({ channel: 'chrome', headless: true });
  const contexto = await navegador.newContext({ viewport: { width: 1366, height: 768 } });
  // addInitScript y no un setItem despues de navegar: tiene que estar ANTES
  // de que la app arranque, o el router la manda a /login.
  await contexto.addInitScript((t) => {
    window.localStorage.setItem('asisto_token', t);
  }, token);

  const pagina = await contexto.newPage();
  pagina.setDefaultTimeout(TIMEOUT);

  await pagina.goto(`${BASE}/pacientes/${ID_PACIENTE}`, { waitUntil: 'domcontentloaded' });
  paso(`ficha del paciente ${ID_PACIENTE} abierta`);

  await pagina.getByRole('tab', { name: /Sesiones/ }).click();
  paso('pestaña Sesiones');

  // La fila del historial expone role="button" y su aria-label sale de
  // `etiquetaFila` (PacienteFicha.jsx:513). Es el selector mas estable que
  // hay: si alguien le saca el rol o la etiqueta, la fila deja de ser
  // accesible por teclado y este chequeo lo dice.
  await pagina.getByRole('button', { name: /Ver el registro de la sesión/ }).first().click();
  paso('fila del historial abierta');

  const dialogo = pagina.getByRole('dialog');
  await dialogo.waitFor({ state: 'visible' });

  // ESPERAR A QUE EL MODAL TERMINE DE CARGAR, y esperar algo que este SIEMPRE
  // -- no el texto que se busca --. Si esperara el texto buscado, el caso
  // negativo tardaria el timeout entero en ponerse en rojo y no sabria
  // distinguir "no se pinto" de "todavia no llego".
  //
  // "Atendio ..." se dibuja apenas hay datos, haya o no observacion cargada
  // (ModalDetalleSesion.jsx, bloque de encabezado). El primer intento afirmaba
  // apenas el dialogo era visible y leia "Abriendo la sesion...": un rojo que
  // no significaba nada.
  await dialogo.getByText(/Atendió/).waitFor({ state: 'visible' });
  paso('contenido de la sesión cargado');

  // ---------------------------------------------------------------------
  // LA UNICA AFIRMACION DE ESTE ARCHIVO
  // ---------------------------------------------------------------------
  const visible = await dialogo.getByText(TEXTO, { exact: false }).isVisible()
    .catch(() => false);

  if (!visible) {
    const enElDom = (await dialogo.innerText()).includes(TEXTO);
    console.error('');
    console.error('FAIL  la observacion guardada NO aparece en la pantalla.');
    console.error(`      texto buscado : ${TEXTO}`);
    console.error(`      esta en el DOM del modal: ${enElDom}`);
    if (enElDom) {
      console.error('      -> el texto llego al DOM pero no se ve. Mirar overflow o color.');
    } else {
      console.error('      -> el texto NO llego al DOM: es el defecto original, el dato');
      console.error('         viaja al navegador y se descarta antes de pintarse.');
    }
    console.error('');
    console.error('Texto que SI muestra el modal:');
    console.error((await dialogo.innerText()).split('\n').map((l) => `      | ${l}`).join('\n'));
    process.exit(1);
  }

  console.log('');
  console.log('PASS  la observacion guardada en la base aparece en la pantalla.');
  process.exit(0);
} catch (error) {
  console.error('');
  console.error(`ERROR de la sonda: ${error.message}`);
  process.exit(1);
} finally {
  if (navegador) await navegador.close().catch(() => {});
}

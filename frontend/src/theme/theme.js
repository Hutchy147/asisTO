// frontend/src/theme/theme.js
// Theme centralizado de AsisTO. Fuente de verdad de la identidad visual
// en toda la app — no hardcodear colores sueltos en componentes, siempre
// consumir desde acá (theme.palette.roles.*, theme.palette.sesionEstado.*).
//
// Reconciliado contra el sistema de diseño (diseno/tokens/*.css). Los
// valores de acá y los de ahí son los mismos: si divergen, se corrigen
// juntos. Las rampas 50–800 del diseño quedan como derivados y NO entran
// enteras: solo los escalones que la app realmente usa.

import { createTheme } from '@mui/material/styles';
// Textos internos de MUI en castellano (el «Close» de los avisos, «No options»).
import { esES } from '@mui/material/locale';

// --- Núcleo (5) ---
const EUCALIPTO = '#3E8E7E'; // primary, del logo
const NAVY = '#1B3B5C';      // del logo, texto y superficies oscuras
const ARCILLA = '#C97B5A';   // acento cálido (materiales de TO)
const SALVIA = '#7FA99B';    // variante clara del eucalipto
const HUESO = '#F6F4F0';     // fondo cálido, no blanco clínico

// --- Semánticos (2) ---
const AMBAR = '#D9A441';     // sesión incompleta
const LADRILLO = '#B5544C';  // ausencia

// --- Escalones derivados que la app sí usa ---
// Los oscuros son para TEXTO sobre fondo claro: el escalón 500 de cada
// rampa no llega a contraste suficiente en una etiqueta chica.
const EUCALIPTO_700 = '#235244';
const EUCALIPTO_600 = '#2F6F60';
const EUCALIPTO_100 = '#DCEAE5';
const EUCALIPTO_50 = '#EEF5F2';
const NAVY_100 = '#DBE3EB';
const NAVY_50 = '#EDF1F5';
const ARCILLA_700 = '#8E4F34';
const ARCILLA_100 = '#F5E3D9';
const SALVIA_700 = '#4E7266';
const SALVIA_100 = '#E3EDE9';
const AMBAR_700 = '#8F6716';
const AMBAR_100 = '#F7EAD0';
const AMBAR_50 = '#FBF5E7';
const LADRILLO_700 = '#7F3831';
const LADRILLO_600 = '#9C453D';
const LADRILLO_100 = '#F1D9D6';
const LADRILLO_50 = '#F9ECEA';

// Superficies y bordes derivados del hueso
const HUESO_200 = '#EDEAE4'; // fondo hundido, encabezado de tabla, zebra
const HUESO_300 = '#E1DDD6'; // borde
const HUESO_400 = '#CBC7BF'; // borde fuerte, divisor de sección

// Grises de texto
const GRIS_500 = '#6B7280';  // text.secondary
const GRIS_400 = '#9CA3AF';  // text.disabled

const BLANCO = '#FFFFFF';

// --- Tipografía ---
// La escala arranca en 11 y sube poco: es una herramienta de trabajo con
// mucha información en pantalla, no una landing. Es deliberadamente más
// densa que los defaults de MUI.
const FUENTE_UI = 'Inter, "Helvetica Neue", Arial, sans-serif';
const FUENTE_TITULO = '"Plus Jakarta Sans", "Helvetica Neue", Arial, sans-serif';

const titulo = (fontSize, fontWeight = 600) => ({
  fontFamily: FUENTE_TITULO,
  fontSize,
  fontWeight,
  lineHeight: 1.2,
  letterSpacing: '-0.01em',
});

const theme = createTheme({
  palette: {
    primary: {
      main: EUCALIPTO,
      light: SALVIA,
      dark: EUCALIPTO_600,
      contrastText: BLANCO,
    },
    secondary: { main: NAVY, contrastText: BLANCO },
    // Acento cálido: usar con moderación (CTAs secundarios, vista familiar)
    accent: { main: ARCILLA, dark: ARCILLA_700, contrastText: BLANCO },
    background: { default: HUESO, paper: BLANCO },
    text: { primary: NAVY, secondary: GRIS_500, disabled: GRIS_400 },
    success: { main: EUCALIPTO, dark: EUCALIPTO_700, light: EUCALIPTO_50 },
    warning: { main: AMBAR, dark: AMBAR_700, light: AMBAR_50 },
    error: { main: LADRILLO, dark: LADRILLO_700, light: LADRILLO_50 },
    divider: HUESO_300,

    // Superficies y bordes. Antes había que hardcodear un gris para un
    // borde de tarjeta porque el theme no tenía ninguno.
    superficie: {
      app: HUESO,
      tarjeta: BLANCO,
      hundida: HUESO_200,   // encabezado de tabla, zebra, fondo hundido
      nav: NAVY,            // barra lateral: navy para todos los roles
      acentoSuave: EUCALIPTO_50,
      borde: HUESO_300,
      bordeFuerte: HUESO_400,
    },

    // Colores por rol. Se usan SOLO donde los roles conviven en pantalla;
    // dentro de un dashboard el rol es implícito y la barra va en navy.
    //
    // Son los escalones OSCUROS de cada rampa, no el 500, y el motivo es
    // contraste: salvia #7FA99B sobre blanco no alcanza para una etiqueta
    // con texto, #4E7266 sí. Es accesibilidad, no gusto.
    roles: {
      terapeuta: { fg: EUCALIPTO_600, bg: EUCALIPTO_100 },
      rrhh: { fg: NAVY, bg: NAVY_100 },
      familiar: { fg: ARCILLA_700, bg: ARCILLA_100 },
      paciente: { fg: SALVIA_700, bg: SALVIA_100 },
      admin: { fg: NAVY, bg: NAVY_100 },
    },

    // Estados de sesión (calendario, chips, listados) — HDU4.
    //
    // Par fg/bg y no color sólido: en una tabla densa un chip macizo pesa
    // demasiado y compite con los datos. El color se lee igual.
    //
    // Son EXACTAMENTE los tres del ENUM de la base. No hay un cuarto
    // estado: "pendiente de evolución" no es un estado de la sesión, se
    // comunica por la columna de objetivos calificados y por el bloque de
    // pendientes del panel. El chip no carga dos semánticas.
    sesionEstado: {
      completa: { fg: EUCALIPTO_700, bg: EUCALIPTO_100 },
      incompleta: { fg: AMBAR_700, bg: AMBAR_100 },
      ausencia: { fg: LADRILLO_700, bg: LADRILLO_100 },
      agendada: { fg: NAVY, bg: NAVY_100 },
    },

    // Feedback: reutiliza los semánticos. No hay azul de "info".
    feedback: {
      exito: { fg: EUCALIPTO_700, bg: EUCALIPTO_50 },
      advertencia: { fg: AMBAR_700, bg: AMBAR_50 },
      error: { fg: LADRILLO_700, bg: LADRILLO_50 },
      info: { fg: NAVY, bg: NAVY_50 },
    },
  },

  typography: {
    fontFamily: FUENTE_UI,
    fontSize: 14,
    h1: titulo(38, 700),  // login y portadas
    h2: titulo(30, 700),  // titular de estado vacío
    h3: titulo(23),       // título de pantalla
    h4: titulo(19),       // título de sección
    h5: titulo(16),       // título de tarjeta
    h6: titulo(14),       // encabezado menor
    subtitle1: { fontSize: 16, fontWeight: 500 },
    subtitle2: { fontSize: 13, fontWeight: 600 },
    body1: { fontSize: 14, lineHeight: 1.5 },
    body2: { fontSize: 13, lineHeight: 1.5 },
    caption: { fontSize: 12, color: GRIS_500 },
    // Etiqueta de columna y rótulo de dato. Siempre en mayúsculas.
    overline: {
      fontSize: 11,
      fontWeight: 600,
      letterSpacing: '0.08em',
      textTransform: 'uppercase',
      lineHeight: 1.4,
    },
    button: { fontSize: 14, textTransform: 'none', fontWeight: 600 }, // nunca UPPERCASE
  },

  shape: { borderRadius: 10 },

  // Radios con nombre. shape.borderRadius sigue siendo el general.
  formas: {
    xs: 4,    // microcontroles dentro de celdas
    sm: 8,    // botones e inputs
    md: 10,   // tarjetas, paneles, tablas
    lg: 10,   // diálogos, estados vacíos
    pill: 999,
  },

  // La app es plana: solo lo flotante proyecta sombra.
  elevaciones: {
    plana: 'none',
    popover: '0 2px 8px rgba(27, 59, 92, 0.10)',
    dialogo: '0 8px 28px rgba(27, 59, 92, 0.16)',
  },

  // Foco visible. Es accesibilidad: no quitarlo ni reemplazarlo por color.
  foco: {
    anillo: `0 0 0 3px rgba(62, 142, 126, 0.30)`,
    anilloError: `0 0 0 3px rgba(181, 84, 76, 0.28)`,
  },

  // Medidas de la app de escritorio.
  layout: {
    sidebar: 232,
    sidebarColapsada: 60,
    topbar: 56,
    contenidoMax: 1320,
    gutter: 24,
    filaDensa: 38,
    filaComoda: 46,
    control: { sm: 28, md: 34, lg: 40 },
    medidaTexto: '68ch',
  },

  // Movimiento funcional, corto, sin rebotes.
  transitions: {
    duration: { shortest: 90, shorter: 140, short: 220 },
    easing: { easeInOut: 'cubic-bezier(0.2, 0, 0.2, 1)' },
  },

  components: {
    MuiCssBaseline: {
      styleOverrides: {
        // Cifras alineadas en tablas, horarios y calificaciones. Reemplaza
        // a la familia monoespaciada, que el sistema no tiene.
        '.tabular': { fontVariantNumeric: 'tabular-nums lining-nums' },

        // TEXTO LIBRE QUE VIENE DE LA BASE. Va en todo lugar donde se
        // renderice algo que escribió una persona: descripción de objetivo,
        // diagnóstico, nombres, observaciones.
        //
        // El problema que resuelve: un texto largo SIN espacios no envuelve.
        // El navegador solo corta renglón en oportunidades de salto —espacios,
        // guiones— así que una secuencia continua es un token irrompible que
        // se pinta FUERA de su caja. Reproducido con un objetivo de 700
        // caracteres terminado en "holaaaa…": 1312 px de texto saliendo de la
        // tarjeta hacia la derecha.
        //
        // Por qué `anywhere` y no `break-word`: los dos parten la palabra al
        // llegar al borde, pero solo `anywhere` reduce además el ancho
        // min-content del elemento. Sin eso, dentro de un flex el token sigue
        // exigiendo su ancho completo y el contenedor se estira igual.
        //
        // Es UNA regla en UN lugar a propósito. Estaba repetida cero veces y
        // faltaba en seis; pegarla a mano en cada componente garantiza que el
        // próximo componente nuevo se olvide.
        '.texto-libre': { overflowWrap: 'anywhere' },

        // IMPRESION DE LA HISTORIA CLINICA (Entrega 4). Al imprimir, solo se
        // ve lo que lleva la clase `imprimible`: se ocultan el menu, la barra
        // y el resto de la ficha. Es CSS puro, sin librería de PDF: el
        // navegador ofrece "Guardar como PDF" desde el mismo diálogo.
        '@media print': {
          'body *': { visibility: 'hidden' },
          '.imprimible, .imprimible *': { visibility: 'visible' },
          '.imprimible': { position: 'absolute', left: 0, top: 0, width: '100%' },
          '.no-imprimir': { display: 'none !important' },
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: { fontWeight: 600, borderRadius: 999 },
        sizeSmall: { height: 22, fontSize: 12 },
      },
    },
    MuiButton: {
      defaultProps: { disableElevation: true },
      styleOverrides: {
        root: { borderRadius: 8, minHeight: 34 },
        sizeSmall: { minHeight: 28, fontSize: 13 },
        sizeLarge: { minHeight: 40 },
      },
    },
    MuiPaper: {
      defaultProps: { elevation: 0 },
      styleOverrides: {
        // evita el overlay gris de elevation de MUI sobre el fondo hueso
        root: { backgroundImage: 'none' },
      },
    },
    MuiDialog: {
      styleOverrides: {
        paper: { boxShadow: '0 8px 28px rgba(27, 59, 92, 0.16)', borderRadius: 10 },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        root: { fontSize: 13, padding: '0 12px', height: 38 },
        head: {
          fontSize: 11,
          fontWeight: 600,
          letterSpacing: '0.08em',
          textTransform: 'uppercase',
          color: GRIS_500,
          backgroundColor: HUESO_200,
          borderBottom: `1px solid ${HUESO_400}`,
          height: 34,
        },
      },
    },
    MuiOutlinedInput: {
      styleOverrides: { root: { borderRadius: 8 } },
    },
  },
}, esES);

export default theme;

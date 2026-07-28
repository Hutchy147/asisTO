// frontend/src/theme/theme.js
// Theme centralizado de AsisTO. Fuente de verdad de la identidad visual
// en toda la app — no hardcodear colores sueltos en componentes, siempre
// consumir desde acá (theme.palette.roles.*, theme.palette.sesionEstado.*).

import { createTheme } from '@mui/material/styles';

// --- Núcleo (5) ---
const EUCALIPTO = '#3E8E7E'; // primary, del logo
const NAVY = '#1B3B5C';      // del logo, texto y superficies oscuras
const ARCILLA = '#C97B5A';   // acento cálido (materiales de TO)
const SALVIA = '#7FA99B';    // variante clara del eucalipto
const HUESO = '#F6F4F0';     // fondo cálido, no blanco clínico

// --- Semánticos (2) ---
const AMBAR = '#D9A441';     // sesión incompleta
const LADRILLO = '#B5544C';  // ausencia

const theme = createTheme({
  palette: {
    primary: { main: EUCALIPTO, light: SALVIA, contrastText: '#FFFFFF' },
    secondary: { main: NAVY, contrastText: '#FFFFFF' },
    // Acento cálido: usar con moderación (CTAs secundarios, vista familiar)
    accent: { main: ARCILLA, contrastText: '#FFFFFF' },
    background: { default: HUESO, paper: '#FFFFFF' },
    text: { primary: NAVY, secondary: '#6B7280' },
    success: { main: EUCALIPTO },
    warning: { main: AMBAR },
    error: { main: LADRILLO },

    // Colores por rol — reutilizan el núcleo, cero colores nuevos.
    // Solo se usan donde los roles conviven en pantalla (ej: RRHH viendo
    // listados por terapeuta). Dentro de un dashboard el rol es implícito.
    roles: {
      terapeuta: EUCALIPTO,
      rrhh: NAVY,
      familiar: ARCILLA,
      paciente: SALVIA,
    },

    // Estados de sesión (calendario, chips, listados) — HDU4
    sesionEstado: {
      completa: EUCALIPTO,
      incompleta: AMBAR,
      ausencia: LADRILLO,
    },
  },
  typography: {
    fontFamily: 'Inter, "Helvetica Neue", Arial, sans-serif',
    h1: { fontFamily: '"Plus Jakarta Sans", sans-serif', fontWeight: 700 },
    h2: { fontFamily: '"Plus Jakarta Sans", sans-serif', fontWeight: 700 },
    h3: { fontFamily: '"Plus Jakarta Sans", sans-serif', fontWeight: 600 },
    h4: { fontFamily: '"Plus Jakarta Sans", sans-serif', fontWeight: 600 },
    h5: { fontFamily: '"Plus Jakarta Sans", sans-serif', fontWeight: 600 },
    h6: { fontFamily: '"Plus Jakarta Sans", sans-serif', fontWeight: 600 },
    button: { textTransform: 'none', fontWeight: 600 }, // nunca UPPERCASE
  },
  shape: { borderRadius: 10 },
  components: {
    MuiChip: { styleOverrides: { root: { fontWeight: 600 } } },
    MuiButton: { styleOverrides: { root: { borderRadius: 8 } } },
    // evita el overlay gris de elevation de MUI sobre el fondo hueso
    MuiPaper: { styleOverrides: { root: { backgroundImage: 'none' } } },
  },
});

export default theme;

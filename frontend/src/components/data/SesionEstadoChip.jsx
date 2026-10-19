// frontend/src/components/data/SesionEstadoChip.jsx
// Chip de estado de sesion (HDU4).
//
// Par fg/bg con punto, no color solido: en una tabla densa un chip macizo
// pesa demasiado y compite con los datos.
//
// Muestra UNICAMENTE el estado clinico de la sesion: los tres valores del
// ENUM de la base. No existe un cuarto estado "pendiente" — que una sesion
// ocurrida no tenga evolucion cargada es trabajo pendiente, no un estado
// de la sesion, y se comunica por la columna de objetivos calificados y
// por el bloque de pendientes del panel. El chip no carga dos semanticas.
//
// Tampoco hay estado "futura": en la Entrega 1 las sesiones se registran
// cuando ocurren o despues, y siempre con estado. No hay agenda a futuro.

import Box from '@mui/material/Box';

const ETIQUETAS = {
  completa: 'Completa',
  incompleta: 'Incompleta',
  ausencia: 'Ausencia',
};

export default function SesionEstadoChip({ estado, etiqueta: etiquetaPropia }) {
  // `etiqueta` permite mostrar el estado visible (ver estadoVisible) sin
  // cambiar el color por estado declarado.
  const etiqueta = etiquetaPropia ?? ETIQUETAS[estado] ?? estado;

  return (
    <Box
      component="span"
      sx={(t) => {
        const colores = t.palette.sesionEstado[estado] ?? {
          fg: t.palette.text.secondary,
          bg: t.palette.superficie.hundida,
        };
        return {
          display: 'inline-flex',
          alignItems: 'center',
          gap: 0.75,
          fontSize: 12,
          fontWeight: 600,
          lineHeight: 1.6,
          px: 1,
          py: '2px',
          borderRadius: `${t.formas.pill}px`,
          whiteSpace: 'nowrap',
          color: colores.fg,
          backgroundColor: colores.bg,
        };
      }}
    >
      <Box
        component="i"
        aria-hidden="true"
        sx={{ width: 6, height: 6, borderRadius: '50%', backgroundColor: 'currentColor', flex: 'none' }}
      />
      {etiqueta}
    </Box>
  );
}

// frontend/src/components/SesionEstadoChip.jsx
// Chip de estado de sesion (HDU4). El color sale siempre de
// palette.sesionEstado, nunca de un hex local.

import Chip from '@mui/material/Chip';

const LABELS = {
  completa: 'Completa',
  incompleta: 'Incompleta',
  ausencia: 'Ausencia',
};

export default function SesionEstadoChip({ estado }) {
  return (
    <Chip
      size="small"
      label={LABELS[estado] ?? estado}
      sx={(theme) => ({
        backgroundColor: theme.palette.sesionEstado[estado],
        color: theme.palette.primary.contrastText,
      })}
    />
  );
}

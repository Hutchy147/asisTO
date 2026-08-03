// frontend/src/components/data/PersonCell.jsx
// Celda de persona: avatar con iniciales, nombre y un dato de contexto.

import Avatar from '@mui/material/Avatar';
import Box from '@mui/material/Box';

function iniciales(nombre = '') {
  return nombre
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((parte) => parte[0]?.toUpperCase() ?? '')
    .join('');
}

export default function PersonCell({ nombre, meta }) {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25, minWidth: 0 }}>
      <Avatar
        sx={(t) => ({
          width: 26,
          height: 26,
          fontSize: 11,
          fontWeight: 600,
          flex: 'none',
          color: t.palette.roles.terapeuta.fg,
          backgroundColor: t.palette.roles.terapeuta.bg,
        })}
      >
        {iniciales(nombre)}
      </Avatar>
      <Box sx={{ minWidth: 0, display: 'flex', flexDirection: 'column' }}>
        <Box
          component="span"
          sx={{
            fontSize: 13,
            // Interlineado ajustado a proposito: con el 1.5 heredado, dos
            // lineas no entran en la fila densa de 38px y la tabla entera
            // se estira.
            lineHeight: 1.3,
            fontWeight: 600,
            color: 'text.primary',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {nombre}
        </Box>
        {meta && (
          <Box component="span" sx={{ fontSize: 12, lineHeight: 1.25, color: 'text.secondary' }}>
            {meta}
          </Box>
        )}
      </Box>
    </Box>
  );
}

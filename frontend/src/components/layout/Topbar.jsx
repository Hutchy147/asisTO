// frontend/src/components/layout/Topbar.jsx
// Barra superior de pantalla: titulo de la vista, contexto y acciones.

import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';

export default function Topbar({ titulo, subtitulo, acciones }) {
  return (
    <Box
      component="header"
      sx={(t) => ({
        height: t.layout.topbar,
        flex: 'none',
        display: 'flex',
        alignItems: 'center',
        gap: 2,
        px: 3,
        backgroundColor: t.palette.superficie.tarjeta,
        borderBottom: `1px solid ${t.palette.superficie.borde}`,
      })}
    >
      <Box sx={{ flex: '1 1 auto', minWidth: 0, display: 'flex', flexDirection: 'column' }}>
        <Typography variant="h4" noWrap>
          {titulo}
        </Typography>
        {subtitulo && (
          <Typography variant="caption" noWrap>
            {subtitulo}
          </Typography>
        )}
      </Box>
      {acciones && (
        <Box sx={{ ml: 'auto', display: 'flex', alignItems: 'center', gap: 1 }}>{acciones}</Box>
      )}
    </Box>
  );
}

// frontend/src/components/estado/Cargando.jsx

import Box from '@mui/material/Box';
import CircularProgress from '@mui/material/CircularProgress';
import Typography from '@mui/material/Typography';

/**
 * Estado de carga. Sin diseño final: la forma la define el template.
 *
 * `minHeight` reserva el alto para que el contenido no salte cuando
 * termina de cargar.
 */
export default function Cargando({ texto = 'Cargando...', minHeight = 200 }) {
  return (
    <Box
      sx={{
        minHeight,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 2,
      }}
    >
      <CircularProgress />
      {texto && (
        <Typography variant="body2" color="text.secondary">
          {texto}
        </Typography>
      )}
    </Box>
  );
}

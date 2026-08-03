// frontend/src/components/estado/EstadoVacio.jsx

import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Typography from '@mui/material/Typography';

/**
 * "No hay nada todavia". Distinto de un error: acá el pedido funcionó.
 *
 * Siempre lleva un `titulo` que diga qué falta, y cuando corresponde una
 * acción para resolverlo. Una lista vacía sin explicación se lee como si
 * la pantalla estuviera rota.
 */
export default function EstadoVacio({
  titulo,
  descripcion,
  textoAccion,
  onAccion,
  minHeight = 200,
}) {
  return (
    <Box
      sx={{
        minHeight,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        textAlign: 'center',
        gap: 1,
        p: 3,
      }}
    >
      <Typography variant="h6">{titulo}</Typography>
      {descripcion && (
        <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 460 }}>
          {descripcion}
        </Typography>
      )}
      {textoAccion && onAccion && (
        <Button variant="contained" onClick={onAccion} sx={{ mt: 2 }}>
          {textoAccion}
        </Button>
      )}
    </Box>
  );
}

// frontend/src/components/estado/EstadoVacio.jsx

import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';

/**
 * "No hay nada todavia". Distinto de un error: acá el pedido funcionó.
 *
 * Siempre lleva un `titulo` que diga qué falta, y cuando corresponde una
 * acción para resolverlo. Una lista vacía sin explicación se lee como si
 * la pantalla estuviera rota.
 *
 * `plano` lo saca de su caja: se usa cuando ya está adentro de una tarjeta
 * y una segunda caja punteada sobraría.
 */
export default function EstadoVacio({ titulo, descripcion, acciones, plano = false }) {
  return (
    <Box
      sx={(t) => ({
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        textAlign: 'center',
        gap: 1.5,
        px: 3,
        py: plano ? 5 : 6,
        fontFamily: t.typography.fontFamily,
        ...(plano
          ? { backgroundColor: 'transparent' }
          : {
              backgroundColor: t.palette.superficie.tarjeta,
              border: `1px dashed ${t.palette.superficie.bordeFuerte}`,
              borderRadius: `${t.formas.lg}px`,
            }),
      })}
    >
      <Typography variant="h3" component="p" sx={{ m: 0 }}>
        {titulo}
      </Typography>
      {descripcion && (
        <Typography
          variant="body1"
          color="text.secondary"
          sx={{ maxWidth: '44ch', lineHeight: 1.65, m: 0 }}
        >
          {descripcion}
        </Typography>
      )}
      {acciones && <Box sx={{ display: 'flex', gap: 1, mt: 0.5 }}>{acciones}</Box>}
    </Box>
  );
}

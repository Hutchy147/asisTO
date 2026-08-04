// frontend/src/components/data/StatTile.jsx
// Cifra de cabecera del panel. Sin íconos ni flechas de tendencia
// decorativas: el número y qué significa, nada más.

import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';

export default function StatTile({ etiqueta, valor, unidad, nota }) {
  return (
    <Box
      sx={(t) => ({
        display: 'flex',
        flexDirection: 'column',
        gap: 0.5,
        px: 2,
        py: 1.5,
        backgroundColor: t.palette.superficie.tarjeta,
        border: `1px solid ${t.palette.superficie.borde}`,
        borderRadius: `${t.formas.md}px`,
        minWidth: 0,
        height: '100%',
      })}
    >
      <Typography variant="overline" component="span" color="text.secondary">
        {etiqueta}
      </Typography>
      <Box component="span" className="tabular" sx={{ fontSize: 23, fontWeight: 600, lineHeight: 1.2 }}>
        {valor}
        {unidad && (
          <Box component="span" sx={{ fontSize: 13, fontWeight: 500, color: 'text.secondary', ml: 0.5 }}>
            {unidad}
          </Box>
        )}
      </Box>
      {nota && (
        <Typography variant="body2" color="text.secondary">
          {nota}
        </Typography>
      )}
    </Box>
  );
}

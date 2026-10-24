// frontend/src/components/familiar/EscalaExplicada.jsx
// Qué quiere decir cada palabra de la escala, para la familia y el paciente.
// Plegable: abierta la primera vez molesta, pero tiene que estar a mano
// (pruebas de usabilidad: «¿Inicial es bueno o malo?»).

import { useState } from 'react';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Collapse from '@mui/material/Collapse';
import Typography from '@mui/material/Typography';

import { ESCALA_VALORES, SIGNIFICADO_NIVEL } from '../../services/evolucionesService.js';

export default function EscalaExplicada({ abiertaAlInicio = false }) {
  const [abierta, setAbierta] = useState(abiertaAlInicio);
  return (
    <Box>
      <Button size="small" onClick={() => setAbierta((v) => !v)} aria-expanded={abierta} sx={{ px: 0 }}>
        {abierta ? 'Ocultar qué significa cada nivel' : '¿Qué significa cada nivel?'}
      </Button>
      <Collapse in={abierta}>
        <Box
          component="dl"
          sx={(t) => ({
            m: 0, mt: 1, p: 1.5,
            display: 'grid', gridTemplateColumns: 'max-content 1fr', columnGap: 2, rowGap: 0.75,
            backgroundColor: t.palette.superficie.hundida,
            borderRadius: `${t.formas.sm}px`,
          })}
        >
          {[...ESCALA_VALORES].reverse().map((paso) => (
            <Box key={paso.valor} sx={{ display: 'contents' }}>
              <Typography component="dt" variant="body2" sx={{ fontWeight: 600 }}>{paso.etiqueta}</Typography>
              <Typography component="dd" variant="body2" color="text.secondary" sx={{ m: 0 }}>
                {SIGNIFICADO_NIVEL[paso.valor]}
              </Typography>
            </Box>
          ))}
        </Box>
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.75 }}>
          En el gráfico, la curva muestra el mejor nivel alcanzado hasta cada fecha: sube cuando hay avance y se mantiene plana cuando no. Los puntos son las calificaciones; uno hueco es una calificación por debajo de ese nivel.
          Las marcas debajo del eje son sesiones donde ese objetivo no se calificó (ámbar) o ausencias (rojo).
        </Typography>
      </Collapse>
    </Box>
  );
}

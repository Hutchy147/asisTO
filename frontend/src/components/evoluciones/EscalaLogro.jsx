// frontend/src/components/evoluciones/EscalaLogro.jsx
// Selector de la escala de logro.

import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';

import { ESCALA_VALORES } from '../../services/evolucionesService.js';

/**
 * Las cinco palabras, TODAS CON EL MISMO PESO VISUAL.
 *
 * Sin degradado de rojo a verde y sin que "Logrado" se vea mejor que "No
 * logrado": esto no es una nota, es una lectura de avance. "No logrado" es
 * el punto de partida legítimo de muchos tratamientos, y pintarlo de rojo
 * lo convertiría en un fracaso del terapeuta o del paciente.
 *
 * Lo seleccionado se marca con el color primario, igual para los cinco.
 */
export default function EscalaLogro({ valor, onChange, deshabilitado = false, error }) {
  return (
    <Box>
      <Typography
        component="label"
        variant="body2"
        sx={{ display: 'block', mb: 0.75, fontWeight: 500 }}
      >
        Cómo evolucionó en esta sesión <Box component="span" sx={{ color: 'error.main' }}>*</Box>
      </Typography>

      <Box
        role="radiogroup"
        aria-label="Cómo evolucionó en esta sesión"
        sx={(t) => ({
          display: 'inline-flex',
          flexWrap: 'wrap',
          border: `1px solid ${error ? t.palette.error.main : t.palette.superficie.bordeFuerte}`,
          borderRadius: `${t.formas.sm}px`,
          overflow: 'hidden',
          backgroundColor: t.palette.superficie.tarjeta,
        })}
      >
        {ESCALA_VALORES.map((paso, indice) => {
          const elegido = Number(valor) === paso.valor;
          return (
            <Box
              key={paso.valor}
              component="button"
              type="button"
              role="radio"
              aria-checked={elegido}
              disabled={deshabilitado}
              onClick={() => onChange(paso.valor)}
              sx={(t) => ({
                appearance: 'none',
                border: 0,
                borderRight:
                  indice < ESCALA_VALORES.length - 1
                    ? `1px solid ${t.palette.superficie.borde}`
                    : 0,
                px: 1.75,
                height: t.layout.control.md,
                fontFamily: 'inherit',
                fontSize: 13,
                fontWeight: 500,
                whiteSpace: 'nowrap',
                cursor: deshabilitado ? 'not-allowed' : 'pointer',
                backgroundColor: elegido ? t.palette.primary.main : 'transparent',
                color: elegido
                  ? t.palette.primary.contrastText
                  : deshabilitado
                    ? t.palette.text.disabled
                    : t.palette.text.secondary,
                transition: `background-color ${t.transitions.duration.shortest}ms`,
                '&:hover': !deshabilitado && !elegido
                  ? { backgroundColor: t.palette.superficie.hundida }
                  : undefined,
                '&:focus-visible': { outline: 'none', boxShadow: `inset ${t.foco.anillo}` },
              })}
            >
              {paso.etiqueta}
            </Box>
          );
        })}
      </Box>

      <Typography
        variant="caption"
        sx={{ display: 'block', mt: 0.75, color: error ? 'error.main' : 'text.secondary' }}
      >
        {error || 'Escala de logro del centro. Se guarda junto con la fecha de la sesión.'}
      </Typography>
    </Box>
  );
}

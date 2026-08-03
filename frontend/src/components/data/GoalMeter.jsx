// frontend/src/components/data/GoalMeter.jsx

import Box from '@mui/material/Box';

import { MAXIMO_OBJETIVOS_ACTIVOS } from '../../services/objetivosService.js';

/**
 * Objetivos activos sobre el tope duro del sistema (4).
 *
 * Las ranuras libres se dibujan igual que las ocupadas, en hueco: el tope
 * se lee sin contar. Y NO se usa color de alarma al llegar a 4 — tener 4
 * objetivos activos es lo normal, no un problema. El aviso de que hay que
 * archivar aparece recien cuando se intenta crear el quinto.
 */
export default function GoalMeter({ valor = 0, maximo = MAXIMO_OBJETIVOS_ACTIVOS, conEtiqueta = true }) {
  const usados = Math.max(0, Math.min(valor, maximo));
  const lleno = usados >= maximo;
  const vacio = usados === 0;

  return (
    <Box sx={{ display: 'inline-flex', alignItems: 'center', gap: 1 }}>
      <Box sx={{ display: 'inline-flex', gap: '3px' }} aria-hidden="true">
        {Array.from({ length: maximo }, (_, i) => (
          <Box
            key={i}
            sx={(t) => ({
              width: 7,
              height: 14,
              borderRadius: '2px',
              flex: 'none',
              backgroundColor: i < usados ? t.palette.primary.main : 'transparent',
              boxShadow: i < usados ? 'none' : `inset 0 0 0 1px ${t.palette.superficie.bordeFuerte}`,
            })}
          />
        ))}
      </Box>
      {conEtiqueta && (
        <Box
          component="span"
          className="tabular"
          sx={(t) => ({
            fontSize: 13,
            whiteSpace: 'nowrap',
            color: vacio
              ? t.palette.text.disabled
              : lleno
                ? t.palette.text.primary
                : t.palette.text.secondary,
            fontWeight: lleno ? 500 : 400,
          })}
        >
          {usados}
          <Box component="span" sx={{ color: 'text.secondary', fontWeight: 400 }}>
            {' '}de {maximo}
          </Box>
        </Box>
      )}
    </Box>
  );
}

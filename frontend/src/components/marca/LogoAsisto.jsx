// frontend/src/components/marca/LogoAsisto.jsx
// Marca de AsisTO: isotipo + palabra. SVG propio, minimalista: un círculo
// con la curva de evolución subiendo y el punto de logro. Si se quiere usar
// el logo oficial, se reemplaza este archivo (o se apunta <img> a
// /public/logo.svg) y el resto de la app no cambia.

import { useId } from 'react';
import Box from '@mui/material/Box';

export function Isotipo({ size = 40, claro = false }) {
  const id = useId();
  const fondo = claro ? 'rgba(255,255,255,0.14)' : `url(#${id})`;
  const trazo = '#FFFFFF';
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" role="img" aria-label="AsisTO">
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#3E8E7E" />
          <stop offset="1" stopColor="#1B3B5C" />
        </linearGradient>
      </defs>
      <rect width="48" height="48" rx="14" fill={fondo} />
      {/* curva de evolución: sube y se asienta */}
      <path
        d="M10 33 C 16 33, 17 25, 22 24 S 30 20, 34 14"
        fill="none" stroke={trazo} strokeWidth="3.2" strokeLinecap="round"
      />
      <circle cx="34.5" cy="13.5" r="3.6" fill="#D9A441" stroke={trazo} strokeWidth="1.6" />
    </svg>
  );
}

export default function LogoAsisto({ size = 40, claro = false, texto = true }) {
  return (
    <Box sx={{ display: 'inline-flex', alignItems: 'center', gap: 1.25 }}>
      <Isotipo size={size} claro={claro} />
      {texto && (
        <Box
          component="span"
          sx={(t) => ({
            fontFamily: '"Plus Jakarta Sans", "Helvetica Neue", Arial, sans-serif',
            fontSize: size * 0.62,
            fontWeight: 700,
            letterSpacing: '-0.02em',
            lineHeight: 1,
            color: claro ? '#FFFFFF' : t.palette.secondary?.main ?? '#1B3B5C',
            '& span': { fontWeight: 400, opacity: claro ? 0.75 : 0.7 },
          })}
        >
          Asis<span>TO</span>
        </Box>
      )}
    </Box>
  );
}

// frontend/src/components/objetivos/FilaObjetivo.jsx
// Un objetivo dentro de la ficha, activo o archivado.

import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Typography from '@mui/material/Typography';

import { etiquetaDeValor } from '../../services/evolucionesService.js';
import { formatearFecha } from '../../utils/fechas.js';

/**
 * Última calificación en PALABRAS, no en número.
 *
 * La escala vive en un solo lugar (evolucionesService). Acá no se
 * reimplementa ni se muestra el 1–5 como forma principal: un objetivo está
 * "En proceso", no en "3 de 5".
 */
function textoUltimaCalificacion(seguimiento) {
  const etiqueta = etiquetaDeValor(seguimiento?.ultimo_valor);
  if (!etiqueta) return 'Sin calificaciones todavía';

  const fecha = formatearFecha(seguimiento.fecha_ultima_evolucion);
  return fecha ? `Última calificación: ${etiqueta} · ${fecha}` : `Última calificación: ${etiqueta}`;
}

export function ObjetivoActivo({ objetivo, numero, onEditar, onArchivar }) {
  return (
    <Box
      sx={(t) => ({
        display: 'flex',
        alignItems: 'flex-start',
        gap: 2,
        px: 2.25,
        py: 1.75,
        borderBottom: `1px solid ${t.palette.superficie.borde}`,
        '&:last-of-type': { borderBottom: 0 },
      })}
    >
      <Box
        component="span"
        aria-hidden="true"
        sx={(t) => ({
          flex: 'none',
          width: 22,
          height: 22,
          borderRadius: '50%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 11,
          fontWeight: 600,
          color: t.palette.roles.terapeuta.fg,
          backgroundColor: t.palette.roles.terapeuta.bg,
        })}
      >
        {numero}
      </Box>

      <Box sx={{ flex: 1, minWidth: 0 }}>
        {/* texto-libre: la descripción la escribe una persona y puede traer
            una secuencia sin espacios, que sin esto se pinta fuera de la
            tarjeta. Ver theme.js. */}
        <Typography variant="body1" className="texto-libre" sx={{ lineHeight: 1.4 }}>
          {objetivo.descripcion}
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.25 }}>
          {textoUltimaCalificacion(objetivo.seguimiento)}
        </Typography>
      </Box>

      <Box sx={{ display: 'flex', gap: 1, flex: 'none' }}>
        <Button size="small" variant="outlined" onClick={() => onEditar(objetivo)}>
          Editar
        </Button>
        <Button size="small" variant="outlined" onClick={() => onArchivar(objetivo)}>
          Archivar
        </Button>
      </Box>
    </Box>
  );
}

export function ObjetivoArchivado({ objetivo }) {
  const seguimiento = objetivo.seguimiento ?? {};
  const total = seguimiento.total_evoluciones ?? 0;
  const cierre = etiquetaDeValor(seguimiento.ultimo_valor);

  const detalle = [
    `Archivado el ${formatearFecha(objetivo.fecha_archivado) ?? '—'}`,
    `${total} ${total === 1 ? 'calificación' : 'calificaciones'}`,
    cierre ? `cerró en ${cierre}` : null,
  ]
    .filter(Boolean)
    .join(' · ');

  return (
    <Box
      sx={(t) => ({
        display: 'flex',
        alignItems: 'flex-start',
        gap: 2,
        px: 2.25,
        py: 1.75,
        borderBottom: `1px solid ${t.palette.superficie.borde}`,
        '&:last-of-type': { borderBottom: 0 },
      })}
    >
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Typography
          variant="body1"
          color="text.secondary"
          className="texto-libre"
          sx={{ lineHeight: 1.4 }}
        >
          {objetivo.descripcion}
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.25 }}>
          {detalle}
        </Typography>
      </Box>
      {/* Sin acción de editar a propósito: la descripción quedó fija porque
          hay evoluciones puntuadas contra ese texto. Un botón que siempre
          falla es peor que no tenerlo. */}
    </Box>
  );
}

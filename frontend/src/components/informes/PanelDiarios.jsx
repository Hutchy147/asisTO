// frontend/src/components/informes/PanelDiarios.jsx
// Los diarios del período: sesión por sesión, lo que se planificó, lo que se
// registró y lo evaluado en cada objetivo. Es lo que la terapeuta consulta
// mientras revisa un informe grande. Todo en palabras, sin números.

import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Typography from '@mui/material/Typography';

import { Cargando, EstadoError, EstadoVacio } from '../estado/index.js';
import { formatearFecha } from '../../utils/fechas.js';

const ESTADO = { completa: 'Completa', incompleta: 'Incompleta', ausencia: 'Ausencia', programada: 'Programada' };

function Lista({ titulo, filas }) {
  if (!filas || filas.length === 0) return null;
  return (
    <Box sx={{ mt: 0.75 }}>
      <Typography variant="caption" color="text.secondary">{titulo}</Typography>
      <Box component="ul" sx={{ m: 0, pl: 2.5 }}>
        {filas.map((f, i) => (
          <Typography key={i} component="li" variant="body2" className="texto-libre" sx={{ fontWeight: f.destacado ? 600 : 400 }}>
            {f.texto}
          </Typography>
        ))}
      </Box>
    </Box>
  );
}

export default function PanelDiarios({ peticion }) {
  const { datos, cargando, error, recargar } = peticion;
  if (cargando) return <Cargando texto="Cargando los diarios..." />;
  if (error) return <EstadoError error={error} onReintentar={recargar} />;
  if (!datos) return null;
  return (
    <Box>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
        {datos.periodo_etiqueta} · del {formatearFecha(datos.desde)} al {formatearFecha(datos.hasta)} ·{' '}
        {datos.diarios.length} {datos.diarios.length === 1 ? 'sesión' : 'sesiones'}
      </Typography>
      {datos.diarios.length === 0 ? (
        <EstadoVacio plano titulo="No hay sesiones en este período" descripcion="Cuando se registren sesiones, sus diarios aparecerán aquí." />
      ) : (
        datos.diarios.map((d) => (
          <Box
            key={d.id_sesion}
            sx={(t) => ({ border: `1px solid ${t.palette.superficie.borde}`, borderRadius: `${t.formas.md}px`, p: 1.5, mb: 1.25 })}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Typography variant="body1" sx={{ fontWeight: 600 }} className="tabular">
                {formatearFecha(d.fecha)} · {d.hora_inicio}
              </Typography>
              <Chip size="small" label={ESTADO[d.estado] ?? d.estado} />
            </Box>
            <Lista titulo="Planificado" filas={d.plan} />
            <Lista titulo="Registrado" filas={d.registro} />
            {d.objetivos.length > 0 && (
              <Box sx={{ mt: 0.75 }}>
                <Typography variant="caption" color="text.secondary">Objetivos evaluados</Typography>
                {d.objetivos.map((o) => (
                  <Box key={o.id_objetivo} sx={{ display: 'flex', gap: 1, alignItems: 'baseline', flexWrap: 'wrap' }}>
                    <Typography variant="body2" className="texto-libre">{o.objetivo}</Typography>
                    <Chip size="small" label={o.valor} />
                    {o.observaciones && (
                      <Typography variant="body2" color="text.secondary" className="texto-libre">{o.observaciones}</Typography>
                    )}
                  </Box>
                ))}
              </Box>
            )}
            {d.nota && (
              <Box sx={{ mt: 0.75 }}>
                <Typography variant="caption" color="text.secondary">Nota</Typography>
                <Typography variant="body2" className="texto-libre">{d.nota}</Typography>
              </Box>
            )}
          </Box>
        ))
      )}
    </Box>
  );
}

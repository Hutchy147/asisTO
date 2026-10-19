// frontend/src/components/ingreso/HistoriaClinica.jsx
// Historia clínica del centro, generada al completar el ingreso. Vista de
// lectura imprimible (el navegador permite guardarla como PDF).

import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Typography from '@mui/material/Typography';

import { Cargando, EstadoError } from '../estado/index.js';
import { usePeticion } from '../../hooks/usePeticion.js';
import { obtenerHistoriaClinica } from '../../services/ingresoService.js';
import { formatearFecha, textoEdad } from '../../utils/fechas.js';

function Dato({ etiqueta, children }) {
  return (
    <Box sx={{ minWidth: 160 }}>
      <Typography variant="overline" component="div" color="text.secondary">{etiqueta}</Typography>
      <Box className="texto-libre" sx={{ fontSize: 14 }}>{children ?? '—'}</Box>
    </Box>
  );
}

export default function HistoriaClinica({ idPaciente }) {
  const historia = usePeticion(() => obtenerHistoriaClinica(idPaciente), [idPaciente]);

  if (historia.cargando) return <Cargando texto="Generando la historia clínica..." />;
  if (historia.error) return <EstadoError error={historia.error} onReintentar={historia.recargar} />;
  const h = historia.datos;
  if (!h) return null;

  return (
    <Box
      className="imprimible"
      sx={(t) => ({
        backgroundColor: t.palette.superficie.tarjeta,
        border: `1px solid ${t.palette.superficie.borde}`,
        borderRadius: `${t.formas.md}px`,
        mb: 2,
      })}
    >
      <Box sx={(t) => ({ display: 'flex', alignItems: 'flex-start', gap: 2, px: 2.25, py: 1.75, borderBottom: `1px solid ${t.palette.superficie.borde}` })}>
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography variant="h5">Historia clínica</Typography>
          <Typography variant="body2" color="text.secondary">
            Generada el {formatearFecha(h.ingreso.fecha_completado)} a partir del ingreso iniciado
            el {formatearFecha(h.ingreso.fecha_inicio)}.
          </Typography>
        </Box>
        <Button className="no-imprimir" variant="outlined" onClick={() => window.print()}>
          Imprimir o guardar como PDF
        </Button>
      </Box>

      <Box sx={{ p: 2.25, display: 'flex', flexDirection: 'column', gap: 3 }}>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
          <Dato etiqueta="Paciente">{h.paciente.nombre_completo}</Dato>
          <Dato etiqueta="Fecha de nacimiento">
            {formatearFecha(h.paciente.fecha_nacimiento)} ({textoEdad(h.paciente.fecha_nacimiento)})
          </Dato>
          <Dato etiqueta="N° de historia">{h.paciente.nro_historia}</Dato>
          <Dato etiqueta="Obra social">{h.paciente.obra_social}</Dato>
          <Dato etiqueta="Terapeuta responsable">{h.responsables.join(', ') || null}</Dato>
        </Box>
        <Dato etiqueta="Diagnóstico">{h.paciente.diagnostico}</Dato>

        {h.secciones.map((seccion) => (
          <Box key={seccion.etapa}>
            <Typography variant="h6" sx={{ mb: 1 }}>{seccion.nombre}</Typography>
            {seccion.campos.length === 0 ? (
              <Typography variant="body2" color="text.secondary">Sin datos registrados.</Typography>
            ) : (
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.25 }}>
                {seccion.campos.map((c) => (
                  <Box key={c.clave}>
                    <Typography variant="body2" color="text.secondary" sx={{ fontWeight: 600 }}>{c.etiqueta}</Typography>
                    <Typography className="texto-libre" sx={{ whiteSpace: 'pre-wrap' }}>
                      {c.tipo === 'fecha' ? formatearFecha(c.valor) : c.valor}
                    </Typography>
                  </Box>
                ))}
              </Box>
            )}
          </Box>
        ))}

        <Box>
          <Typography variant="h6" sx={{ mb: 1 }}>Objetivos terapéuticos vigentes</Typography>
          <Box component="ol" sx={{ m: 0, pl: 3 }}>
            {h.objetivos.map((o) => (
              <li key={o.id}><Typography className="texto-libre">{o.descripcion}</Typography></li>
            ))}
          </Box>
        </Box>
      </Box>
    </Box>
  );
}

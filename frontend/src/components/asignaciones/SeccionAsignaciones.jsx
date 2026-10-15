// frontend/src/components/asignaciones/SeccionAsignaciones.jsx
// Pestaña "Asignación" de la ficha (HDU 11): quién es responsable del
// paciente hoy y quién lo fue. La lectura es abierta; abrir y cerrar
// asignaciones se ofrece solo si el paciente está en tratamiento.

import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Typography from '@mui/material/Typography';

import DataTable from '../data/DataTable.jsx';
import { EstadoVacio } from '../estado/index.js';
import { formatearFecha } from '../../utils/fechas.js';

export default function SeccionAsignaciones({
  datos, soloLectura, idTerapeutaActual, onAsignar, onCerrar,
}) {
  const columnas = [
    {
      clave: 'terapeuta',
      etiqueta: 'Terapeuta',
      truncar: true,
      render: (a) => (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <span className="texto-libre">{a.terapeuta ?? '—'}</span>
          {a.id_terapeuta === idTerapeutaActual && <Chip size="small" label="Vos" />}
        </Box>
      ),
    },
    { clave: 'desde', etiqueta: 'Desde', ancho: 120, render: (a) => formatearFecha(a.fecha_desde) },
    {
      clave: 'hasta',
      etiqueta: 'Hasta',
      ancho: 120,
      render: (a) => (a.vigente ? <Chip size="small" color="primary" label="Vigente" /> : formatearFecha(a.fecha_hasta)),
    },
    {
      clave: 'acciones',
      etiqueta: '',
      ancho: 110,
      alinear: 'right',
      render: (a) => (
        a.vigente && !soloLectura ? (
          <Button
            size="small"
            variant="outlined"
            onClick={(evento) => { evento.stopPropagation(); onCerrar(a); }}
          >
            Cerrar
          </Button>
        ) : null
      ),
    },
  ];

  return (
    <Box
      sx={(t) => ({
        backgroundColor: t.palette.superficie.tarjeta,
        border: `1px solid ${t.palette.superficie.borde}`,
        borderRadius: `${t.formas.md}px`,
        mb: 2,
      })}
    >
      <Box
        sx={(t) => ({
          display: 'flex', alignItems: 'flex-start', gap: 2, px: 2.25, py: 1.75,
          borderBottom: `1px solid ${t.palette.superficie.borde}`,
        })}
      >
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography variant="h5">Terapeuta responsable</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.25 }}>
            Solo quien tiene asignado al paciente registra sus sesiones y evoluciones.
            Todos los terapeutas pueden leer su ficha, su historial y sus gráficos.
          </Typography>
        </Box>
        {!soloLectura && (
          <Button variant="contained" onClick={onAsignar}>Asignar terapeuta</Button>
        )}
      </Box>
      {datos.asignaciones.length === 0 ? (
        <EstadoVacio
          plano
          titulo="Todavía no tiene terapeuta asignado"
          descripcion="Hasta que se le asigne uno, nadie puede registrarle sesiones ni cargarle evoluciones."
        />
      ) : (
        <DataTable columnas={columnas} filas={datos.asignaciones} />
      )}
    </Box>
  );
}

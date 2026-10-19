// frontend/src/components/asignaciones/SeccionAsignaciones.jsx
// Pestaña "Asignación" de la ficha (HDU 11): quién es responsable del
// paciente hoy y quién lo fue. Es solo lectura: abrir y cerrar asignaciones
// es una función del administrador (pantalla /admin).

import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Typography from '@mui/material/Typography';

import DataTable from '../data/DataTable.jsx';
import { EstadoVacio } from '../estado/index.js';
import { formatearFecha } from '../../utils/fechas.js';

export default function SeccionAsignaciones({ datos, idTerapeutaActual }) {
  const columnas = [
    {
      clave: 'terapeuta',
      etiqueta: 'Terapeuta',
      truncar: true,
      render: (a) => (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <span className="texto-libre">{a.terapeuta ?? '—'}</span>
          {a.id_terapeuta === idTerapeutaActual && <Chip size="small" label="Usted" />}
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
            Solo el terapeuta asignado registra las sesiones y evoluciones del paciente.
            Todos los terapeutas pueden consultar su ficha, su historial y sus gráficos.
            Las asignaciones las gestiona el administrador.
          </Typography>
        </Box>
      </Box>
      {datos.asignaciones.length === 0 ? (
        <EstadoVacio
          plano
          titulo="Todavía no tiene terapeuta asignado"
          descripcion="Hasta que el administrador le asigne uno, nadie puede registrar sesiones ni evoluciones de este paciente."
        />
      ) : (
        <DataTable columnas={columnas} filas={datos.asignaciones} />
      )}
    </Box>
  );
}

// frontend/src/pages/Panel.jsx
// Panel del terapeuta: lo de hoy y lo que quedo pendiente de evolucion.
// ESTRUCTURA PROVISORIA, sin diseño final.

import Chip from '@mui/material/Chip';
import Grid from '@mui/material/Grid';
import List from '@mui/material/List';
import ListItemButton from '@mui/material/ListItemButton';
import ListItemText from '@mui/material/ListItemText';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import { useNavigate } from 'react-router-dom';

import SesionEstadoChip from '../components/data/SesionEstadoChip.jsx';
import AppLayout from '../components/layout/AppLayout.jsx';
import { Cargando, EstadoError, EstadoVacio } from '../components/estado/index.js';
import { usePeticion } from '../hooks/usePeticion.js';
import {
  listarPendientesDeEvolucion, listarSesionesDeHoy,
} from '../services/sesionesService.js';

function ListaSesiones({ sesiones, onAbrir, mostrarFecha = false }) {
  return (
    <List dense>
      {sesiones.map((sesion) => (
        <ListItemButton key={sesion.id} onClick={() => onAbrir(sesion.id)}>
          <ListItemText
            primary={sesion.paciente.nombre_completo}
            secondary={
              (mostrarFecha ? `${sesion.fecha} · ` : '') +
              `${sesion.hora_inicio}${sesion.hora_fin ? ` a ${sesion.hora_fin}` : ''}`
            }
          />
          <Stack direction="row" spacing={1} alignItems="center">
            {sesion.admite_evolucion && !sesion.tiene_evolucion && (
              <Chip size="small" label="Falta evolución" color="warning" />
            )}
            <SesionEstadoChip estado={sesion.estado} />
          </Stack>
        </ListItemButton>
      ))}
    </List>
  );
}

export default function Panel() {
  const navigate = useNavigate();
  const hoy = usePeticion(listarSesionesDeHoy, []);
  const pendientes = usePeticion(listarPendientesDeEvolucion, []);

  const abrir = (idSesion) => navigate(`/calendario?sesion=${idSesion}`);

  return (
    <AppLayout titulo="Panel">
      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Paper elevation={1} sx={{ p: 3, height: '100%' }}>
            <Typography variant="h6" gutterBottom>
              Sesiones de hoy
            </Typography>

            {hoy.cargando && <Cargando texto="Buscando las sesiones de hoy..." />}
            {hoy.error && <EstadoError error={hoy.error} onReintentar={hoy.recargar} />}

            {hoy.datos && !hoy.cargando && !hoy.error && (
              hoy.datos.total === 0 ? (
                <EstadoVacio
                  titulo="No hay sesiones hoy"
                  descripcion="Es lo normal un fin de semana o un día sin agenda."
                />
              ) : (
                <ListaSesiones sesiones={hoy.datos.sesiones} onAbrir={abrir} />
              )
            )}
          </Paper>
        </Grid>

        <Grid item xs={12} md={6}>
          <Paper elevation={1} sx={{ p: 3, height: '100%' }}>
            <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
              <Typography variant="h6">Pendientes de evolución</Typography>
              {pendientes.datos?.total > 0 && (
                <Chip size="small" color="warning" label={pendientes.datos.total} />
              )}
            </Stack>

            {pendientes.cargando && <Cargando texto="Revisando sesiones sin evolución..." />}
            {pendientes.error && (
              <EstadoError error={pendientes.error} onReintentar={pendientes.recargar} />
            )}

            {pendientes.datos && !pendientes.cargando && !pendientes.error && (
              pendientes.datos.total === 0 ? (
                <EstadoVacio
                  titulo="No quedan evoluciones pendientes"
                  descripcion="Todas las sesiones ya ocurridas tienen su evolución cargada. Las sesiones en ausencia no cuentan: no llevan evolución."
                />
              ) : (
                <ListaSesiones
                  sesiones={pendientes.datos.sesiones}
                  onAbrir={abrir}
                  mostrarFecha
                />
              )
            )}
          </Paper>
        </Grid>
      </Grid>
    </AppLayout>
  );
}

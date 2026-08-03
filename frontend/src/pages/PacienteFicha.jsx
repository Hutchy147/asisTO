// frontend/src/pages/PacienteFicha.jsx
// Ficha del paciente con sus objetivos. ESTRUCTURA PROVISORIA.

import Chip from '@mui/material/Chip';
import Divider from '@mui/material/Divider';
import Grid from '@mui/material/Grid';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemText from '@mui/material/ListItemText';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import { useParams } from 'react-router-dom';

import AvisoCupoCompleto from '../components/avisos/AvisoCupoCompleto.jsx';
import AppLayout from '../components/layout/AppLayout.jsx';
import { Cargando, EstadoError, EstadoVacio } from '../components/estado/index.js';
import { usePeticion } from '../hooks/usePeticion.js';
import { listarObjetivosDePaciente } from '../services/objetivosService.js';

function Dato({ etiqueta, valor }) {
  return (
    <Stack spacing={0.25}>
      <Typography variant="caption" color="text.secondary">
        {etiqueta}
      </Typography>
      <Typography variant="body1">{valor ?? '—'}</Typography>
    </Stack>
  );
}

export default function PacienteFicha() {
  const { id } = useParams();
  const { datos, cargando, error, recargar } = usePeticion(
    () => listarObjetivosDePaciente(id), [id]
  );

  if (cargando) {
    return (
      <AppLayout titulo="Ficha del paciente">
        <Cargando texto="Cargando la ficha..." />
      </AppLayout>
    );
  }

  // Cubre las dos variantes de 404 del contrato: "no existe" y "esta dado
  // de baja". El mensaje distingue cual es, y viene del servidor.
  if (error) {
    return (
      <AppLayout titulo="Ficha del paciente">
        <EstadoError error={error} onReintentar={recargar} />
      </AppLayout>
    );
  }

  const { paciente, activos, archivados, cupo } = datos;

  return (
    <AppLayout titulo={paciente.nombre_completo}>
      <Paper elevation={1} sx={{ p: 3, mb: 3 }}>
        <Grid container spacing={3}>
          <Grid item xs={6} sm={3}>
            <Dato etiqueta="Historia clínica" valor={paciente.nro_historia} />
          </Grid>
          <Grid item xs={6} sm={3}>
            <Dato etiqueta="Fecha de nacimiento" valor={paciente.fecha_nacimiento} />
          </Grid>
          <Grid item xs={6} sm={3}>
            <Dato
              etiqueta="Acceso al sistema"
              valor={paciente.tiene_login ? 'Con cuenta' : 'Sin cuenta'}
            />
          </Grid>
          <Grid item xs={6} sm={3}>
            <Dato
              etiqueta="Objetivos activos"
              valor={`${cupo.usados} de ${cupo.maximo}`}
            />
          </Grid>
          <Grid item xs={12}>
            <Divider sx={{ mb: 2 }} />
            <Dato etiqueta="Diagnóstico" valor={paciente.diagnostico} />
          </Grid>
        </Grid>
      </Paper>

      <AvisoCupoCompleto cupo={cupo} />

      <Paper elevation={1} sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          Objetivos activos
        </Typography>
        {activos.length === 0 ? (
          <EstadoVacio

            titulo="Sin objetivos activos"
            descripcion="Hay que crear al menos un objetivo para poder cargar evoluciones en las sesiones."
          />
        ) : (
          <List dense>
            {activos.map((objetivo) => (
              <ListItem key={objetivo.id} divider>
                <ListItemText
                  primary={objetivo.descripcion}
                  secondary={`Creado el ${objetivo.fecha_creacion?.slice(0, 10)}`}
                />
              </ListItem>
            ))}
          </List>
        )}
      </Paper>

      <Paper elevation={1} sx={{ p: 3 }}>
        <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
          <Typography variant="h6">Objetivos archivados</Typography>
          {archivados.length > 0 && <Chip size="small" label={archivados.length} />}
        </Stack>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          No consumen cupo y conservan las evoluciones cargadas. Su
          descripción ya no se puede editar.
        </Typography>

        {archivados.length === 0 ? (
          <EstadoVacio

            titulo="No hay objetivos archivados"
            descripcion="Cuando se archive un objetivo va a quedar acá, con su historia."
          />
        ) : (
          <List dense>
            {archivados.map((objetivo) => (
              <ListItem key={objetivo.id} divider>
                <ListItemText
                  primary={objetivo.descripcion}
                  secondary={`Archivado el ${objetivo.fecha_archivado?.slice(0, 10)}`}
                />
              </ListItem>
            ))}
          </List>
        )}
      </Paper>
    </AppLayout>
  );
}

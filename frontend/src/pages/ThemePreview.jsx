// frontend/src/pages/ThemePreview.jsx
// Pantalla minima de verificacion: prueba que el theme esta aplicado y que
// el front llega al backend. Se elimina cuando entre el login de Entrega 1.
// Todos los colores se leen del theme, no hay ningun hex en este archivo.

import { useEffect, useState } from 'react';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Container from '@mui/material/Container';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

import SesionEstadoChip from '../components/SesionEstadoChip.jsx';
import { getHealth } from '../services/api.js';

const ROLES = ['terapeuta', 'rrhh', 'familiar', 'paciente'];
const ESTADOS = ['completa', 'incompleta', 'ausencia'];

export default function ThemePreview() {
  const [backend, setBackend] = useState({ estado: 'consultando', detalle: '' });

  useEffect(() => {
    getHealth()
      .then((data) => setBackend({ estado: 'ok', detalle: data?.mensaje ?? '' }))
      .catch((error) => setBackend({ estado: 'error', detalle: error.message }));
  }, []);

  return (
    <Container maxWidth="md" sx={{ py: 6 }}>
      <Typography variant="h3" gutterBottom>
        AsisTO
      </Typography>
      <Typography variant="body1" color="text.secondary" sx={{ mb: 4 }}>
        Sistema de Gestión de Asistencias y Seguimiento Terapéutico.
      </Typography>

      <Stack spacing={3}>
        <Paper elevation={1} sx={{ p: 3 }}>
          <Typography variant="h6" gutterBottom>
            Colores por rol
          </Typography>
          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
            {ROLES.map((rol) => (
              <Chip
                key={rol}
                label={rol}
                sx={(theme) => ({
                  backgroundColor: theme.palette.roles[rol],
                  color: theme.palette.primary.contrastText,
                })}
              />
            ))}
          </Stack>
        </Paper>

        <Paper elevation={1} sx={{ p: 3 }}>
          <Typography variant="h6" gutterBottom>
            Estados de sesión
          </Typography>
          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
            {ESTADOS.map((estado) => (
              <SesionEstadoChip key={estado} estado={estado} />
            ))}
          </Stack>
        </Paper>

        <Paper elevation={1} sx={{ p: 3 }}>
          <Typography variant="h6" gutterBottom>
            Botones
          </Typography>
          <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap>
            <Button variant="contained">Primario</Button>
            <Button variant="contained" color="secondary">
              Secundario
            </Button>
            {/* accent no es una paleta estandar de MUI: se aplica por sx */}
            <Button
              variant="contained"
              sx={(theme) => ({
                backgroundColor: theme.palette.accent.main,
                color: theme.palette.accent.contrastText,
                '&:hover': { backgroundColor: theme.palette.accent.main },
              })}
            >
              Acento
            </Button>
            <Button variant="outlined">Contorno</Button>
          </Stack>
        </Paper>

        <Paper elevation={1} sx={{ p: 3 }}>
          <Typography variant="h6" gutterBottom>
            Backend
          </Typography>
          <Box>
            <Typography
              variant="body2"
              color={backend.estado === 'error' ? 'error.main' : 'text.secondary'}
            >
              {backend.estado === 'consultando' && 'Consultando /api/health...'}
              {backend.estado === 'ok' && `Conectado — ${backend.detalle}`}
              {backend.estado === 'error' && `Sin conexión — ${backend.detalle}`}
            </Typography>
          </Box>
        </Paper>
      </Stack>
    </Container>
  );
}

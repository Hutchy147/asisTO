// frontend/src/pages/Dashboard.jsx
// Dashboard provisorio, uno por rol. Cada uno se identifica con el color
// de su rol, tomado de theme.palette.roles: ningun hex hardcodeado.
//
// Es una pantalla de andamiaje: se reemplaza por el contenido real de cada
// rol a medida que se construyan los modulos de la Entrega 1.

import AppBar from '@mui/material/AppBar';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Container from '@mui/material/Container';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import Toolbar from '@mui/material/Toolbar';
import Typography from '@mui/material/Typography';

import { useAuth } from '../context/AuthContext.jsx';

const TITULOS = {
  terapeuta: 'Panel del terapeuta',
  rrhh: 'Panel de RRHH',
  familiar: 'Portal familiar',
  paciente: 'Mi seguimiento',
};

const DESCRIPCIONES = {
  terapeuta: 'Pacientes, objetivos, sesiones, evoluciones e informes.',
  rrhh: 'Verificacion de asistencias y observaciones tecnicas. Sin contenido clinico.',
  familiar: 'Seguimiento del paciente vinculado e informes finales.',
  paciente: 'Tus objetivos y tu progreso.',
};

export default function Dashboard({ rol }) {
  const { usuario, perfil, logout } = useAuth();

  return (
    <Box sx={{ minHeight: '100vh' }}>
      <AppBar
        position="static"
        elevation={0}
        // El color identifica el rol en pantalla. Sale del theme.
        sx={(theme) => ({ backgroundColor: theme.palette.roles[rol] })}
      >
        <Toolbar>
          <Typography variant="h6" sx={{ flexGrow: 1 }}>
            AsisTO
          </Typography>
          <Stack direction="row" spacing={2} alignItems="center">
            <Typography variant="body2">{usuario?.nombre_completo}</Typography>
            <Button color="inherit" variant="outlined" onClick={logout}>
              Cerrar sesion
            </Button>
          </Stack>
        </Toolbar>
      </AppBar>

      <Container maxWidth="md" sx={{ py: 5 }}>
        <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 1 }}>
          <Typography variant="h4">{TITULOS[rol]}</Typography>
          <Chip
            label={rol}
            sx={(theme) => ({
              backgroundColor: theme.palette.roles[rol],
              color: theme.palette.primary.contrastText,
            })}
          />
        </Stack>

        <Typography variant="body1" color="text.secondary" sx={{ mb: 4 }}>
          {DESCRIPCIONES[rol]}
        </Typography>

        <Paper elevation={1} sx={{ p: 3 }}>
          <Typography variant="h6" gutterBottom>
            Sesion activa
          </Typography>
          <Stack spacing={0.5}>
            <Typography variant="body2" color="text.secondary">
              Email: {usuario?.email}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Rol: {usuario?.rol}
            </Typography>
            {perfil?.matricula && (
              <Typography variant="body2" color="text.secondary">
                Matricula: {perfil.matricula}
              </Typography>
            )}
            {perfil?.nro_legajo && (
              <Typography variant="body2" color="text.secondary">
                Legajo: {perfil.nro_legajo}
              </Typography>
            )}
            {perfil?.parentesco && (
              <Typography variant="body2" color="text.secondary">
                Parentesco: {perfil.parentesco}
              </Typography>
            )}
            {perfil?.nro_historia && (
              <Typography variant="body2" color="text.secondary">
                Historia clinica: {perfil.nro_historia}
              </Typography>
            )}
          </Stack>
        </Paper>
      </Container>
    </Box>
  );
}

// frontend/src/pages/Dashboard.jsx
// Dashboard de los roles cuyo modulo todavia no se construyo: rrhh,
// familiar y paciente. El del terapeuta es /panel.
//
// La pantalla existe para que una demostracion con esos roles no parezca
// rota: el aviso deja claro que falta la pantalla, no el acceso.

import AppBar from '@mui/material/AppBar';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Container from '@mui/material/Container';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import Toolbar from '@mui/material/Toolbar';
import Typography from '@mui/material/Typography';

import AvisoModuloPendiente from '../components/avisos/AvisoModuloPendiente.jsx';
import { useAuth } from '../context/AuthContext.jsx';

const TITULOS = {
  rrhh: 'Panel de RRHH',
  familiar: 'Portal familiar',
  paciente: 'Mi seguimiento',
};

export default function Dashboard({ rol }) {
  const { usuario, perfil, logout } = useAuth();

  return (
    <Box sx={{ minHeight: '100vh' }}>
      <AppBar
        position="static"
        elevation={0}
        sx={(theme) => ({ backgroundColor: theme.palette.roles[rol] })}
      >
        <Toolbar>
          <Typography variant="h6" sx={{ flexGrow: 1 }}>
            AsisTO
          </Typography>
          <Stack direction="row" spacing={2} alignItems="center">
            <Typography variant="body2">{usuario?.nombre_completo}</Typography>
            <Button color="inherit" variant="outlined" onClick={logout}>
              Cerrar sesión
            </Button>
          </Stack>
        </Toolbar>
      </AppBar>

      <Container maxWidth="md" sx={{ py: 5 }}>
        <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 3 }}>
          <Typography variant="h4">{TITULOS[rol]}</Typography>
          <Chip
            label={rol}
            sx={(theme) => ({
              backgroundColor: theme.palette.roles[rol],
              color: theme.palette.primary.contrastText,
            })}
          />
        </Stack>

        <AvisoModuloPendiente rol={rol} />

        <Paper elevation={1} sx={{ p: 3 }}>
          <Typography variant="h6" gutterBottom>
            Sesión activa
          </Typography>
          <Stack spacing={0.5}>
            <Typography variant="body2" color="text.secondary">
              Email: {usuario?.email}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Rol: {usuario?.rol}
            </Typography>
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
                Historia clínica: {perfil.nro_historia}
              </Typography>
            )}
          </Stack>
        </Paper>
      </Container>
    </Box>
  );
}

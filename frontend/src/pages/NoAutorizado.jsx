// frontend/src/pages/NoAutorizado.jsx
// Pantalla 403. Se muestra cuando hay sesion valida pero el rol no alcanza.

import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import { useNavigate } from 'react-router-dom';

import { RUTA_POR_ROL, useAuth } from '../context/AuthContext.jsx';

export default function NoAutorizado() {
  const { rol, logout } = useAuth();
  const navigate = useNavigate();

  const rutaPropia = RUTA_POR_ROL[rol] ?? '/login';

  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        p: 2,
      }}
    >
      <Paper elevation={2} sx={{ p: 4, maxWidth: 480, width: '100%', textAlign: 'center' }}>
        <Typography variant="h2" sx={{ color: 'error.main', mb: 1 }}>
          403
        </Typography>
        <Typography variant="h6" gutterBottom>
          No tiene acceso a esta sección
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
          Su sesión es válida, pero el rol <strong>{rol}</strong> no puede ver esta
          pantalla. Si considera que debería tenerlo, avise al equipo.
        </Typography>

        <Stack direction="row" spacing={2} justifyContent="center">
          <Button variant="contained" onClick={() => navigate(rutaPropia, { replace: true })}>
            Ir a mi inicio
          </Button>
          <Button variant="outlined" onClick={logout}>
            Cerrar sesion
          </Button>
        </Stack>
      </Paper>
    </Box>
  );
}

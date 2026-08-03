// frontend/src/components/LayoutTerapeuta.jsx
// Marco comun de las pantallas del terapeuta. ESTRUCTURA PROVISORIA: la
// navegacion definitiva sale del template de diseño.

import AppBar from '@mui/material/AppBar';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Container from '@mui/material/Container';
import Stack from '@mui/material/Stack';
import Toolbar from '@mui/material/Toolbar';
import Typography from '@mui/material/Typography';
import { NavLink, useLocation } from 'react-router-dom';

import { useAuth } from '../context/AuthContext.jsx';

const SECCIONES = [
  { ruta: '/panel', etiqueta: 'Panel' },
  { ruta: '/pacientes', etiqueta: 'Pacientes' },
  { ruta: '/calendario', etiqueta: 'Calendario' },
];

export default function LayoutTerapeuta({ children, titulo }) {
  const { usuario, logout } = useAuth();
  const ubicacion = useLocation();

  return (
    <Box sx={{ minHeight: '100vh' }}>
      <AppBar
        position="static"
        elevation={0}
        sx={(theme) => ({ backgroundColor: theme.palette.roles.terapeuta })}
      >
        <Toolbar>
          <Typography variant="h6" sx={{ mr: 4 }}>
            AsisTO
          </Typography>

          <Stack direction="row" spacing={1} sx={{ flexGrow: 1 }}>
            {SECCIONES.map(({ ruta, etiqueta }) => {
              const activa = ubicacion.pathname.startsWith(ruta);
              return (
                <Button
                  key={ruta}
                  component={NavLink}
                  to={ruta}
                  color="inherit"
                  sx={{
                    // Subrayado en la seccion activa. El color se hereda de
                    // la barra, que ya sale del theme.
                    borderBottom: activa ? '2px solid currentColor' : '2px solid transparent',
                    borderRadius: 0,
                  }}
                >
                  {etiqueta}
                </Button>
              );
            })}
          </Stack>

          <Stack direction="row" spacing={2} alignItems="center">
            <Typography variant="body2">{usuario?.nombre_completo}</Typography>
            <Button color="inherit" variant="outlined" onClick={logout}>
              Cerrar sesión
            </Button>
          </Stack>
        </Toolbar>
      </AppBar>

      <Container maxWidth="lg" sx={{ py: 4 }}>
        {titulo && (
          <Typography variant="h4" sx={{ mb: 3 }}>
            {titulo}
          </Typography>
        )}
        {children}
      </Container>
    </Box>
  );
}

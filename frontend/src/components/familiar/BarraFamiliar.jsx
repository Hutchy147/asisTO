// frontend/src/components/familiar/BarraFamiliar.jsx
// Marco de las pantallas del portal familiar: barra superior con el color
// del rol, navegación entre Evolución, Informes y Avisos, y cierre de sesión.

import AppBar from '@mui/material/AppBar';
import Badge from '@mui/material/Badge';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Container from '@mui/material/Container';
import Stack from '@mui/material/Stack';
import Toolbar from '@mui/material/Toolbar';
import Typography from '@mui/material/Typography';
import { useNavigate } from 'react-router-dom';

import { hayCapacidad } from '../../config/entregas.js';
import { useAuth } from '../../context/AuthContext.jsx';

export default function BarraFamiliar({ activa, sinLeer = 0, children }) {
  const { usuario, logout } = useAuth();
  const navigate = useNavigate();
  const conAvisos = hayCapacidad('notificaciones');
  const conInformes = hayCapacidad('familiar.informes');

  const boton = (id, etiqueta, ruta, insignia = 0) => (
    <Button
      key={id}
      color="inherit"
      onClick={() => navigate(ruta)}
      sx={{ fontWeight: activa === id ? 700 : 400, borderBottom: activa === id ? '2px solid currentColor' : '2px solid transparent', borderRadius: 0 }}
    >
      <Badge color="error" badgeContent={insignia} max={99} sx={{ '& .MuiBadge-badge': { right: -10 } }}>
        {etiqueta}
      </Badge>
    </Button>
  );

  return (
    <Box sx={{ minHeight: '100vh', backgroundColor: 'background.default' }}>
      <AppBar position="static" elevation={0} sx={(t) => ({ backgroundColor: t.palette.roles.familiar.fg })}>
        <Toolbar>
          <Typography variant="h6" sx={{ mr: 4 }}>AsisTO · Portal familiar</Typography>
          <Stack direction="row" spacing={1} sx={{ flexGrow: 1 }}>
            {boton('evolucion', 'Evolución', '/familiar')}
            {conInformes && boton('informes', 'Informes', '/familiar/informes')}
            {conAvisos && boton('avisos', 'Avisos', '/familiar/notificaciones', sinLeer)}
          </Stack>
          <Stack direction="row" spacing={2} alignItems="center">
            <Typography variant="body2" className="texto-libre" noWrap>{usuario?.nombre_completo}</Typography>
            <Button color="inherit" variant="outlined" onClick={logout}>Cerrar sesión</Button>
          </Stack>
        </Toolbar>
      </AppBar>
      <Container maxWidth="lg" sx={{ py: 4 }}>{children}</Container>
    </Box>
  );
}

// frontend/src/components/familiar/BarraFamiliar.jsx
// Marco de las pantallas del portal familiar: barra superior con el color
// del rol, navegación entre Progreso, Informes y Avisos, y cierre de sesión.
// Pensada también para el celular (es como entra la mayoría de las familias).

import AppBar from '@mui/material/AppBar';
import Badge from '@mui/material/Badge';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Container from '@mui/material/Container';
import Stack from '@mui/material/Stack';
import Toolbar from '@mui/material/Toolbar';
import Typography from '@mui/material/Typography';
import useMediaQuery from '@mui/material/useMediaQuery';
import { useTheme } from '@mui/material/styles';
import { useNavigate, useSearchParams } from 'react-router-dom';

import { hayCapacidad } from '../../config/entregas.js';
import { useAuth } from '../../context/AuthContext.jsx';

export default function BarraFamiliar({ activa, sinLeer = 0, children }) {
  const { usuario, logout } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const celular = useMediaQuery(useTheme().breakpoints.down('sm'));
  const conAvisos = hayCapacidad('notificaciones');
  const conInformes = hayCapacidad('familiar.informes');
  // El hijo elegido viaja entre Progreso e Informes: antes se volvía al primero.
  const paciente = params.get('paciente');
  const conPaciente = (ruta) => (paciente ? `${ruta}?paciente=${paciente}` : ruta);

  const boton = (id, etiqueta, ruta, insignia = 0) => (
    <Button
      key={id}
      color="inherit"
      onClick={() => navigate(ruta)}
      aria-current={activa === id ? 'page' : undefined}
      aria-label={insignia ? `${etiqueta} (${insignia} ${insignia === 1 ? 'nuevo' : 'nuevos'})` : etiqueta}
      sx={{
        fontWeight: activa === id ? 700 : 400, borderRadius: 0, minWidth: 0,
        px: { xs: 1, sm: 1.5 }, fontSize: { xs: 13.5, sm: 14 },
        borderBottom: activa === id ? '2px solid currentColor' : '2px solid transparent',
      }}
    >
      {/* Sin número cuando no hay nada: antes se leía «Informes 0». */}
      <Badge color="error" badgeContent={insignia || null} max={99} sx={{ '& .MuiBadge-badge': { right: -12 } }}>
        {etiqueta}
      </Badge>
    </Button>
  );

  return (
    <Box sx={{ minHeight: '100vh', backgroundColor: 'background.default', overflowX: 'hidden' }}>
      <AppBar position="static" elevation={0} sx={(t) => ({ backgroundColor: t.palette.roles.familiar.fg })}>
        <Toolbar sx={{ flexWrap: 'wrap', gap: { xs: 0.5, sm: 2 }, py: { xs: 1, sm: 0 } }}>
          <Typography variant="h6" sx={{ mr: { sm: 2 }, flexGrow: { xs: 1, sm: 0 }, fontSize: { xs: 17, sm: 20 } }}>
            {celular ? 'AsisTO' : 'AsisTO · Portal familiar'}
          </Typography>
          {celular && (
            <Button color="inherit" variant="outlined" size="small" onClick={logout}>Cerrar sesión</Button>
          )}
          <Stack direction="row" spacing={{ xs: 1, sm: 2 }} sx={{ flexGrow: 1, flexBasis: { xs: '100%', sm: 'auto' } }}>
            {boton('evolucion', 'Progreso', conPaciente('/familiar'))}
            {conInformes && boton('informes', 'Informes', conPaciente('/familiar/informes'))}
            {conAvisos && boton('avisos', 'Avisos', '/familiar/notificaciones', sinLeer)}
          </Stack>
          {!celular && (
            <Stack direction="row" spacing={2} alignItems="center">
              <Typography variant="body2" className="texto-libre" noWrap sx={{ maxWidth: 220 }}>{usuario?.nombre_completo}</Typography>
              <Button color="inherit" variant="outlined" onClick={logout}>Cerrar sesión</Button>
            </Stack>
          )}
        </Toolbar>
      </AppBar>
      <Container maxWidth="lg" sx={{ py: { xs: 2, sm: 4 }, px: { xs: 1.5, sm: 3 } }}>{children}</Container>
    </Box>
  );
}

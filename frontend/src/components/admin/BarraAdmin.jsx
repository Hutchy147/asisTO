// frontend/src/components/admin/BarraAdmin.jsx
// Barra superior de las pantallas del administrador: color del rol,
// navegación entre sus pantallas y cierre de sesión.

import AppBar from '@mui/material/AppBar';
import Button from '@mui/material/Button';
import Stack from '@mui/material/Stack';
import Toolbar from '@mui/material/Toolbar';
import Typography from '@mui/material/Typography';
import { useNavigate } from 'react-router-dom';

import { hayCapacidad } from '../../config/entregas.js';
import { useAuth } from '../../context/AuthContext.jsx';

export default function BarraAdmin({ activa }) {
  const { usuario, logout } = useAuth();
  const navigate = useNavigate();

  const enlace = (id, etiqueta, ruta) => (
    <Button
      key={id}
      color="inherit"
      onClick={() => navigate(ruta)}
      sx={{
        fontWeight: activa === id ? 700 : 400, borderRadius: 0,
        borderBottom: activa === id ? '2px solid currentColor' : '2px solid transparent',
      }}
    >
      {etiqueta}
    </Button>
  );

  return (
    <AppBar position="static" elevation={0} sx={(t) => ({ backgroundColor: t.palette.roles.admin.fg })}>
      <Toolbar>
        <Typography variant="h6" sx={{ mr: 4 }}>AsisTO · Administración</Typography>
        <Stack direction="row" spacing={1} sx={{ flexGrow: 1 }}>
          {enlace('asignaciones', 'Asignaciones', '/admin')}
          {hayCapacidad('admin.usuarios') && enlace('usuarios', 'Cuentas de acceso', '/admin/usuarios')}
          {hayCapacidad('ingreso.configurar') && enlace('formularios', 'Formulario de ingreso', '/admin/formularios')}
          {hayCapacidad('objetivos.plantillas') && enlace('plantillas', 'Plantillas de objetivos', '/admin/plantillas')}
        </Stack>
        <Stack direction="row" spacing={2} alignItems="center">
          <Typography variant="body2" className="texto-libre" noWrap>{usuario?.nombre_completo}</Typography>
          <Button color="inherit" variant="outlined" onClick={logout}>Cerrar sesión</Button>
        </Stack>
      </Toolbar>
    </AppBar>
  );
}

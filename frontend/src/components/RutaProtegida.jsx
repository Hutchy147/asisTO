// frontend/src/components/RutaProtegida.jsx
// Guarda de rutas: exige sesion y, opcionalmente, un rol.

import Box from '@mui/material/Box';
import CircularProgress from '@mui/material/CircularProgress';
import { Navigate, useLocation } from 'react-router-dom';

import { useAuth } from '../context/AuthContext.jsx';
import NoAutorizado from '../pages/NoAutorizado.jsx';

export default function RutaProtegida({ rolesPermitidos, children }) {
  const { autenticado, rol, cargando } = useAuth();
  const ubicacion = useLocation();

  // Mientras se revalida el token guardado no se decide nada. Si se
  // redirigiera al login durante la carga, recargar una ruta protegida
  // sacaria al usuario aunque su sesion siga siendo valida.
  if (cargando) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  // Sin sesion: al login. Se recuerda a donde queria ir para volver
  // despues de autenticarse.
  if (!autenticado) {
    return <Navigate to="/login" replace state={{ desde: ubicacion.pathname }} />;
  }

  // Con sesion pero sin el rol: 403 propio. NO se redirige al login,
  // que sugeriria que el problema es la sesion cuando es de permisos.
  if (rolesPermitidos && !rolesPermitidos.includes(rol)) {
    return <NoAutorizado />;
  }

  return children;
}

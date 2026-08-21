// frontend/src/components/RutaProtegida.jsx
// Guarda de rutas: exige sesion, opcionalmente un rol, y que la pantalla
// pertenezca a la entrega que se esta mostrando.

import Box from '@mui/material/Box';
import CircularProgress from '@mui/material/CircularProgress';
import { Navigate, useLocation } from 'react-router-dom';

import { hayCapacidad } from '../config/entregas.js';
import { useAuth } from '../context/AuthContext.jsx';
import FueraDeEntrega from '../pages/FueraDeEntrega.jsx';
import NoAutorizado from '../pages/NoAutorizado.jsx';

export default function RutaProtegida({ rolesPermitidos, capacidad, children }) {
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

  // La pantalla existe pero no en la entrega que se esta mostrando. Va
  // DESPUES del chequeo de rol a proposito: si las dos cosas fallan, la que
  // hay que decir es la de permisos, que es la que no cambia segun como se
  // arranco la aplicacion.
  //
  // Esto es lo que hace que no alcance con esconder el menu: aca se corta
  // tambien la URL escrita a mano.
  if (capacidad && !hayCapacidad(capacidad)) {
    return <FueraDeEntrega capacidad={capacidad} />;
  }

  return children;
}

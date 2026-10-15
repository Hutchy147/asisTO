// frontend/src/App.jsx
// Router de la app.

import Box from '@mui/material/Box';
import CircularProgress from '@mui/material/CircularProgress';
import { Navigate, Route, Routes } from 'react-router-dom';

import RutaProtegida from './components/RutaProtegida.jsx';
import { validarRutas } from './config/entregas.js';
import { RUTAS_PROTEGIDAS } from './config/rutas.js';
import { RUTA_POR_ROL, useAuth } from './context/AuthContext.jsx';
import Calendario from './pages/Calendario.jsx';
import Dashboard from './pages/Dashboard.jsx';
import Login from './pages/Login.jsx';
import NoAutorizado from './pages/NoAutorizado.jsx';
import PacienteFicha from './pages/PacienteFicha.jsx';
import Pacientes from './pages/Pacientes.jsx';
import Panel from './pages/Panel.jsx';
import PanelRrhh from './pages/PanelRrhh.jsx';
import RecuperarContrasena from './pages/RecuperarContrasena.jsx';
import RestablecerContrasena from './pages/RestablecerContrasena.jsx';

// QUE SE DIBUJA EN CADA RUTA.
//
// QUIEN puede verla y a que entrega pertenece NO se declara aca: sale de
// RUTAS_PROTEGIDAS (src/config/rutas.js), que es la lista unica y la que
// tambien consulta `Login` para decidir si un destino guardado sirve para el
// rol que entra. Aca solo se le cuelga el componente a cada ruta.
//
// Los tres roles cuyo modulo todavia no existe caen en `Dashboard`, que dice
// explicitamente que falta la pantalla y no el acceso. RRHH salio de ese
// grupo el 2026-09-13, cuando se construyo su panel.
const ELEMENTO_POR_RUTA = {
  '/panel': <Panel />,
  '/pacientes': <Pacientes />,
  '/pacientes/:id': <PacienteFicha />,
  '/calendario': <Calendario />,
  '/rrhh': <PanelRrhh />,
  '/familiar': <Dashboard rol="familiar" />,
  '/paciente': <Dashboard rol="paciente" />,
};

// Corre una vez al importar el modulo. Si alguien agrega una pantalla sin
// decir a que entrega pertenece, la aplicacion no arranca en desarrollo y el
// error dice cual es.
validarRutas(RUTAS_PROTEGIDAS);

// Y el par de la misma guarda: una ruta declarada sin componente seria una
// pantalla en blanco. Se cae al arrancar, con el nombre adentro.
const SIN_ELEMENTO = RUTAS_PROTEGIDAS.filter((r) => !ELEMENTO_POR_RUTA[r.ruta]);
if (SIN_ELEMENTO.length > 0) {
  throw new Error(
    '[rutas] Rutas declaradas en src/config/rutas.js sin componente en App.jsx:\n' +
    SIN_ELEMENTO.map((r) => `  ${r.ruta}`).join('\n')
  );
}

function Inicio() {
  const { autenticado, rol, cargando } = useAuth();

  if (cargando) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  if (!autenticado) return <Navigate to="/login" replace />;
  return <Navigate to={RUTA_POR_ROL[rol] ?? '/login'} replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/recuperar" element={<RecuperarContrasena />} />
      <Route path="/restablecer/:token" element={<RestablecerContrasena />} />
      <Route path="/" element={<Inicio />} />

      {/* Una sola pasada sobre la lista unica. Los roles y la capacidad de
          cada ruta salen de ahi, no de este archivo. */}
      {RUTAS_PROTEGIDAS.map(({ ruta, roles, capacidad }) => (
        <Route
          key={ruta}
          path={ruta}
          element={
            <RutaProtegida rolesPermitidos={roles} capacidad={capacidad}>
              {ELEMENTO_POR_RUTA[ruta]}
            </RutaProtegida>
          }
        />
      ))}

      {/* Compatibilidad: /terapeuta era la ruta inicial antes de /panel */}
      <Route path="/terapeuta" element={<Navigate to="/panel" replace />} />

      <Route path="/403" element={<NoAutorizado />} />

      {/* Cualquier otra ruta cae en Inicio, que decide segun la sesion */}
      <Route path="*" element={<Inicio />} />
    </Routes>
  );
}

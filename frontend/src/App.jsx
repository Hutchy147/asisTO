// frontend/src/App.jsx
// Router de la app.

import Box from '@mui/material/Box';
import CircularProgress from '@mui/material/CircularProgress';
import { Navigate, Route, Routes } from 'react-router-dom';

import RutaProtegida from './components/RutaProtegida.jsx';
import { RUTA_POR_ROL, useAuth } from './context/AuthContext.jsx';
import Calendario from './pages/Calendario.jsx';
import Dashboard from './pages/Dashboard.jsx';
import Login from './pages/Login.jsx';
import NoAutorizado from './pages/NoAutorizado.jsx';
import PacienteFicha from './pages/PacienteFicha.jsx';
import Pacientes from './pages/Pacientes.jsx';
import Panel from './pages/Panel.jsx';

// Pantallas del terapeuta. Todas exigen sesion y rol terapeuta.
const RUTAS_TERAPEUTA = [
  { ruta: '/panel', elemento: <Panel /> },
  { ruta: '/pacientes', elemento: <Pacientes /> },
  { ruta: '/pacientes/:id', elemento: <PacienteFicha /> },
  { ruta: '/calendario', elemento: <Calendario /> },
];

// Los tres roles cuyo modulo llega en una entrega posterior. Su dashboard
// lo dice explicitamente para que no parezca una pantalla rota.
const RUTAS_PENDIENTES = ['rrhh', 'familiar', 'paciente'];

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
      <Route path="/" element={<Inicio />} />

      {RUTAS_TERAPEUTA.map(({ ruta, elemento }) => (
        <Route
          key={ruta}
          path={ruta}
          element={
            <RutaProtegida rolesPermitidos={['terapeuta']}>{elemento}</RutaProtegida>
          }
        />
      ))}

      {/* Compatibilidad: /terapeuta era la ruta inicial antes de /panel */}
      <Route path="/terapeuta" element={<Navigate to="/panel" replace />} />

      {RUTAS_PENDIENTES.map((rol) => (
        <Route
          key={rol}
          path={`/${rol}`}
          element={
            <RutaProtegida rolesPermitidos={[rol]}>
              <Dashboard rol={rol} />
            </RutaProtegida>
          }
        />
      ))}

      <Route path="/403" element={<NoAutorizado />} />

      {/* Cualquier otra ruta cae en Inicio, que decide segun la sesion */}
      <Route path="*" element={<Inicio />} />
    </Routes>
  );
}

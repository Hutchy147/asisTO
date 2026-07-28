// frontend/src/App.jsx
// Router de la app. Cada rol tiene su ruta y su dashboard.

import Box from '@mui/material/Box';
import CircularProgress from '@mui/material/CircularProgress';
import { Navigate, Route, Routes } from 'react-router-dom';

import RutaProtegida from './components/RutaProtegida.jsx';
import { RUTA_POR_ROL, useAuth } from './context/AuthContext.jsx';
import Dashboard from './pages/Dashboard.jsx';
import Login from './pages/Login.jsx';
import NoAutorizado from './pages/NoAutorizado.jsx';

// Cada entrada define quien puede entrar. El array es la unica fuente de
// verdad: agregar un rol nuevo es agregar una fila, no tocar el JSX.
const RUTAS_POR_ROL = [
  { ruta: '/terapeuta', rol: 'terapeuta' },
  { ruta: '/rrhh', rol: 'rrhh' },
  { ruta: '/familiar', rol: 'familiar' },
  { ruta: '/paciente', rol: 'paciente' },
];

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

      {RUTAS_POR_ROL.map(({ ruta, rol }) => (
        <Route
          key={ruta}
          path={ruta}
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

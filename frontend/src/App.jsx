// frontend/src/App.jsx
// Router de la app.

import Box from '@mui/material/Box';
import CircularProgress from '@mui/material/CircularProgress';
import { Navigate, Route, Routes } from 'react-router-dom';

import RutaProtegida from './components/RutaProtegida.jsx';
import { validarRutas } from './config/entregas.js';
import { RUTA_POR_ROL, useAuth } from './context/AuthContext.jsx';
import Calendario from './pages/Calendario.jsx';
import Dashboard from './pages/Dashboard.jsx';
import Login from './pages/Login.jsx';
import NoAutorizado from './pages/NoAutorizado.jsx';
import PacienteFicha from './pages/PacienteFicha.jsx';
import Pacientes from './pages/Pacientes.jsx';
import Panel from './pages/Panel.jsx';
import PanelRrhh from './pages/PanelRrhh.jsx';

// Pantallas del terapeuta. Todas exigen sesion y rol terapeuta.
//
// `capacidad` NO ES OPCIONAL: dice a que entrega pertenece la pantalla y sale
// de la tabla unica de src/config/entregas.js. Una ruta sin ella hace fallar
// el arranque en desarrollo — ver validarRutas mas abajo.
const RUTAS_TERAPEUTA = [
  { ruta: '/panel', capacidad: 'panel', elemento: <Panel /> },
  { ruta: '/pacientes', capacidad: 'pacientes.listado', elemento: <Pacientes /> },
  { ruta: '/pacientes/:id', capacidad: 'pacientes.listado', elemento: <PacienteFicha /> },
  { ruta: '/calendario', capacidad: 'calendario', elemento: <Calendario /> },
];

// Pantallas de otros roles, con su propia pantalla ya construida.
//
// RRHH salio de RUTAS_PENDIENTES el 2026-09-13, cuando el panel se
// construyo. Lleva la MISMA capacidad que llevaba de pendiente
// (`rrhh.consulta`, entrega 2), asi que en modo 1 desaparece igual que
// antes: lo que cambio es que ahora hay una pantalla detras, no la etiqueta.
const RUTAS_POR_ROL = [
  { ruta: '/rrhh', rol: 'rrhh', capacidad: 'rrhh.consulta', elemento: <PanelRrhh /> },
];

// Los roles cuyo modulo llega en una entrega posterior. Su dashboard lo dice
// explicitamente para que no parezca una pantalla rota.
//
// Van etiquetados aunque el modulo todavia no exista: es justamente el caso
// que la tabla tiene que cubrir sin que nadie vuelva atras a etiquetarlo.
const RUTAS_PENDIENTES = [
  { rol: 'familiar', capacidad: 'familiar.portal' },
  { rol: 'paciente', capacidad: 'paciente.portal' },
];

// Corre una vez al importar el modulo. Si alguien agrega una pantalla sin
// decir a que entrega pertenece, la aplicacion no arranca en desarrollo y el
// error dice cual es.
validarRutas([
  ...RUTAS_TERAPEUTA,
  ...RUTAS_POR_ROL,
  ...RUTAS_PENDIENTES.map((p) => ({ ...p, ruta: `/${p.rol}` })),
]);

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

      {RUTAS_TERAPEUTA.map(({ ruta, capacidad, elemento }) => (
        <Route
          key={ruta}
          path={ruta}
          element={
            <RutaProtegida rolesPermitidos={['terapeuta']} capacidad={capacidad}>
              {elemento}
            </RutaProtegida>
          }
        />
      ))}

      {/* Compatibilidad: /terapeuta era la ruta inicial antes de /panel */}
      <Route path="/terapeuta" element={<Navigate to="/panel" replace />} />

      {RUTAS_POR_ROL.map(({ ruta, rol, capacidad, elemento }) => (
        <Route
          key={ruta}
          path={ruta}
          element={
            <RutaProtegida rolesPermitidos={[rol]} capacidad={capacidad}>
              {elemento}
            </RutaProtegida>
          }
        />
      ))}

      {RUTAS_PENDIENTES.map(({ rol, capacidad }) => (
        <Route
          key={rol}
          path={`/${rol}`}
          element={
            <RutaProtegida rolesPermitidos={[rol]} capacidad={capacidad}>
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

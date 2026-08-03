// frontend/src/components/layout/AppLayout.jsx
// Marco de las pantallas del terapeuta: barra lateral + barra superior.
// Reemplaza a LayoutTerapeuta.

import Box from '@mui/material/Box';

import SidebarNav from './SidebarNav.jsx';
import Topbar from './Topbar.jsx';
import { useAuth } from '../../context/AuthContext.jsx';

export default function AppLayout({ titulo, subtitulo, acciones, contadores = {}, children }) {
  const { usuario, logout } = useAuth();

  const grupos = [
    {
      items: [
        { id: 'panel', etiqueta: 'Panel', ruta: '/panel', contador: contadores.panel },
        { id: 'pacientes', etiqueta: 'Pacientes', ruta: '/pacientes', contador: contadores.pacientes },
        { id: 'calendario', etiqueta: 'Calendario', ruta: '/calendario' },
      ],
    },
    {
      items: [{ id: 'salir', etiqueta: 'Cerrar sesión', onClick: logout }],
    },
  ];

  return (
    <Box sx={{ display: 'flex', height: '100vh', backgroundColor: 'background.default' }}>
      <SidebarNav grupos={grupos} usuario={usuario} />

      <Box component="main" sx={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
        <Topbar titulo={titulo} subtitulo={subtitulo} acciones={acciones} />
        <Box sx={{ flex: 1, overflow: 'auto' }}>
          <Box sx={(t) => ({ p: 3, maxWidth: t.layout.contenidoMax })}>{children}</Box>
        </Box>
      </Box>
    </Box>
  );
}

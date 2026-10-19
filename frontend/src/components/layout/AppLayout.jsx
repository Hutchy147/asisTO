// frontend/src/components/layout/AppLayout.jsx
// Marco de las pantallas del terapeuta: barra lateral + barra superior.
// Reemplaza a LayoutTerapeuta.

import Box from '@mui/material/Box';

import SidebarNav from './SidebarNav.jsx';
import Topbar from './Topbar.jsx';
import { hayCapacidad } from '../../config/entregas.js';
import { useAuth } from '../../context/AuthContext.jsx';

export default function AppLayout({ titulo, subtitulo, acciones, contadores = {}, children }) {
  const { usuario, logout } = useAuth();

  // Cada item de navegacion lleva la capacidad de su pantalla, la misma que
  // declara su ruta en App.jsx. Esconder el menu es la mitad barata del
  // trabajo: la que vale es la de RutaProtegida, que corta la URL escrita a
  // mano. Las dos leen la MISMA tabla, asi que no pueden discrepar.
  const navegacion = [
    { id: 'panel', etiqueta: 'Panel', ruta: '/panel', capacidad: 'panel', contador: contadores.panel },
    { id: 'pacientes', etiqueta: 'Pacientes', ruta: '/pacientes', capacidad: 'pacientes.listado', contador: contadores.pacientes },
    { id: 'calendario', etiqueta: 'Calendario', ruta: '/calendario', capacidad: 'calendario' },
    { id: 'sesiones', etiqueta: 'Sesiones', ruta: '/sesiones', capacidad: 'sesiones.consultar' },
    { id: 'informes', etiqueta: 'Informes', ruta: '/informes', capacidad: 'informes.control' },
  ];

  const grupos = [
    { items: navegacion.filter((item) => hayCapacidad(item.capacidad)) },
    {
      // Cerrar sesion no se filtra nunca: es parte de la sesion, no de una
      // entrega, y dejar a alguien sin salida seria peor que mostrar de mas.
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

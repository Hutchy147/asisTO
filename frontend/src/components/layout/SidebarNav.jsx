// frontend/src/components/layout/SidebarNav.jsx
// Barra lateral de navegacion.
//
// El fondo es NAVY para todos los roles, no el color del rol. Los colores
// de rol se usan solo donde varios roles conviven en pantalla; adentro de
// la app el rol es implicito y pintar el chrome de su color no informa
// nada. Sale de palette.superficie.nav.

import Avatar from '@mui/material/Avatar';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import { NavLink } from 'react-router-dom';

/** Iniciales para el avatar. Dos como maximo. */
function iniciales(nombre = '') {
  return nombre
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((parte) => parte[0]?.toUpperCase() ?? '')
    .join('');
}

function ItemNav({ item, onSelect }) {
  const contenido = (activo) => (
    <Box
      component="span"
      sx={(t) => ({
        display: 'flex',
        alignItems: 'center',
        gap: 1.5,
        width: '100%',
        height: 34,
        px: 1.5,
        borderRadius: `${t.formas.sm}px`,
        fontFamily: t.typography.h4.fontFamily,
        fontSize: 14,
        fontWeight: activo ? 500 : 400,
        color: activo ? '#FFFFFF' : 'rgba(255,255,255,.78)',
        backgroundColor: activo ? t.palette.roles.terapeuta.fg : 'transparent',
        transition: `background-color ${t.transitions.duration.shortest}ms`,
        '&:hover': {
          backgroundColor: activo ? t.palette.roles.terapeuta.fg : 'rgba(255,255,255,.08)',
          color: '#FFFFFF',
        },
      })}
    >
      <Box component="span" sx={{ flex: 1, minWidth: 0 }}>
        {item.etiqueta}
      </Box>
      {item.contador !== undefined && item.contador !== null && (
        <Box
          component="span"
          className="tabular"
          sx={{ fontSize: 11, color: 'rgba(255,255,255,.55)' }}
        >
          {item.contador}
        </Box>
      )}
    </Box>
  );

  // Los items de accion (cerrar sesion) no son rutas
  if (item.onClick) {
    return (
      <Box
        component="button"
        type="button"
        onClick={item.onClick}
        sx={{ background: 'none', border: 0, p: 0, cursor: 'pointer', textAlign: 'left' }}
      >
        {contenido(false)}
      </Box>
    );
  }

  return (
    <NavLink
      to={item.ruta}
      onClick={onSelect}
      style={{ textDecoration: 'none' }}
      end={item.exacto}
    >
      {({ isActive }) => contenido(isActive)}
    </NavLink>
  );
}

export default function SidebarNav({ grupos = [], usuario }) {
  return (
    <Box
      component="nav"
      sx={(t) => ({
        width: t.layout.sidebar,
        flex: 'none',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        backgroundColor: t.palette.superficie.nav,
        color: '#FFFFFF',
      })}
    >
      <Box
        sx={(t) => ({
          display: 'flex',
          alignItems: 'center',
          height: t.layout.topbar,
          px: 2,
          flex: 'none',
          borderBottom: '1px solid rgba(255,255,255,.10)',
        })}
      >
        <Typography
          component="span"
          sx={(t) => ({
            fontFamily: t.typography.h4.fontFamily,
            fontSize: 19,
            fontWeight: 600,
            letterSpacing: '-0.01em',
            color: '#FFFFFF',
          })}
        >
          Asis
          <Box component="span" sx={{ color: 'primary.light' }}>
            TO
          </Box>
        </Typography>
      </Box>

      <Box sx={{ flex: 1, overflow: 'auto', p: 1, display: 'flex', flexDirection: 'column', gap: '1px' }}>
        {grupos.map((grupo, indice) => (
          <Box key={indice} sx={{ display: 'flex', flexDirection: 'column', gap: '1px', mt: indice > 0 ? 2 : 0 }}>
            {grupo.titulo && (
              <Typography variant="overline" sx={{ px: 1.5, py: 0.5, color: 'rgba(255,255,255,.42)' }}>
                {grupo.titulo}
              </Typography>
            )}
            {grupo.items.map((item) => (
              <ItemNav key={item.id} item={item} />
            ))}
          </Box>
        ))}
      </Box>

      {usuario && (
        <Box
          sx={{
            p: 1.5,
            flex: 'none',
            borderTop: '1px solid rgba(255,255,255,.10)',
            display: 'flex',
            alignItems: 'center',
            gap: 1,
            fontSize: 12,
            color: 'rgba(255,255,255,.6)',
          }}
        >
          <Avatar
            sx={(t) => ({
              width: 26,
              height: 26,
              fontSize: 11,
              fontWeight: 600,
              backgroundColor: t.palette.roles.terapeuta.fg,
            })}
          >
            {iniciales(usuario.nombre_completo)}
          </Avatar>
          <Box
            component="span"
            sx={{ flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
          >
            {usuario.nombre_completo}
          </Box>
        </Box>
      )}
    </Box>
  );
}

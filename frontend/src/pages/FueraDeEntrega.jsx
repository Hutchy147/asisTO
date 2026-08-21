// frontend/src/pages/FueraDeEntrega.jsx
//
// La pantalla existe en el código pero no en la entrega que se está
// mostrando. NO es un 403 y por eso no reusa `NoAutorizado`: ahí el problema
// es el rol y el mensaje diría algo falso —"el rol terapeuta no puede ver
// esta pantalla"— cuando en realidad sí puede, sólo que en otra versión.
//
// Existe porque esconder el menú no alcanza: si a la pantalla se llega
// escribiendo la URL, en la demostración de la Entrega 1 aparece algo de la 2.

import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';
import { useNavigate } from 'react-router-dom';

import { RUTA_POR_ROL, useAuth } from '../context/AuthContext.jsx';
import { CAPACIDADES, ENTREGA_ACTIVA, NOMBRE_DE_ENTREGA } from '../config/entregas.js';

export default function FueraDeEntrega({ capacidad }) {
  const { rol } = useAuth();
  const navigate = useNavigate();

  const declarada = CAPACIDADES[capacidad];
  const rutaPropia = RUTA_POR_ROL[rol] ?? '/login';

  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        p: 2,
      }}
    >
      <Paper elevation={2} sx={{ p: 4, maxWidth: 520, width: '100%', textAlign: 'center' }}>
        <Typography variant="overline" color="text.secondary">
          {NOMBRE_DE_ENTREGA[ENTREGA_ACTIVA] ?? `Entrega ${ENTREGA_ACTIVA}`}
        </Typography>
        <Typography variant="h6" gutterBottom sx={{ mt: 1 }}>
          Esta pantalla todavía no existe
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
          {declarada ? (
            <>
              <strong>{declarada.nombre}</strong> llega en la entrega{' '}
              <strong>{declarada.entrega}</strong>, y ahora se está mostrando la{' '}
              <strong>{ENTREGA_ACTIVA}</strong>. No es un problema de permisos:
              en la versión completa esta pantalla está.
            </>
          ) : (
            <>
              Se está mostrando la entrega <strong>{ENTREGA_ACTIVA}</strong> y esta
              pantalla no pertenece a ella.
            </>
          )}
        </Typography>

        <Button variant="contained" onClick={() => navigate(rutaPropia, { replace: true })}>
          Ir a mi inicio
        </Button>
      </Paper>
    </Box>
  );
}

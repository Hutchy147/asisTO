// frontend/src/pages/RestablecerContrasena.jsx
// Elige la contraseña nueva con el token del enlace. El token es de un solo
// uso y vence a la hora: si no sirve, el servidor lo dice y se ofrece pedir otro.

import { useEffect, useState } from 'react';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Link from '@mui/material/Link';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import { Link as RouterLink, Navigate, useParams } from 'react-router-dom';

import { hayCapacidad } from '../config/entregas.js';
import { restablecerContrasena, verificarEnlaceRecuperacion } from '../services/api.js';

export default function RestablecerContrasena() {
  const { token } = useParams();
  const [clave, setClave] = useState('');
  const [repetida, setRepetida] = useState('');
  const [error, setError] = useState(null); // { mensaje, campo }
  const [enviando, setEnviando] = useState(false);
  const [listo, setListo] = useState(false);
  // null = consultando; false = el enlace ya no sirve (usado o vencido).
  const [vigente, setVigente] = useState(null);

  useEffect(() => {
    let cancelado = false;
    verificarEnlaceRecuperacion(token)
      .then((r) => { if (!cancelado) setVigente(Boolean(r?.vigente)); })
      // Sin respuesta no se bloquea: el servidor vuelve a validar al enviar.
      .catch(() => { if (!cancelado) setVigente(true); });
    return () => { cancelado = true; };
  }, [token]);

  if (!hayCapacidad('auth.recuperar')) return <Navigate to="/login" replace />;

  const noCoinciden = repetida.length > 0 && clave !== repetida;

  async function enviar(evento) {
    evento.preventDefault();
    setError(null);
    setEnviando(true);
    try {
      await restablecerContrasena(token, clave);
      setListo(true);
    } catch (fallo) {
      setError({ mensaje: fallo.message || 'No se pudo cambiar la contraseña.', campo: fallo.campo });
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Box sx={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', p: 2 }}>
      <Paper elevation={2} sx={{ p: 4, maxWidth: 420, width: '100%' }}>
        <Typography variant="h4" sx={{ color: 'primary.main', mb: 0.5 }}>AsisTO</Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
          Elegir una contraseña nueva
        </Typography>

        {!listo && vigente === false ? (
          <Stack spacing={2}>
            <Alert severity="warning">
              Este enlace ya no es válido: se usó o venció (dura una hora y sirve una sola vez).
            </Alert>
            <Button component={RouterLink} to="/recuperar" variant="contained" size="large">Pedir un enlace nuevo</Button>
            <Button component={RouterLink} to="/login" variant="text">Volver al inicio de sesión</Button>
          </Stack>
        ) : listo ? (
          <Stack spacing={2}>
            <Alert severity="success">Contraseña actualizada. Ya puede ingresar con la nueva.</Alert>
            <Button component={RouterLink} to="/login" variant="contained" size="large">Ir al inicio de sesión</Button>
          </Stack>
        ) : (
          <form onSubmit={enviar} noValidate>
            <Stack spacing={2}>
              <TextField
                label="Contraseña nueva" type="password" value={clave} autoFocus required fullWidth
                onChange={(e) => setClave(e.target.value)} autoComplete="new-password"
                error={error?.campo === 'contrasena_nueva'}
                helperText="Al menos 8 caracteres, con letras y números."
              />
              <TextField
                label="Repetir la contraseña" type="password" value={repetida} required fullWidth
                onChange={(e) => setRepetida(e.target.value)} autoComplete="new-password"
                error={noCoinciden} helperText={noCoinciden ? 'No coinciden.' : ' '}
              />
              {error && (
                <Alert severity="error">
                  {error.mensaje}
                  {error.campo === 'token' && (
                    <>{' '}<Link component={RouterLink} to="/recuperar">Pedir un enlace nuevo</Link></>
                  )}
                </Alert>
              )}
              <Button
                type="submit" variant="contained" size="large" fullWidth
                disabled={enviando || !clave || clave !== repetida}
              >
                {enviando ? 'Guardando…' : 'Cambiar contraseña'}
              </Button>
            </Stack>
          </form>
        )}
      </Paper>
    </Box>
  );
}

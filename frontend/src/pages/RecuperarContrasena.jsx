// frontend/src/pages/RecuperarContrasena.jsx
// Pide el enlace de recuperacion. Responde igual exista o no la cuenta.
// Sin servidor de mail, en desarrollo la API devuelve el token y se muestra
// el enlace en pantalla; en produccion ese campo no viene y solo se ve el aviso.

import { useState } from 'react';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Link from '@mui/material/Link';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import { Link as RouterLink, Navigate } from 'react-router-dom';

import { hayCapacidad } from '../config/entregas.js';
import { pedirRecuperacion } from '../services/api.js';

export default function RecuperarContrasena() {
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [enviando, setEnviando] = useState(false);
  const [respuesta, setRespuesta] = useState(null);

  if (!hayCapacidad('auth.recuperar')) return <Navigate to="/login" replace />;

  async function enviar(evento) {
    evento.preventDefault();
    setError('');
    setEnviando(true);
    try {
      setRespuesta(await pedirRecuperacion(email.trim()));
    } catch (fallo) {
      setError(fallo.message || 'No se pudo pedir el enlace.');
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Box sx={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', p: 2 }}>
      <Paper elevation={2} sx={{ p: 4, maxWidth: 420, width: '100%' }}>
        <Typography variant="h4" sx={{ color: 'primary.main', mb: 0.5 }}>AsisTO</Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
          Recuperar la contraseña
        </Typography>

        {respuesta ? (
          <Stack spacing={2}>
            <Alert severity="success">{respuesta.mensaje}</Alert>
            {respuesta.token_desarrollo && (
              <Alert severity="info">
                Modo desarrollo (sin servidor de mail):{' '}
                <Link component={RouterLink} to={`/restablecer/${respuesta.token_desarrollo}`}>
                  abrir el enlace de recuperación
                </Link>
              </Alert>
            )}
            <Link component={RouterLink} to="/login" underline="hover">Volver al inicio de sesión</Link>
          </Stack>
        ) : (
          <form onSubmit={enviar} noValidate>
            <Stack spacing={2}>
              <Typography variant="body2" color="text.secondary">
                Ingrese el email de su cuenta y se generará un enlace para elegir una contraseña nueva.
              </Typography>
              <TextField
                label="Email" type="email" value={email} autoFocus required fullWidth
                onChange={(e) => setEmail(e.target.value)} autoComplete="username"
              />
              {error && <Alert severity="error">{error}</Alert>}
              <Button type="submit" variant="contained" size="large" disabled={enviando || !email} fullWidth>
                {enviando ? 'Enviando…' : 'Pedir enlace'}
              </Button>
              <Link component={RouterLink} to="/login" underline="hover" sx={{ textAlign: 'center' }}>
                Volver al inicio de sesión
              </Link>
            </Stack>
          </form>
        )}
      </Paper>
    </Box>
  );
}

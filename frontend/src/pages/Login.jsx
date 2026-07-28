// frontend/src/pages/Login.jsx
// Pantalla de inicio de sesion. Todos los colores salen del theme.

import { useState } from 'react';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';

import { RUTA_POR_ROL, useAuth } from '../context/AuthContext.jsx';

export default function Login() {
  const { login, autenticado, rol, cargando, avisoSesion } = useAuth();
  const navigate = useNavigate();
  const ubicacion = useLocation();

  const [email, setEmail] = useState('');
  const [contrasena, setContrasena] = useState('');
  const [error, setError] = useState('');
  const [enviando, setEnviando] = useState(false);

  // El aviso de sesion vencida NO se limpia al desmontar esta pantalla.
  // Se intento asi y no funciona: con StrictMode React monta, desmonta y
  // vuelve a montar en desarrollo, y esa limpieza borraba el aviso apenas
  // aparecia. Se limpia donde corresponde: al loguearse bien o al salir.

  if (cargando) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  // Ya logueado: no tiene sentido ver el login. Va a su dashboard.
  if (autenticado) {
    return <Navigate to={RUTA_POR_ROL[rol] ?? '/'} replace />;
  }

  async function manejarEnvio(evento) {
    evento.preventDefault();
    setError('');
    setEnviando(true);

    try {
      const usuario = await login(email.trim(), contrasena);
      const destino = ubicacion.state?.desde ?? RUTA_POR_ROL[usuario.rol] ?? '/';
      navigate(destino, { replace: true });
    } catch (fallo) {
      // El backend devuelve el mismo mensaje si el email no existe o si la
      // contrasena esta mal. Se muestra tal cual: no hay que "mejorarlo"
      // aclarando cual de los dos fallo.
      setError(fallo.message || 'No se pudo iniciar sesion.');
    } finally {
      setEnviando(false);
    }
  }

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
      <Paper elevation={2} sx={{ p: 4, maxWidth: 420, width: '100%' }}>
        <Typography variant="h4" sx={{ color: 'primary.main', mb: 0.5 }}>
          AsisTO
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
          Gestion de asistencias y seguimiento terapeutico
        </Typography>

        {avisoSesion && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            {avisoSesion}
          </Alert>
        )}

        <form onSubmit={manejarEnvio} noValidate>
          <Stack spacing={2}>
            <TextField
              label="Email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="username"
              autoFocus
              required
              fullWidth
            />
            <TextField
              label="Contrasena"
              type="password"
              value={contrasena}
              onChange={(e) => setContrasena(e.target.value)}
              autoComplete="current-password"
              required
              fullWidth
            />

            {error && <Alert severity="error">{error}</Alert>}

            <Button
              type="submit"
              variant="contained"
              size="large"
              disabled={enviando || !email || !contrasena}
              fullWidth
            >
              {enviando ? 'Ingresando...' : 'Ingresar'}
            </Button>
          </Stack>
        </form>
      </Paper>
    </Box>
  );
}

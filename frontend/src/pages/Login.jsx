// frontend/src/pages/Login.jsx
// Pantalla de inicio de sesion. Todos los colores salen del theme.

import { useState } from 'react';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import Link from '@mui/material/Link';
import { Link as RouterLink, Navigate, useLocation, useNavigate } from 'react-router-dom';

import { hayCapacidad } from '../config/entregas.js';
import LogoAsisto, { Isotipo } from '../components/marca/LogoAsisto.jsx';

import { rolPuedeVer } from '../config/rutas.js';
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

      // El destino guardado SOLO vale si el rol que acaba de entrar puede
      // verlo. Si no puede, se descarta EN SILENCIO y se va a su inicio.
      //
      // Antes esta linea era `ubicacion.state?.desde ?? RUTA_POR_ROL[...]`,
      // o sea que el destino guardado ganaba siempre. Con eso, a un
      // terapeuta que venia de `/rrhh` —porque se le vencio la sesion ahi, o
      // porque salio desde ahi— el login lo dejaba en la pantalla 403. La
      // sesion estaba bien; lo que estaba mal era a donde lo mandabamos.
      //
      // NO se ignora el destino guardado: el caso legitimo es el que mas
      // pasa. A quien se le vence la sesion en una pantalla SUYA, volver ahi
      // despues de reloguear es lo util, y eso se conserva. La regla es "si
      // el rol no puede, se descarta", no "se descarta siempre".
      //
      // Se descarta CALLADO a proposito: el usuario no pidió ir a /rrhh, lo
      // pidió el estado que arrastraba la sesión anterior. Avisarle de algo
      // que no hizo solo lo confunde.
      const guardado = ubicacion.state?.desde;
      // Solo rutas internas: nada de «//otro-sitio» ni barras invertidas, que
      // algunos navegadores leen como otro dominio (redirección abierta).
      const interno = typeof guardado === 'string' && guardado.startsWith('/')
        && !guardado.startsWith('//') && !guardado.includes('\\');
      const destino = interno && rolPuedeVer(usuario.rol, guardado)
        ? guardado
        : (RUTA_POR_ROL[usuario.rol] ?? '/');

      navigate(destino, { replace: true });
    } catch (fallo) {
      // El backend devuelve el mismo mensaje si el email no existe o si la
      // contrasena esta mal. Se muestra tal cual: no hay que "mejorarlo"
      // aclarando cual de los dos fallo.
      setError(fallo.message || 'No se pudo iniciar sesión.');
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'grid',
        gridTemplateColumns: { xs: '1fr', md: '1.05fr 1fr' },
        gridTemplateRows: '1fr',
        '@keyframes subir': {
          from: { opacity: 0, transform: 'translateY(14px)' },
          to: { opacity: 1, transform: 'translateY(0)' },
        },
        '@keyframes flotar': {
          '0%, 100%': { transform: 'translate3d(0,0,0) scale(1)' },
          '50%': { transform: 'translate3d(26px,-22px,0) scale(1.08)' },
        },
        '@keyframes trazar': { to: { strokeDashoffset: 0 } },
        '@keyframes aparecer': { from: { opacity: 0 }, to: { opacity: 1 } },
        '@media (prefers-reduced-motion: reduce)': {
          '& *': { animation: 'none !important', transition: 'none !important' },
        },
      }}
    >
      {/* --- Panel de marca --- */}
      <Box
        sx={{
          position: 'relative',
          overflow: 'hidden',
          color: '#fff',
          background: 'linear-gradient(150deg, #1B3B5C 0%, #1F4A63 55%, #2F6F60 100%)',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          p: 6,
          // En celular el panel no entra: queda solo el formulario con el logo.
          display: { xs: 'none', md: 'flex' },
        }}
      >
        {/* manchas que flotan despacio */}
        <Box aria-hidden sx={{ position: 'absolute', width: 380, height: 380, borderRadius: '50%', top: -120, right: -90, background: 'radial-gradient(circle, rgba(127,169,155,0.55), rgba(127,169,155,0) 70%)', animation: 'flotar 14s ease-in-out infinite' }} />
        <Box aria-hidden sx={{ position: 'absolute', width: 320, height: 320, borderRadius: '50%', bottom: -110, left: -80, background: 'radial-gradient(circle, rgba(201,123,90,0.40), rgba(201,123,90,0) 70%)', animation: 'flotar 18s ease-in-out -6s infinite' }} />

        <Box
          sx={{
            position: 'relative', alignSelf: 'flex-start', animation: 'subir .7s ease both',
            backgroundColor: 'rgba(255,255,255,0.94)', borderRadius: '16px', p: 1.25,
            boxShadow: '0 8px 24px rgba(0,0,0,0.18)',
          }}
        >
          <Isotipo alto={52} />
        </Box>

        <Box sx={{ position: 'relative' }}>
          <Typography
            component="h2"
            sx={{ fontFamily: '"Plus Jakarta Sans", sans-serif', fontWeight: 700, fontSize: 34, lineHeight: 1.15, letterSpacing: '-0.02em', maxWidth: 420, animation: 'subir .8s .15s ease both' }}
          >
            Cada sesión cuenta, y cada avance se ve.
          </Typography>
          <Typography sx={{ mt: 1.5, maxWidth: 400, opacity: 0.8, fontSize: 15, animation: 'subir .8s .3s ease both' }}>
            Gestión de asistencias y seguimiento terapéutico, en un solo lugar.
          </Typography>

          {/* curva que se dibuja sola */}
          <Box component="svg" viewBox="0 0 360 110" aria-hidden sx={{ mt: 4, width: '100%', maxWidth: 380, overflow: 'visible' }}>
            <path d="M4 96 H356" stroke="rgba(255,255,255,0.18)" strokeWidth="1" />
            <path d="M4 52 H356" stroke="rgba(255,255,255,0.10)" strokeWidth="1" strokeDasharray="3 5" />
            <path
              d="M6 92 C 70 92, 84 64, 140 60 S 230 46, 290 20 S 336 12, 352 12"
              fill="none" stroke="#fff" strokeWidth="3" strokeLinecap="round"
              strokeDasharray="520" strokeDashoffset="520"
              style={{ animation: 'trazar 2.2s .6s cubic-bezier(.3,.7,.2,1) forwards' }}
            />
            <circle cx="352" cy="12" r="6" fill="#D9A441" stroke="#fff" strokeWidth="2" style={{ opacity: 0, animation: 'aparecer .4s 2.6s forwards' }} />
          </Box>
        </Box>

        <Typography variant="caption" sx={{ position: 'relative', opacity: 0.7 }}>
          Práctica Profesionalizante III · IES 9-023
        </Typography>
      </Box>

      {/* --- Formulario --- */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', p: { xs: 2.5, md: 6 }, backgroundColor: 'background.default' }}>
        <Box sx={{ width: '100%', maxWidth: 380, animation: 'subir .7s .1s ease both' }}>
          <Box sx={{ mb: 3, animation: 'subir .7s ease both' }}>
            <LogoAsisto alto={104} />
          </Box>
          <Typography variant="h4" component="h1" sx={{ mb: 0.5 }}>
            Bienvenido
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 3.5 }}>
            Ingrese con su cuenta para continuar.
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
                label="Contraseña"
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
                sx={{ transition: 'transform .15s ease, box-shadow .15s ease', '&:not(:disabled):hover': { transform: 'translateY(-1px)' } }}
              >
                {enviando ? 'Ingresando...' : 'Ingresar'}
              </Button>

              {hayCapacidad('auth.recuperar') && (
                <Link component={RouterLink} to="/recuperar" underline="hover" sx={{ textAlign: 'center' }}>
                  ¿Olvidó su contraseña?
                </Link>
              )}
            </Stack>
          </form>
        </Box>
      </Box>
    </Box>
  );
}

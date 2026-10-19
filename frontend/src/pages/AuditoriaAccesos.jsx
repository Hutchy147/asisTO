// frontend/src/pages/AuditoriaAccesos.jsx
// Auditoría de accesos para RRHH: quién intentó entrar, cuándo y con qué
// resultado. Solo lectura. Nunca muestra contraseñas (la tabla no las guarda).

import { useMemo, useState } from 'react';
import AppBar from '@mui/material/AppBar';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Container from '@mui/material/Container';
import Grid from '@mui/material/Grid';
import MenuItem from '@mui/material/MenuItem';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Toolbar from '@mui/material/Toolbar';
import Typography from '@mui/material/Typography';
import { useNavigate } from 'react-router-dom';

import DataTable from '../components/data/DataTable.jsx';
import StatTile from '../components/data/StatTile.jsx';
import { Cargando, EstadoError, EstadoVacio } from '../components/estado/index.js';
import { useAuth } from '../context/AuthContext.jsx';
import { usePeticion } from '../hooks/usePeticion.js';
import { obtenerAuditoriaAccesos } from '../services/rrhhService.js';

const RESULTADOS = {
  exitoso: { etiqueta: 'Exitoso', color: 'success' },
  fallido: { etiqueta: 'Fallido', color: 'warning' },
  bloqueado: { etiqueta: 'Bloqueado', color: 'error' },
};

const iso = (f) => f.toISOString().slice(0, 10);

function ventanaInicial() {
  const hasta = new Date();
  const desde = new Date();
  desde.setDate(desde.getDate() - 7);
  return { desde: iso(desde), hasta: iso(hasta), resultado: '', email: '' };
}

function formatearMomento(texto) {
  // 'AAAA-MM-DD HH:MM:SS' -> 'DD/MM/AAAA HH:MM'
  const m = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/.exec(texto ?? '');
  return m ? `${m[3]}/${m[2]}/${m[1]} ${m[4]}:${m[5]}` : (texto ?? '—');
}

export default function AuditoriaAccesos() {
  const { usuario, logout } = useAuth();
  const navigate = useNavigate();
  const inicial = useMemo(ventanaInicial, []);
  const [borrador, setBorrador] = useState(inicial);
  const [aplicado, setAplicado] = useState(inicial);

  const accesos = usePeticion(
    () => obtenerAuditoriaAccesos(aplicado),
    [aplicado.desde, aplicado.hasta, aplicado.resultado, aplicado.email]
  );
  const datos = accesos.datos;

  const columnas = [
    { clave: 'fecha', etiqueta: 'Fecha y hora', ancho: 170, render: (a) => formatearMomento(a.fecha) },
    {
      clave: 'email', etiqueta: 'Email', truncar: true,
      // texto-libre: en un intento fallido el email lo escribió cualquiera.
      render: (a) => <span className="texto-libre">{a.email}</span>,
    },
    {
      clave: 'resultado', etiqueta: 'Resultado', ancho: 130,
      render: (a) => <Chip size="small" color={RESULTADOS[a.resultado]?.color} label={RESULTADOS[a.resultado]?.etiqueta ?? a.resultado} />,
    },
    {
      clave: 'cuenta', etiqueta: 'Cuenta', ancho: 150,
      render: (a) => (a.id_usuario ? `Usuario ${a.id_usuario}` : <Box component="span" sx={{ color: 'text.secondary' }}>Sin cuenta</Box>),
    },
    { clave: 'ip', etiqueta: 'IP', ancho: 140, render: (a) => a.ip ?? '—' },
  ];

  return (
    <Box sx={{ minHeight: '100vh' }}>
      <AppBar position="static" elevation={0} sx={(t) => ({ backgroundColor: t.palette.roles.rrhh.fg })}>
        <Toolbar>
          <Typography variant="h6" sx={{ flexGrow: 1 }}>AsisTO</Typography>
          <Stack direction="row" spacing={2} alignItems="center">
            <Typography variant="body2" className="texto-libre" noWrap>{usuario?.nombre_completo}</Typography>
            <Button color="inherit" variant="outlined" onClick={() => navigate('/rrhh')}>Volver al panel</Button>
            <Button color="inherit" variant="outlined" onClick={logout}>Cerrar sesión</Button>
          </Stack>
        </Toolbar>
      </AppBar>

      <Container maxWidth="lg" sx={{ py: 4 }}>
        <Typography variant="h4">Auditoría de accesos</Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
          Cada intento de inicio de sesión: exitoso, fallido o bloqueado. No se guardan contraseñas.
        </Typography>

        <Box
          component="form"
          onSubmit={(e) => { e.preventDefault(); setAplicado(borrador); }}
          sx={(t) => ({
            display: 'flex', flexWrap: 'wrap', gap: 2, alignItems: 'flex-end', p: 2, mb: 3,
            backgroundColor: t.palette.superficie.tarjeta,
            border: `1px solid ${t.palette.superficie.borde}`,
            borderRadius: `${t.formas.md}px`,
          })}
        >
          <TextField label="Desde" type="date" size="small" InputLabelProps={{ shrink: true }}
            value={borrador.desde} onChange={(e) => setBorrador({ ...borrador, desde: e.target.value })} />
          <TextField label="Hasta" type="date" size="small" InputLabelProps={{ shrink: true }}
            value={borrador.hasta} onChange={(e) => setBorrador({ ...borrador, hasta: e.target.value })} />
          <TextField select label="Resultado" size="small" sx={{ minWidth: 160 }}
            value={borrador.resultado} onChange={(e) => setBorrador({ ...borrador, resultado: e.target.value })}>
            <MenuItem value="">Todos</MenuItem>
            {Object.entries(RESULTADOS).map(([clave, r]) => <MenuItem key={clave} value={clave}>{r.etiqueta}</MenuItem>)}
          </TextField>
          <TextField label="Email contiene" size="small" sx={{ minWidth: 220 }}
            value={borrador.email} onChange={(e) => setBorrador({ ...borrador, email: e.target.value })} />
          <Button type="submit" variant="contained">Ver accesos</Button>
        </Box>

        {accesos.cargando && <Cargando texto="Buscando los accesos..." />}
        {accesos.error && <EstadoError error={accesos.error} onReintentar={accesos.recargar} />}

        {datos && !accesos.cargando && !accesos.error && (
          <>
            <Grid container spacing={1.5} sx={{ mb: 3 }}>
              <Grid item xs={12} sm={3}><StatTile etiqueta="Intentos del período" valor={datos.resumen.total} nota="Todos los del filtro" /></Grid>
              <Grid item xs={12} sm={3}><StatTile etiqueta="Exitosos" valor={datos.resumen.exitoso} nota="Recuento" /></Grid>
              <Grid item xs={12} sm={3}><StatTile etiqueta="Fallidos" valor={datos.resumen.fallido} nota="Clave o email incorrectos" /></Grid>
              <Grid item xs={12} sm={3}><StatTile etiqueta="Bloqueados" valor={datos.resumen.bloqueado} nota="Cuenta bloqueada" /></Grid>
            </Grid>

            {datos.accesos.length === 0 ? (
              <EstadoVacio titulo="No hay accesos con ese filtro" descripcion="Pruebe con un rango más amplio o quite el filtro de resultado." />
            ) : (
              <>
                <DataTable columnas={columnas} filas={datos.accesos} claveFila={(a) => a.id} />
                {datos.resumen.total > datos.accesos.length && (
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                    Se muestran los {datos.accesos.length} más recientes de {datos.resumen.total}. Los
                    recuentos de arriba son sobre todos. Acotá el período o filtrá para ver el resto.
                  </Typography>
                )}
              </>
            )}
          </>
        )}
      </Container>
    </Box>
  );
}

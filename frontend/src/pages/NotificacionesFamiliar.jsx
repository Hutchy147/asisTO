// frontend/src/pages/NotificacionesFamiliar.jsx
// Avisos del tratamiento (Entrega 4): historial con filtros, marcar como
// leído y activar o desactivar cada tipo de aviso.

import { useState } from 'react';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import FormControlLabel from '@mui/material/FormControlLabel';
import MenuItem from '@mui/material/MenuItem';
import Snackbar from '@mui/material/Snackbar';
import Switch from '@mui/material/Switch';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';

import BarraFamiliar from '../components/familiar/BarraFamiliar.jsx';
import { Cargando, EstadoError, EstadoVacio } from '../components/estado/index.js';
import { usePeticion } from '../hooks/usePeticion.js';
import { hayCapacidad } from '../config/entregas.js';
import {
  guardarPreferencia, listarNotificaciones, marcarNotificacion, marcarTodasLeidas,
  obtenerPreferencias,
} from '../services/notificacionesService.js';

function fechaHora(iso) {
  const d = new Date(iso);
  const dos = (n) => String(n).padStart(2, '0');
  return `${dos(d.getDate())}/${dos(d.getMonth() + 1)}/${d.getFullYear()} ${dos(d.getHours())}:${dos(d.getMinutes())}`;
}

export default function NotificacionesFamiliar() {
  const [tipo, setTipo] = useState('');
  const [leida, setLeida] = useState('');
  const [error, setError] = useState('');

  const lista = usePeticion(() => listarNotificaciones({ tipo, leida }), [tipo, leida]);
  const preferencias = usePeticion(() => obtenerPreferencias(), []);

  const [guardado, setGuardado] = useState('');

  const accion = async (funcion) => {
    setError('');
    try {
      await funcion();
      // El contador de la barra se actualiza en el acto (antes quedaba el
      // número viejo hasta recargar la página).
      if (funcion === marcarTodasLeidas && lista.datos) {
        lista.setDatos({
          ...lista.datos,
          no_leidas: 0,
          notificaciones: lista.datos.notificaciones.map((n) => ({ ...n, leida: true })),
        });
      }
      lista.recargar();
    } catch (fallo) {
      setError(fallo.message);
    }
  };

  const cambiarPreferencia = async (item, habilitada) => {
    setError('');
    try {
      const respuesta = await guardarPreferencia(item.tipo, habilitada);
      preferencias.setDatos(respuesta);
      // Confirmación visible: sin ella no se sabía si el cambio había quedado.
      setGuardado(habilitada
        ? `Listo: va a recibir los avisos de «${item.etiqueta}».`
        : `Listo: ya no va a recibir los avisos de «${item.etiqueta}».`);
    } catch (fallo) {
      setError(fallo.message);
    }
  };

  const noLeidas = lista.datos?.no_leidas ?? 0;
  // En una entrega sin informes para la familia (modos 4 y 5) el tipo
  // «Informe generado» no existe todavía: ni su interruptor ni sus avisos (H29).
  const tipoVisible = (t) => t !== 'informe_generado' || hayCapacidad('familiar.informes');
  const tipos = (preferencias.datos?.preferencias ?? []).filter((p) => tipoVisible(p.tipo));
  const avisos = (lista.datos?.notificaciones ?? []).filter((n) => tipoVisible(n.tipo));

  return (
    <BarraFamiliar activa="avisos" sinLeer={noLeidas}>
      <Typography variant="h4">Avisos</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Novedades del tratamiento. Los avisos se ven en esta página y en el contador de la barra
        superior; no se envían por correo. Más abajo puede elegir qué tipos de aviso desea recibir.
      </Typography>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      <Box
        sx={(t) => ({
          backgroundColor: t.palette.superficie.tarjeta,
          border: `1px solid ${t.palette.superficie.borde}`,
          borderRadius: `${t.formas.md}px`,
        })}
      >
        <Box
          sx={(t) => ({
            display: 'flex', flexWrap: 'wrap', gap: 2, alignItems: 'center', px: 2.25, py: 1.75,
            borderBottom: `1px solid ${t.palette.superficie.borde}`,
          })}
        >
          <Typography variant="h5" sx={{ flex: 1, minWidth: 160 }}>Historial</Typography>
          <TextField id="filtro-tipo" select size="small" label="Tipo" value={tipo} sx={{ minWidth: 220 }}
            onChange={(e) => setTipo(e.target.value)}>
            <MenuItem value="">Todos</MenuItem>
            {tipos.map((item) => <MenuItem key={item.tipo} value={item.tipo}>{item.etiqueta}</MenuItem>)}
          </TextField>
          <TextField id="filtro-leida" select size="small" label="Estado" value={leida} sx={{ minWidth: 140 }}
            onChange={(e) => setLeida(e.target.value)}>
            <MenuItem value="">Todos</MenuItem>
            <MenuItem value="0">Sin leer</MenuItem>
            <MenuItem value="1">Leídos</MenuItem>
          </TextField>
          <Button variant="outlined" disabled={noLeidas === 0} onClick={() => accion(marcarTodasLeidas)}>
            Marcar todos como leídos
          </Button>
        </Box>

        {lista.cargando && <Cargando texto="Cargando los avisos..." />}
        {lista.error && <EstadoError error={lista.error} onReintentar={lista.recargar} />}
        {lista.datos && !lista.cargando && !lista.error && (
          avisos.length === 0 ? (
            <EstadoVacio
              plano
              titulo="No hay avisos para mostrar"
              descripcion={tipo || leida ? 'Pruebe con otros filtros.' : 'Cuando haya novedades del tratamiento las verá aquí.'}
            />
          ) : (
            <Box component="ul" sx={{ listStyle: 'none', m: 0, p: 0 }}>
              {avisos.map((n) => (
                <Box
                  component="li"
                  key={n.id}
                  data-testid="aviso"
                  sx={(t) => ({
                    display: 'flex', alignItems: 'flex-start', gap: 2, px: 2.25, py: 1.5,
                    borderBottom: `1px solid ${t.palette.superficie.borde}`,
                    backgroundColor: n.leida ? 'transparent' : t.palette.action.hover,
                  })}
                >
                  <Box sx={{ flex: 1, minWidth: 0 }}>
                    <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 0.5, flexWrap: 'wrap' }}>
                      <Chip size="small" label={n.tipo_etiqueta} sx={{ maxWidth: '100%', '& .MuiChip-label': { whiteSpace: 'normal' }, height: 'auto', minHeight: 24 }} />
                      <Typography variant="caption" color="text.secondary" className="tabular">{fechaHora(n.fecha)}</Typography>
                      {!n.leida && <Chip size="small" color="primary" label="Nuevo" />}
                    </Box>
                    <Typography className="texto-libre" sx={{ fontWeight: n.leida ? 400 : 600 }}>{n.mensaje}</Typography>
                  </Box>
                  <Button size="small" color="inherit" onClick={() => accion(() => marcarNotificacion(n.id, !n.leida))}>
                    {n.leida ? 'Marcar como no leído' : 'Marcar como leído'}
                  </Button>
                </Box>
              ))}
            </Box>
          )
        )}
      </Box>

      {/* Primero los avisos; la configuración, debajo (en el celular tapaba todo). */}
      <Box
        sx={(t) => ({
          backgroundColor: t.palette.superficie.tarjeta,
          border: `1px solid ${t.palette.superficie.borde}`,
          borderRadius: `${t.formas.md}px`,
          mt: 3,
        })}
      >
        <Box sx={(t) => ({ px: 2.25, py: 1.75, borderBottom: `1px solid ${t.palette.superficie.borde}` })}>
          <Typography variant="h5">Qué avisos recibir</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.25 }}>
            La elección vale para todos los pacientes vinculados a su cuenta.
          </Typography>
        </Box>
        {preferencias.cargando && <Cargando texto="Cargando sus preferencias..." />}
        {preferencias.error && <EstadoError error={preferencias.error} onReintentar={preferencias.recargar} />}
        <Box sx={{ p: 2.25, display: 'flex', flexDirection: 'column', gap: 1.5 }}>
          {tipos.map((item) => (
            <Box key={item.tipo} sx={{ display: 'flex', alignItems: 'center', gap: { xs: 0.5, sm: 2 }, flexWrap: 'wrap' }}>
              <FormControlLabel
                sx={{ m: 0, flex: 'none' }}
                control={
                  <Switch
                    checked={item.habilitada}
                    onChange={(e) => cambiarPreferencia(item, e.target.checked)}
                    inputProps={{ 'aria-label': item.etiqueta }}
                  />
                }
                label={<Typography sx={{ fontWeight: 600, minWidth: { sm: 220 } }}>{item.etiqueta}</Typography>}
              />
              <Typography variant="body2" color="text.secondary" sx={{ flex: '1 1 240px' }}>{item.descripcion}</Typography>
            </Box>
          ))}
        </Box>
      </Box>

      <Snackbar
        open={Boolean(guardado)} autoHideDuration={4000} onClose={() => setGuardado('')}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert severity="success" variant="filled" onClose={() => setGuardado('')}>{guardado}</Alert>
      </Snackbar>
    </BarraFamiliar>
  );
}

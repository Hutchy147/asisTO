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
import Switch from '@mui/material/Switch';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';

import BarraFamiliar from '../components/familiar/BarraFamiliar.jsx';
import { Cargando, EstadoError, EstadoVacio } from '../components/estado/index.js';
import { usePeticion } from '../hooks/usePeticion.js';
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

  const accion = async (funcion) => {
    setError('');
    try {
      await funcion();
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
    } catch (fallo) {
      setError(fallo.message);
    }
  };

  const noLeidas = lista.datos?.no_leidas ?? 0;
  const tipos = preferencias.datos?.preferencias ?? [];

  return (
    <BarraFamiliar activa="avisos" sinLeer={noLeidas}>
      <Typography variant="h4">Avisos</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Novedades del tratamiento. Puede elegir qué tipos de aviso desea recibir; los avisos
        anteriores se conservan en el historial.
      </Typography>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      <Box
        sx={(t) => ({
          backgroundColor: t.palette.superficie.tarjeta,
          border: `1px solid ${t.palette.superficie.borde}`,
          borderRadius: `${t.formas.md}px`,
          mb: 3,
        })}
      >
        <Box sx={(t) => ({ px: 2.25, py: 1.75, borderBottom: `1px solid ${t.palette.superficie.borde}` })}>
          <Typography variant="h5">Qué avisos recibir</Typography>
        </Box>
        {preferencias.cargando && <Cargando texto="Cargando sus preferencias..." />}
        {preferencias.error && <EstadoError error={preferencias.error} onReintentar={preferencias.recargar} />}
        <Box sx={{ p: 2.25, display: 'flex', flexDirection: 'column', gap: 1.5 }}>
          {tipos.map((item) => (
            <Box key={item.tipo} sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <FormControlLabel
                sx={{ m: 0, flex: 'none' }}
                control={
                  <Switch
                    checked={item.habilitada}
                    onChange={(e) => cambiarPreferencia(item, e.target.checked)}
                    inputProps={{ 'aria-label': item.etiqueta }}
                  />
                }
                label={<Typography sx={{ fontWeight: 600, minWidth: 220 }}>{item.etiqueta}</Typography>}
              />
              <Typography variant="body2" color="text.secondary">{item.descripcion}</Typography>
            </Box>
          ))}
        </Box>
      </Box>

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
          lista.datos.notificaciones.length === 0 ? (
            <EstadoVacio
              plano
              titulo="No hay avisos para mostrar"
              descripcion={tipo || leida ? 'Pruebe con otros filtros.' : 'Cuando haya novedades del tratamiento las verá aquí.'}
            />
          ) : (
            <Box component="ul" sx={{ listStyle: 'none', m: 0, p: 0 }}>
              {lista.datos.notificaciones.map((n) => (
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
                      <Chip size="small" label={n.tipo_etiqueta} />
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
    </BarraFamiliar>
  );
}

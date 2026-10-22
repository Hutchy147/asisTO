// frontend/src/pages/PortalPaciente.jsx
// Portal del paciente (Entrega 6, HDU 10): sus objetivos y su progreso.
// Solo lectura. Reemplaza al tablero genérico que tenía este rol.
//
// QUÉ NO HAY ACÁ, A PROPÓSITO: informes, diagnóstico, observaciones de las
// sesiones ni nombres de profesionales. El servidor no los envía, y la
// identidad sale del token: la pantalla no puede pedir los datos de otra
// persona. Las calificaciones van siempre en palabras, nunca como número.

import { useState } from 'react';
import AppBar from '@mui/material/AppBar';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Container from '@mui/material/Container';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Toolbar from '@mui/material/Toolbar';
import Typography from '@mui/material/Typography';

import GraficoEvolucion from '../components/data/GraficoEvolucion.jsx';
import { Cargando, EstadoError, EstadoVacio } from '../components/estado/index.js';
import { useAuth } from '../context/AuthContext.jsx';
import { usePeticion } from '../hooks/usePeticion.js';
import { etiquetaDeValor } from '../services/evolucionesService.js';
import { obtenerMiProgreso } from '../services/portalPacienteService.js';
import { formatearFecha } from '../utils/fechas.js';

export default function PortalPaciente() {
  const { usuario, logout } = useAuth();
  const [desde, setDesde] = useState('');
  const [hasta, setHasta] = useState('');
  const [filtro, setFiltro] = useState({ desde: '', hasta: '' });
  const rangoInvalido = Boolean(desde && hasta && desde > hasta);

  const progreso = usePeticion(() => obtenerMiProgreso(filtro), [filtro.desde, filtro.hasta]);
  const datos = progreso.datos;
  const activos = datos?.objetivos.filter((o) => o.activo) ?? [];
  const archivados = datos?.objetivos.filter((o) => !o.activo) ?? [];

  const aplicar = () => { if (!rangoInvalido) setFiltro({ desde, hasta }); };
  const limpiar = () => { setDesde(''); setHasta(''); setFiltro({ desde: '', hasta: '' }); };

  const bloque = (serie) => (
    <GraficoEvolucion
      key={serie.id}
      serie={serie}
      titulo={
        <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 1, mb: 0.5, flexWrap: 'wrap' }}>
          <Typography variant="body1" className="texto-libre" sx={{ flex: 1, minWidth: 200 }}>{serie.descripcion}</Typography>
          {serie.resumen.ultimo !== null && (
            <Chip size="small" color="primary" label={`Última calificación: ${etiquetaDeValor(serie.resumen.ultimo)}`} />
          )}
          {!serie.activo && <Chip size="small" label="Archivado" />}
        </Box>
      }
    />
  );

  return (
    <Box sx={{ minHeight: '100vh', backgroundColor: 'background.default' }}>
      <AppBar position="static" elevation={0} sx={(t) => ({ backgroundColor: t.palette.roles.paciente.fg })}>
        <Toolbar>
          <Typography variant="h6" sx={{ flexGrow: 1 }}>AsisTO · Mi seguimiento</Typography>
          <Stack direction="row" spacing={2} alignItems="center">
            <Typography variant="body2" className="texto-libre" noWrap>{usuario?.nombre_completo}</Typography>
            <Button color="inherit" variant="outlined" onClick={logout}>Cerrar sesión</Button>
          </Stack>
        </Toolbar>
      </AppBar>

      <Container maxWidth="md" sx={{ py: 4 }}>
        {progreso.cargando && <Cargando texto="Cargando su seguimiento..." />}
        {progreso.error && <EstadoError error={progreso.error} onReintentar={progreso.recargar} />}

        {datos && (
          <>
            <Typography variant="h4" className="texto-libre">{datos.paciente.nombre_completo}</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Estos son sus objetivos de trabajo y cómo viene avanzando en cada uno.
            </Typography>

            <Box
              sx={(t) => ({
                display: 'flex', flexWrap: 'wrap', gap: 2, alignItems: 'flex-end', p: 2, mb: 2,
                backgroundColor: t.palette.superficie.tarjeta, border: `1px solid ${t.palette.superficie.borde}`,
                borderRadius: `${t.formas.md}px`,
              })}
            >
              <TextField id="filtro-desde" label="Desde" type="date" size="small" value={desde}
                onChange={(e) => setDesde(e.target.value)} InputLabelProps={{ shrink: true }} error={rangoInvalido}
                helperText=" " />
              <TextField id="filtro-hasta" label="Hasta" type="date" size="small" value={hasta}
                onChange={(e) => setHasta(e.target.value)} InputLabelProps={{ shrink: true }} error={rangoInvalido}
                helperText={rangoInvalido ? 'La fecha final no puede ser anterior a la inicial.' : ' '} />
              <Box sx={{ display: 'flex', gap: 1, mb: 2.75 }}>
                <Button variant="contained" onClick={aplicar} disabled={rangoInvalido}>Filtrar</Button>
                <Button color="inherit" onClick={limpiar} disabled={!filtro.desde && !filtro.hasta && !desde && !hasta}>
                  Todo el tratamiento
                </Button>
              </Box>
            </Box>

            {datos.objetivos.length === 0 ? (
              (filtro.desde || filtro.hasta) ? (
                <EstadoVacio
                  titulo="No hay objetivos en este período"
                  descripcion="Pruebe con otro rango de fechas o vea todo el tratamiento."
                />
              ) : (
                <EstadoVacio
                  titulo="Todavía no tiene objetivos"
                  descripcion="Cuando su terapeuta defina sus objetivos de trabajo, los verá aquí."
                />
              )
            ) : (
              <Box
                sx={(t) => ({
                  backgroundColor: t.palette.superficie.tarjeta, border: `1px solid ${t.palette.superficie.borde}`,
                  borderRadius: `${t.formas.md}px`, p: 2.25, display: 'flex', flexDirection: 'column', gap: 3,
                })}
              >
                <Typography variant="h5">
                  {datos.periodo.completo
                    ? 'Mis objetivos'
                    : `Mis objetivos · del ${formatearFecha(datos.periodo.desde)} al ${formatearFecha(datos.periodo.hasta)}`}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  La línea une las calificaciones en orden. En cada sesión se trabajan algunos objetivos
                  y no todos, por eso hay tramos punteados.
                </Typography>
                {activos.map(bloque)}
                {archivados.length > 0 && (
                  <>
                    <Typography variant="h6">Objetivos ya cerrados</Typography>
                    {archivados.map(bloque)}
                  </>
                )}
              </Box>
            )}
          </>
        )}
      </Container>
    </Box>
  );
}

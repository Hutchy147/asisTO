// frontend/src/pages/Calendario.jsx
// Calendario semanal. ESTRUCTURA PROVISORIA, sin diseño final.

import { useMemo, useState } from 'react';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Grid from '@mui/material/Grid';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

import SesionEstadoChip from '../components/data/SesionEstadoChip.jsx';
import AppLayout from '../components/layout/AppLayout.jsx';
import { Cargando, EstadoError } from '../components/estado/index.js';
import { usePeticion } from '../hooks/usePeticion.js';
import { listarSesiones } from '../services/sesionesService.js';

const DIAS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'];

/** Lunes de la semana de `fecha`. */
function inicioDeSemana(fecha) {
  const dia = new Date(fecha);
  const desplazamiento = (dia.getDay() + 6) % 7; // domingo = 0 -> 6
  dia.setDate(dia.getDate() - desplazamiento);
  dia.setHours(0, 0, 0, 0);
  return dia;
}

function aIso(fecha) {
  // toISOString() convierte a UTC y puede correr un dia segun la zona
  const mes = String(fecha.getMonth() + 1).padStart(2, '0');
  const dia = String(fecha.getDate()).padStart(2, '0');
  return `${fecha.getFullYear()}-${mes}-${dia}`;
}

export default function Calendario() {
  const [lunes, setLunes] = useState(() => inicioDeSemana(new Date()));

  const { desde, hasta, dias } = useMemo(() => {
    const listaDias = Array.from({ length: 7 }, (_, i) => {
      const dia = new Date(lunes);
      dia.setDate(lunes.getDate() + i);
      return dia;
    });
    return {
      desde: aIso(listaDias[0]),
      hasta: aIso(listaDias[6]),
      dias: listaDias,
    };
  }, [lunes]);

  const { datos, cargando, error, recargar } = usePeticion(
    () => listarSesiones({ desde, hasta }), [desde, hasta]
  );

  // Sesiones agrupadas por fecha, para no recorrer la lista por cada dia
  const porFecha = useMemo(() => {
    const mapa = {};
    (datos?.sesiones ?? []).forEach((sesion) => {
      (mapa[sesion.fecha] ??= []).push(sesion);
    });
    return mapa;
  }, [datos]);

  const mover = (semanas) => {
    const nuevo = new Date(lunes);
    nuevo.setDate(lunes.getDate() + semanas * 7);
    setLunes(nuevo);
  };

  return (
    <AppLayout titulo="Calendario">
      <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 3 }}>
        <Button variant="outlined" onClick={() => mover(-1)}>
          Semana anterior
        </Button>
        <Button variant="outlined" onClick={() => setLunes(inicioDeSemana(new Date()))}>
          Esta semana
        </Button>
        <Button variant="outlined" onClick={() => mover(1)}>
          Semana siguiente
        </Button>
        <Typography variant="body2" color="text.secondary">
          {desde} al {hasta}
          {datos ? ` · ${datos.total} sesiones` : ''}
        </Typography>
      </Stack>

      {cargando && <Cargando texto="Cargando la semana..." />}
      {error && <EstadoError error={error} onReintentar={recargar} />}

      {datos && !cargando && !error && (
        <>
          {/* La grilla se dibuja SIEMPRE, aunque la semana este vacia. En
              un calendario la grilla es la estructura, no el contenido:
              reemplazarla por un estado vacio deja al usuario sin la
              referencia de los dias y sin donde hacer clic para cargar una
              sesion. El aviso va arriba, no en lugar de la semana. */}
          {datos.total === 0 && (
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              No hay sesiones en esta semana. Probá con otra semana o registrá
              una sesión nueva.
            </Typography>
          )}
          <Grid container spacing={2}>
            {dias.map((dia) => {
              const iso = aIso(dia);
              const sesiones = porFecha[iso] ?? [];
              return (
                <Grid item xs={12} sm={6} md={12 / 7} key={iso}>
                  <Paper
                    elevation={1}
                    sx={{ p: 1.5, height: '100%', minHeight: 160 }}
                  >
                    <Typography variant="subtitle2">
                      {DIAS[(dia.getDay() + 6) % 7]}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {iso.slice(8)}/{iso.slice(5, 7)}
                    </Typography>

                    <Stack spacing={1} sx={{ mt: 1 }}>
                      {sesiones.length === 0 && (
                        <Typography variant="caption" color="text.secondary">
                          —
                        </Typography>
                      )}
                      {sesiones.map((sesion) => (
                        <Box
                          key={sesion.id}
                          sx={(theme) => ({
                            p: 1,
                            borderRadius: 1,
                            borderLeft: `3px solid ${theme.palette.sesionEstado[sesion.estado].fg}`,
                            backgroundColor: theme.palette.background.default,
                          })}
                        >
                          <Typography variant="caption" display="block">
                            {sesion.hora_inicio?.slice(0, 5)}
                          </Typography>
                          <Typography variant="body2" noWrap>
                            {sesion.paciente.nombre_completo}
                          </Typography>
                          <Stack direction="row" spacing={0.5} sx={{ mt: 0.5 }} flexWrap="wrap" useFlexGap>
                            <SesionEstadoChip estado={sesion.estado} />
                            {sesion.admite_evolucion && !sesion.tiene_evolucion && (
                              <Chip size="small" label="Sin evolución" color="warning" />
                            )}
                          </Stack>
                        </Box>
                      ))}
                    </Stack>
                  </Paper>
                </Grid>
              );
            })}
          </Grid>
        </>
      )}
    </AppLayout>
  );
}

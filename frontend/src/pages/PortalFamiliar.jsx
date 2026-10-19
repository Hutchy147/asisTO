// frontend/src/pages/PortalFamiliar.jsx
// Portal del familiar (Entrega 4): evolución del paciente vinculado.
//
// QUÉ NO HAY ACÁ, A PROPÓSITO: diagnóstico, observaciones de las sesiones,
// nombres de terapeutas ni números de historia. El servidor no los envía
// (ver portal_familiar_service.py): lo que no llega no se puede mostrar
// por accidente. Las calificaciones se muestran con la escala en palabras,
// nunca como número ni promedio.

import { useMemo, useState } from 'react';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Tab from '@mui/material/Tab';
import Tabs from '@mui/material/Tabs';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';

import BarraFamiliar from '../components/familiar/BarraFamiliar.jsx';
import DataTable from '../components/data/DataTable.jsx';
import GraficoEvolucion from '../components/data/GraficoEvolucion.jsx';
import SesionEstadoChip from '../components/data/SesionEstadoChip.jsx';
import { Cargando, EstadoError, EstadoVacio } from '../components/estado/index.js';
import { hayCapacidad } from '../config/entregas.js';
import { usePeticion } from '../hooks/usePeticion.js';
import { contarNoLeidas } from '../services/notificacionesService.js';
import { obtenerEvolucionVinculada, listarPacientesVinculados } from '../services/portalFamiliarService.js';
import { etiquetaDeValor } from '../services/evolucionesService.js';
import { formatearFecha, textoEdad } from '../utils/fechas.js';

const ESTADOS_PACIENTE = {
  en_tratamiento: 'En tratamiento',
  pausa: 'Tratamiento en pausa',
  alta: 'Tratamiento finalizado',
};

function Tarjeta({ titulo, descripcion, children }) {
  return (
    <Box
      sx={(t) => ({
        backgroundColor: t.palette.superficie.tarjeta,
        border: `1px solid ${t.palette.superficie.borde}`,
        borderRadius: `${t.formas.md}px`,
        mb: 2,
      })}
    >
      <Box sx={(t) => ({ px: 2.25, py: 1.75, borderBottom: `1px solid ${t.palette.superficie.borde}` })}>
        <Typography variant="h5">{titulo}</Typography>
        {descripcion && (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.25 }}>{descripcion}</Typography>
        )}
      </Box>
      {children}
    </Box>
  );
}

function EvolucionDe({ paciente }) {
  const [desde, setDesde] = useState('');
  const [hasta, setHasta] = useState('');
  const [filtro, setFiltro] = useState({ desde: '', hasta: '' });
  const [pestania, setPestania] = useState('objetivos');
  const rangoInvalido = Boolean(desde && hasta && desde > hasta);

  const evolucion = usePeticion(
    () => obtenerEvolucionVinculada(paciente.id, filtro),
    [paciente.id, filtro.desde, filtro.hasta],
  );

  const aplicar = () => { if (!rangoInvalido) setFiltro({ desde, hasta }); };
  const limpiar = () => { setDesde(''); setHasta(''); setFiltro({ desde: '', hasta: '' }); };

  const columnasSesiones = useMemo(() => [
    { clave: 'fecha', etiqueta: 'Fecha', ancho: 120, render: (s) => <span className="tabular">{formatearFecha(s.fecha)}</span> },
    { clave: 'estado', etiqueta: 'Sesión', ancho: 130, render: (s) => <SesionEstadoChip estado={s.estado_sesion} /> },
    {
      clave: 'valores', etiqueta: 'Objetivos trabajados',
      render: (s) => (s.valores.length === 0
        ? <Typography variant="body2" color="text.secondary">{s.estado_sesion === 'ausencia' ? 'Sin sesión' : 'Sin calificaciones'}</Typography>
        : (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5, py: 0.5 }}>
            {s.valores.map((v) => (
              <Box key={v.id_objetivo} sx={{ display: 'flex', gap: 1, alignItems: 'baseline' }}>
                <span className="texto-libre">{v.objetivo}</span>
                <Chip size="small" label={etiquetaDeValor(v.valor)} />
              </Box>
            ))}
          </Box>
        )),
    },
  ], []);

  const datos = evolucion.datos;

  return (
    <>
      <Box
        sx={(t) => ({
          display: 'flex', flexWrap: 'wrap', gap: 2, alignItems: 'flex-end', p: 2, mb: 2,
          backgroundColor: t.palette.superficie.tarjeta,
          border: `1px solid ${t.palette.superficie.borde}`,
          borderRadius: `${t.formas.md}px`,
        })}
      >
        <TextField
          id="filtro-desde" label="Desde" type="date" size="small" value={desde}
          onChange={(e) => setDesde(e.target.value)} InputLabelProps={{ shrink: true }}
          error={rangoInvalido}
        />
        <TextField
          id="filtro-hasta" label="Hasta" type="date" size="small" value={hasta}
          onChange={(e) => setHasta(e.target.value)} InputLabelProps={{ shrink: true }}
          error={rangoInvalido}
          helperText={rangoInvalido ? 'La fecha final no puede ser anterior a la inicial.' : ' '}
        />
        <Box sx={{ display: 'flex', gap: 1, mb: 2.75 }}>
          <Button variant="contained" onClick={aplicar} disabled={rangoInvalido}>Filtrar</Button>
          <Button color="inherit" onClick={limpiar} disabled={!filtro.desde && !filtro.hasta && !desde && !hasta}>
            Todo el tratamiento
          </Button>
        </Box>
      </Box>

      {evolucion.cargando && <Cargando texto="Cargando la evolución..." />}
      {evolucion.error && <EstadoError error={evolucion.error} onReintentar={evolucion.recargar} />}
      {datos && !evolucion.cargando && !evolucion.error && (
        <>
          <Tabs
            value={pestania} onChange={(e, v) => setPestania(v)}
            sx={(t) => ({ mb: 2, borderBottom: `1px solid ${t.palette.superficie.borde}` })}
          >
            <Tab value="objetivos" label={<Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>Objetivos <Chip size="small" label={datos.objetivos.length} /></Box>} />
            <Tab value="sesiones" label={<Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>Sesiones <Chip size="small" label={datos.total_sesiones} /></Box>} />
          </Tabs>

          {pestania === 'objetivos' && (
            <Tarjeta
              titulo="Evolución por objetivo"
              descripcion={
                datos.periodo.completo
                  ? 'Todo el tratamiento hasta hoy. Cada objetivo tiene su propio gráfico.'
                  : `Del ${formatearFecha(datos.periodo.desde)} al ${formatearFecha(datos.periodo.hasta)}.`
              }
            >
              {datos.objetivos.length === 0 || datos.total_sesiones === 0 ? (
                <EstadoVacio
                  plano
                  titulo="Todavía no hay evolución para mostrar"
                  descripcion={`Cuando ${paciente.nombre_completo} tenga sesiones registradas en este período, su evolución aparecerá aquí.`}
                />
              ) : (
                <Box sx={{ p: 2.25, display: 'flex', flexDirection: 'column', gap: 3 }}>
                  <Typography variant="body2" color="text.secondary">
                    La línea une las calificaciones en orden. En cada sesión se trabajan algunos
                    objetivos y no todos, por eso hay tramos punteados.
                  </Typography>
                  {datos.objetivos.map((serie) => (
                    <GraficoEvolucion
                      key={serie.id}
                      serie={serie}
                      titulo={
                        <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 1, mb: 0.5 }}>
                          <Typography variant="body1" className="texto-libre" sx={{ flex: 1 }}>{serie.descripcion}</Typography>
                          {serie.resumen.ultimo !== null && (
                            <Chip size="small" color="primary" label={`Última calificación: ${etiquetaDeValor(serie.resumen.ultimo)}`} />
                          )}
                          {!serie.activo && <Chip size="small" label="Archivado" />}
                        </Box>
                      }
                    />
                  ))}
                </Box>
              )}
            </Tarjeta>
          )}

          {pestania === 'sesiones' && (
            <Tarjeta titulo="Sesiones" descripcion="Las sesiones ya realizadas, de la más reciente a la más antigua, con lo trabajado en cada una.">
              {datos.sesiones.length === 0 ? (
                <EstadoVacio plano titulo="No hay sesiones en este período" descripcion="Pruebe con otro rango de fechas." />
              ) : (
                <DataTable columnas={columnasSesiones} filas={datos.sesiones} claveFila={(s) => s.id_sesion} />
              )}
            </Tarjeta>
          )}
        </>
      )}
    </>
  );
}

export default function PortalFamiliar() {
  const pacientes = usePeticion(() => listarPacientesVinculados(), []);
  const avisos = usePeticion(
    () => (hayCapacidad('notificaciones') ? contarNoLeidas() : Promise.resolve({ no_leidas: 0 })),
    [],
  );
  const [elegido, setElegido] = useState(null);

  const lista = pacientes.datos?.pacientes ?? [];
  const paciente = lista.find((p) => p.id === elegido) ?? lista[0] ?? null;

  return (
    <BarraFamiliar activa="evolucion" sinLeer={avisos.datos?.no_leidas ?? 0}>
      {pacientes.cargando && <Cargando texto="Cargando sus datos..." />}
      {pacientes.error && <EstadoError error={pacientes.error} onReintentar={pacientes.recargar} />}
      {pacientes.datos && lista.length === 0 && (
        <EstadoVacio
          titulo="Todavía no tiene pacientes vinculados"
          descripcion="El centro debe vincular su cuenta con el paciente para que pueda consultar su evolución. Comuníquese con el equipo terapéutico."
        />
      )}
      {paciente && (
        <>
          <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 2, mb: 2, flexWrap: 'wrap' }}>
            <Box sx={{ flex: 1, minWidth: 240 }}>
              <Typography variant="h4" className="texto-libre">{paciente.nombre_completo}</Typography>
              <Typography variant="body2" color="text.secondary">
                {[
                  textoEdad(paciente.fecha_nacimiento),
                  paciente.fecha_alta ? `en tratamiento desde el ${formatearFecha(paciente.fecha_alta)}` : null,
                ].filter(Boolean).join(' · ')}
              </Typography>
            </Box>
            <Chip label={ESTADOS_PACIENTE[paciente.estado] ?? paciente.estado} color={paciente.estado === 'en_tratamiento' ? 'primary' : 'default'} />
          </Box>
          {lista.length > 1 && (
            <Tabs
              value={paciente.id} onChange={(e, v) => setElegido(v)}
              sx={(t) => ({ mb: 2, borderBottom: `1px solid ${t.palette.superficie.borde}` })}
            >
              {lista.map((p) => <Tab key={p.id} value={p.id} label={p.nombre_completo} />)}
            </Tabs>
          )}
          <EvolucionDe key={paciente.id} paciente={paciente} />
        </>
      )}
    </BarraFamiliar>
  );
}

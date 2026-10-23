// frontend/src/pages/PortalFamiliar.jsx
// Portal del familiar (Entrega 4): evolución del paciente vinculado.
//
// QUÉ NO HAY ACÁ, A PROPÓSITO: diagnóstico, observaciones de las sesiones,
// nombres de terapeutas ni números de historia. El servidor no los envía
// (ver portal_familiar_service.py): lo que no llega no se puede mostrar
// por accidente. Las calificaciones se muestran con la escala en palabras,
// nunca como número ni promedio.

import { useState } from 'react';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Tab from '@mui/material/Tab';
import Tabs from '@mui/material/Tabs';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';

import BarraFamiliar from '../components/familiar/BarraFamiliar.jsx';
import EscalaExplicada from '../components/familiar/EscalaExplicada.jsx';
import GraficoEvolucion from '../components/data/GraficoEvolucion.jsx';
import { Cargando, EstadoError, EstadoVacio } from '../components/estado/index.js';
import { hayCapacidad } from '../config/entregas.js';
import { usePeticion } from '../hooks/usePeticion.js';
import { useEstadoEnUrl, useFiltrosEnUrl } from '../hooks/useEstadoEnUrl.js';
import { contarNoLeidas } from '../services/notificacionesService.js';
import { obtenerEvolucionVinculada, listarPacientesVinculados } from '../services/portalFamiliarService.js';
import { etiquetaDeValor, resumenEnPalabras } from '../services/evolucionesService.js';
import { aIsoLocal, formatearFecha, formatearHora, textoEdad } from '../utils/fechas.js';

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

/** Estado de la sesión dicho para la familia: fue o no fue. */
function EstadoParaFamilia({ estado }) {
  const falto = estado === 'ausencia';
  return (
    <Chip
      size="small"
      label={falto ? 'No asistió' : 'Asistió'}
      color={falto ? 'error' : 'success'}
      variant={falto ? 'filled' : 'outlined'}
    />
  );
}

/** Atajos de período: elegir dos fechas era lo que más costaba en el celular. */
const ATAJOS = [
  { etiqueta: 'Último mes', meses: 1 },
  { etiqueta: 'Últimos 3 meses', meses: 3 },
];

function haceMeses(meses) {
  const fecha = new Date();
  fecha.setMonth(fecha.getMonth() - meses);
  return aIsoLocal(fecha);
}

/** "12 sesiones: asistió a 11 y faltó a 1". */
function textoAsistencia(sesiones) {
  const total = sesiones.length;
  const faltas = sesiones.filter((s) => s.estado_sesion === 'ausencia').length;
  const plural = (n, uno, varios) => `${n} ${n === 1 ? uno : varios}`;
  if (total === 0) return null;
  if (faltas === 0) return `${plural(total, 'sesión', 'sesiones')} en el período, sin ausencias.`;
  return `${plural(total, 'sesión', 'sesiones')} en el período: asistió a ${total - faltas} y faltó a ${faltas}.`;
}

const TONO_RESUMEN = { bien: 'success.main', igual: 'text.primary', atencion: 'warning.dark', pocos: 'text.secondary' };

function ListaDeSesiones({ sesiones }) {
  // Tarjetas apiladas: en el celular una tabla obligaba a desplazar de costado
  // para ver la calificación.
  return (
    <Box component="ul" sx={{ listStyle: 'none', m: 0, p: 0 }}>
      {sesiones.map((s) => (
        <Box
          component="li" key={s.id_sesion}
          sx={(t) => ({ px: 2.25, py: 1.5, borderBottom: `1px solid ${t.palette.superficie.borde}` })}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap', mb: s.valores.length ? 0.75 : 0 }}>
            <Typography variant="body2" className="tabular" sx={{ fontWeight: 600 }}>
              {formatearFecha(s.fecha)}{s.hora_inicio ? ` · ${formatearHora(s.hora_inicio)}` : ''}
            </Typography>
            <EstadoParaFamilia estado={s.estado_sesion} />
            {s.estado_sesion !== 'ausencia' && s.valores.length === 0 && (
              <Typography variant="body2" color="text.secondary">Sin objetivos calificados en esta sesión.</Typography>
            )}
          </Box>
          {s.valores.map((v) => (
            <Box key={v.id_objetivo} sx={{ display: 'flex', gap: 1, alignItems: 'baseline', flexWrap: 'wrap', py: 0.25 }}>
              <Typography variant="body2" className="texto-libre" sx={{ flex: '1 1 220px' }}>{v.objetivo}</Typography>
              <Chip size="small" label={etiquetaDeValor(v.valor)} />
            </Box>
          ))}
        </Box>
      ))}
    </Box>
  );
}

function EvolucionDe({ paciente }) {
  // El período va en la URL: no se pierde al cambiar de hijo, al pasar a
  // Informes y volver, ni con F5 (pruebas de usabilidad).
  const [filtro, setFiltro] = useFiltrosEnUrl({ desde: '', hasta: '' });
  const [desde, setDesde] = useState(filtro.desde);
  const [hasta, setHasta] = useState(filtro.hasta);
  const [pestania, setPestania] = useEstadoEnUrl('vista', 'objetivos');
  // Fechas futuras escritas a mano: el `max` del campo no las frena y el
  // servidor respondía con un error técnico y «Reintentar» (usabilidad, madre).
  const hoyIso = aIsoLocal(new Date());
  const desdeFutura = Boolean(desde && desde > hoyIso);
  const hastaFutura = Boolean(hasta && hasta > hoyIso);
  const rangoInvalido = Boolean((desde && hasta && desde > hasta) || desdeFutura || hastaFutura);
  const sinFechas = !desde && !hasta;

  const evolucion = usePeticion(
    () => obtenerEvolucionVinculada(paciente.id, filtro),
    [paciente.id, filtro.desde, filtro.hasta],
  );

  const aplicar = () => { if (!rangoInvalido && !sinFechas) setFiltro({ desde, hasta }); };
  const limpiar = () => { setDesde(''); setHasta(''); setFiltro({ desde: '', hasta: '' }); };
  const atajo = (meses) => {
    const rango = { desde: haceMeses(meses), hasta: aIsoLocal(new Date()) };
    setDesde(rango.desde); setHasta(rango.hasta); setFiltro(rango);
  };
  const atajoActivo = (meses) => filtro.desde === haceMeses(meses) && filtro.hasta === aIsoLocal(new Date());

  const datos = evolucion.datos;
  // Desde cuándo hay sesiones cargadas: el tratamiento puede haber empezado
  // antes de que el centro usara el sistema.
  const primeraSesion = datos?.sesiones?.length ? datos.sesiones[datos.sesiones.length - 1].fecha : null;

  return (
    <>
      <Box
        sx={(t) => ({
          display: 'flex', flexWrap: 'wrap', gap: 2, alignItems: 'flex-start', p: 2, mb: 2,
          backgroundColor: t.palette.superficie.tarjeta,
          border: `1px solid ${t.palette.superficie.borde}`,
          borderRadius: `${t.formas.md}px`,
        })}
      >
        <TextField
          id="filtro-desde" label="Desde" type="date" size="small" value={desde} inputProps={{ max: aIsoLocal(new Date()) }}
          onChange={(e) => setDesde(e.target.value)} InputLabelProps={{ shrink: true }}
          error={desdeFutura || Boolean(desde && hasta && desde > hasta)} sx={{ flex: '1 1 150px' }}
          // Mismo hueco de ayuda que "Hasta": si no, quedan desalineados.
          helperText={desdeFutura ? 'No puede ser posterior a hoy.' : ' '}
        />
        <TextField
          id="filtro-hasta" label="Hasta" type="date" size="small" value={hasta} inputProps={{ max: aIsoLocal(new Date()) }}
          onChange={(e) => setHasta(e.target.value)} InputLabelProps={{ shrink: true }}
          error={hastaFutura || Boolean(desde && hasta && desde > hasta)} sx={{ flex: '1 1 150px' }}
          helperText={hastaFutura
            ? 'No puede ser posterior a hoy.'
            : desde && hasta && desde > hasta ? 'La fecha final no puede ser anterior a la inicial.' : ' '}
        />
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', alignItems: 'center' }}>
          <Button variant="contained" onClick={aplicar} disabled={rangoInvalido || sinFechas}>Filtrar</Button>
          <Button variant="outlined" color="inherit" onClick={limpiar} disabled={!filtro.desde && !filtro.hasta && sinFechas}>
            Todo el tratamiento
          </Button>
          {ATAJOS.map((a) => (
            <Button
              key={a.meses} onClick={() => atajo(a.meses)}
              variant={atajoActivo(a.meses) ? 'contained' : 'outlined'}
            >
              {a.etiqueta}
            </Button>
          ))}
        </Box>
        {sinFechas && (
          <Typography variant="caption" color="text.secondary" sx={{ flexBasis: '100%', mt: -1 }}>
            Use un atajo, o elija una fecha de inicio, de fin o ambas para ver solo ese período.
          </Typography>
        )}
      </Box>

      {evolucion.cargando && <Cargando texto="Cargando la evolución..." />}
      {evolucion.error && <EstadoError error={evolucion.error} onReintentar={evolucion.recargar} />}
      {datos && !evolucion.cargando && !evolucion.error && (
        <>
          <Tabs
            variant="scrollable" scrollButtons="auto" allowScrollButtonsMobile
            value={pestania} onChange={(e, v) => setPestania(v)}
            sx={(t) => ({ mb: 2, borderBottom: `1px solid ${t.palette.superficie.borde}` })}
          >
            <Tab value="objetivos" label={<Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>Objetivos <Chip size="small" label={datos.objetivos.length} /></Box>} />
            <Tab value="sesiones" label={<Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>Sesiones <Chip size="small" label={datos.total_sesiones} /></Box>} />
          </Tabs>

          {pestania === 'objetivos' && (
            <Tarjeta
              titulo="Cómo viene cada objetivo"
              descripcion={
                datos.periodo.completo
                  ? `Todo lo cargado en el sistema${primeraSesion ? ` desde la primera sesión registrada, el ${formatearFecha(primeraSesion)},` : ''} hasta hoy. Cada objetivo es algo que se está trabajando en la terapia.`
                  : `Del ${formatearFecha(datos.periodo.desde)} al ${formatearFecha(datos.periodo.hasta)}.${
                    // Si todo lo registrado cae en el período, el gráfico no cambia
                    // y parecía que el filtro no hacía nada (usabilidad, padre).
                    primeraSesion && primeraSesion > datos.periodo.desde
                      ? ` La primera sesión registrada en este período es del ${formatearFecha(primeraSesion)}.`
                      : ''}`
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
                    En cada sesión la terapeuta califica cómo le fue en algunos objetivos, de «No logrado» a
                    «Logrado». Los altibajos de una sesión a otra son normales: importa hacia dónde va.
                    {textoAsistencia(datos.sesiones) ? ` ${textoAsistencia(datos.sesiones)}` : ''}
                  </Typography>
                  <EscalaExplicada />
                  {datos.objetivos.map((serie) => {
                    const resumen = resumenEnPalabras(serie.puntos);
                    return (
                      <GraficoEvolucion
                        key={serie.id}
                        serie={serie}
                        titulo={
                          <Box sx={{ mb: 0.5 }}>
                            <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 1, flexWrap: 'wrap' }}>
                              <Typography variant="body1" className="texto-libre" sx={{ flex: '1 1 220px' }}>{serie.descripcion}</Typography>
                              {serie.resumen.ultimo !== null && (
                                <Chip size="small" color="primary" label={`Última sesión: ${etiquetaDeValor(serie.resumen.ultimo)}`} />
                              )}
                              {!serie.activo && <Chip size="small" label="Ya no se trabaja" />}
                            </Box>
                            <Typography variant="body2" sx={{ color: TONO_RESUMEN[resumen.tono], fontWeight: 600, mt: 0.25 }}>
                              {resumen.texto}
                            </Typography>
                          </Box>
                        }
                      />
                    );
                  })}
                </Box>
              )}
            </Tarjeta>
          )}

          {pestania === 'sesiones' && (
            <Tarjeta
              titulo="Sesiones"
              descripcion={`Las sesiones ya realizadas, de la más reciente a la más antigua, con lo trabajado en cada una.${
                textoAsistencia(datos.sesiones) ? ` ${textoAsistencia(datos.sesiones)}` : ''}`}
            >
              {datos.sesiones.length === 0 ? (
                <EstadoVacio plano titulo="No hay sesiones en este período" descripcion="Pruebe con otro rango de fechas." />
              ) : (
                <ListaDeSesiones sesiones={datos.sesiones} />
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
  // El paciente elegido va en la URL (?paciente=7): F5 no vuelve al primero (H32).
  const [elegidoUrl, setElegido] = useEstadoEnUrl('paciente', '');
  const elegido = Number(elegidoUrl) || null;

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
                  // «En tratamiento desde» confundía con la fecha de la primera
                  // sesión cargada y con un tratamiento en pausa.
                  paciente.fecha_alta ? `ingresó al centro el ${formatearFecha(paciente.fecha_alta)}` : null,
                ].filter(Boolean).join(' · ')}
              </Typography>
            </Box>
            <Chip label={ESTADOS_PACIENTE[paciente.estado] ?? paciente.estado} color={paciente.estado === 'en_tratamiento' ? 'primary' : 'default'} />
          </Box>
          {lista.length > 1 && (
            <Tabs
              variant="scrollable" scrollButtons="auto" allowScrollButtonsMobile
              value={paciente.id} onChange={(e, v) => setElegido(v)}
              sx={(t) => ({ mb: 2, borderBottom: `1px solid ${t.palette.superficie.borde}` })}
            >
              {lista.map((p) => <Tab key={p.id} value={p.id} label={p.nombre_completo} />)}
            </Tabs>
          )}
          {/* key: al cambiar de hijo se rearma, pero el período sigue en la URL. */}
          <EvolucionDe key={paciente.id} paciente={paciente} />
        </>
      )}
    </BarraFamiliar>
  );
}

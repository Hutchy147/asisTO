// frontend/src/components/sesiones/ModalRegistroDia.jsx
// Registro del día de UNA sesión (Entrega 3): plan y registro son el mismo
// objeto en dos momentos, como la página del cuaderno que se escribe antes y
// se anota encima después.
//
//   Pendiente de antes  lo que quedó sin cerrar en sesiones anteriores del
//                       mismo paciente (se arrastra hasta cerrarlo).
//   Objetivos           los del paciente; se marca cuál(es) se va a trabajar.
//   Plan                otras notas de lo que se piensa hacer.
//   Registro            lo que pasó; solo si la sesión ya ocurrió y no fue ausencia.
//
// "Ausente" CIERRA la sesión: no se carga registro ni evolución. El plan
// queda y pasa a la próxima sesión del paciente.

import { useState } from 'react';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Checkbox from '@mui/material/Checkbox';
import TextField from '@mui/material/TextField';
import FormControlLabel from '@mui/material/FormControlLabel';
import Radio from '@mui/material/Radio';
import RadioGroup from '@mui/material/RadioGroup';
import Typography from '@mui/material/Typography';

import SesionEstadoChip from '../data/SesionEstadoChip.jsx';
import EscalaLogro from '../evoluciones/EscalaLogro.jsx';
import { Cargando, EstadoError } from '../estado/index.js';
import ModalFormulario from '../modal/ModalFormulario.jsx';
import ListaRenglones, { CampoRenglon } from '../renglones/ListaRenglones.jsx';
import { usePeticion } from '../../hooks/usePeticion.js';
import {
  agregarRenglon, borrarRenglon, cerrarRenglon, editarRenglon, listarRenglones,
  marcarObjetivoDelPlan,
  MOMENTO_PLAN, MOMENTO_REGISTRO,
} from '../../services/renglonesService.js';
import {
  corregirEvolucion, etiquetaDeValor, quitarEvolucion, registrarEvolucion,
} from '../../services/evolucionesService.js';
import {
  editarSesion, estadoVisible, ESTADO_AUSENCIA, ESTADO_CORTADA, ETIQUETA_AUSENCIA_DE,
  OPCIONES_AUSENCIA_DE, obtenerSesion,
} from '../../services/sesionesService.js';
import { formatearFecha, formatearHora } from '../../utils/fechas.js';

// Deshacer una ausencia devuelve la sesión al estado de "asistida, todavía sin
// cerrar": el que tiene cualquier sesión agendada.
const ESTADO_SIN_CERRAR = 'incompleta';

function hoyIso() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function Bloque({ titulo, nota, contador, children }) {
  return (
    <Box sx={{ mb: 2.5 }}>
      <Box sx={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 1, mb: 0.5 }}>
        <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>{titulo}</Typography>
        {contador !== undefined && (
          <Typography variant="caption" color="text.secondary" className="tabular">{contador}</Typography>
        )}
      </Box>
      {nota && (
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.75 }}>{nota}</Typography>
      )}
      {children}
    </Box>
  );
}

// Una fila por objetivo: si ya tiene evolución se lee; si no, se despliega la
// escala de cinco palabras con observaciones opcionales y se guarda ahí mismo.
function FilaEvolucion({
  objetivo, evolucion, prefijo = null, planeado = false, habilitada, corregible = false, ocupado, onGuardar, onQuitar,
}) {
  const [abierta, setAbierta] = useState(false);
  const [valor, setValor] = useState('');
  const [observaciones, setObservaciones] = useState('');

  // Corregir abre la misma escala con lo ya guardado (usabilidad, terapeuta:
  // una calificación mal tocada no se podía arreglar).
  function abrirCorreccion() {
    setValor(String(evolucion.valor));
    setObservaciones(evolucion.observaciones ?? '');
    setAbierta(true);
  }
  const [error, setError] = useState('');
  const [guardando, setGuardando] = useState(false);

  async function guardar() {
    if (!valor) { setError('Elija cómo evolucionó el objetivo.'); return; }
    setError('');
    setGuardando(true);
    try {
      await onGuardar(Number(valor), observaciones.trim() || null);
      setAbierta(false);
    } catch (fallo) {
      setError(fallo.message || 'No se pudo guardar la evolución.');
    } finally {
      setGuardando(false);
    }
  }

  return (
    <Box component="li" sx={(t) => ({ py: 0.75, borderBottom: `1px solid ${t.palette.superficie.hundida}` })}>
      <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 0.5 }}>
        {prefijo}
        <Box className="texto-libre" sx={{ flex: 1, minWidth: 0, fontSize: 14, lineHeight: 1.4, py: prefijo ? 0.5 : 0, fontWeight: planeado ? 600 : 400 }}>
          {objetivo.descripcion}
        </Box>
        {evolucion ? (
          <Box sx={{ flex: 'none', display: 'flex', alignItems: 'center', gap: 1 }}>
            <Box sx={{ fontSize: 13, fontWeight: 600 }}>{etiquetaDeValor(evolucion.valor)}</Box>
            {corregible && !abierta && (
              <Button size="small" disabled={ocupado} onClick={abrirCorreccion}
                aria-label={`Corregir la calificación de: ${objetivo.descripcion}`}>
                Corregir
              </Button>
            )}
          </Box>
        ) : (
          habilitada && !abierta && (
            <Button size="small" variant="outlined" disabled={ocupado} onClick={() => setAbierta(true)}
              aria-label={`Calificar el objetivo: ${objetivo.descripcion}`}>
              Calificar
            </Button>
          )
        )}
      </Box>
      {evolucion?.observaciones && !abierta && (
        <Typography variant="caption" color="text.secondary" className="texto-libre" sx={{ display: 'block', mt: 0.25 }}>
          {evolucion.observaciones}
        </Typography>
      )}
      {abierta && (
        <Box sx={{ mt: 1 }}>
          <EscalaLogro valor={valor} onChange={setValor} deshabilitado={guardando} error={error && !valor ? error : undefined} />
          <TextField
            size="small" fullWidth multiline minRows={2} sx={{ mt: 1 }} label="Observaciones (opcional)"
            value={observaciones} onChange={(e) => setObservaciones(e.target.value)} disabled={guardando}
          />
          {error && valor && <Typography variant="caption" color="error">{error}</Typography>}
          <Box sx={{ display: 'flex', gap: 1, mt: 1 }}>
            <Button size="small" variant="contained" onClick={guardar} disabled={guardando}>
              {guardando ? 'Guardando…' : evolucion ? 'Guardar la corrección' : 'Guardar evolución'}
            </Button>
            <Button size="small" onClick={() => { setAbierta(false); setError(''); }} disabled={guardando}>Cancelar</Button>
            {evolucion && (
              <Button size="small" color="error" disabled={guardando} sx={{ ml: 'auto' }}
                onClick={async () => {
                  setGuardando(true);
                  try { await onQuitar(); setAbierta(false); } catch (fallo) { setError(fallo.message || 'No se pudo quitar.'); } finally { setGuardando(false); }
                }}>
                Quitar la calificación
              </Button>
            )}
          </Box>
        </Box>
      )}
    </Box>
  );
}

export default function ModalRegistroDia({
  abierto, idSesion, onCerrar, onCambio,
}) {
  const detalle = usePeticion(() => obtenerSesion(idSesion), [idSesion], { inmediata: Boolean(idSesion) });
  const renglones = usePeticion(() => listarRenglones(idSesion), [idSesion], { inmediata: Boolean(idSesion) });

  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState('');
  const [marcandoAusencia, setMarcandoAusencia] = useState(false);
  const [quienFalto, setQuienFalto] = useState('');
  // «Se cortó»: se carga trabajando una sesión sin registrar. La hora real de
  // fin es opcional y se guarda en hora_fin; el motivo no se guarda.
  const [cortando, setCortando] = useState(false);
  const [horaCorte, setHoraCorte] = useState('');

  const datos = detalle.datos;
  const sesion = datos?.sesion;
  const lista = renglones.datos;

  const esPropia = sesion?.es_propia !== false;
  const esAusencia = sesion?.estado === ESTADO_AUSENCIA;
  const esCortada = sesion?.estado === ESTADO_CORTADA;
  const futura = Boolean(sesion && sesion.fecha > hoyIso());
  const puedeEscribir = Boolean(sesion && esPropia);
  const puedeRegistrar = puedeEscribir && !esAusencia && !futura;
  const puedeCargarEvolucion = Boolean(
    puedeEscribir && !futura && sesion?.admite_evolucion && (datos?.objetivos_activos?.length ?? 0) > 0,
  );
  const evolucionPorObjetivo = new Map((datos?.evoluciones ?? []).map((e) => [e.id_objetivo, e]));
  // «Completa» (o «Se cortó») tiene que querer decir algo: terminada, se lee y
  // para cambiar algo se reabre (usabilidad, terapeuta: seguía todo editable).
  const terminada = Boolean(sesion && (esCortada || (sesion.estado === 'completa' && evolucionPorObjetivo.size > 0)));
  // Abierta: sin cerrar, o «completa» pero sin ninguna calificación (cargada
  // con el formato viejo): en ambos casos figura «Sin registrar».
  const abierta = Boolean(sesion && (sesion.estado === ESTADO_SIN_CERRAR || (sesion.estado === 'completa' && evolucionPorObjetivo.size === 0)));
  const editable = puedeEscribir && !terminada;
  const registrable = puedeRegistrar && !terminada;
  const calificable = puedeCargarEvolucion && !terminada;

  // Una acción sobre renglones o sesión: se ocupa la pantalla mientras corre,
  // se recarga lo que cambió y se avisa al panel. El error se dice acá.
  async function ejecutar(accion, { recargarSesion = false } = {}) {
    setError('');
    setOcupado(true);
    try {
      await accion();
      renglones.recargar();
      if (recargarSesion) detalle.recargar();
      onCambio?.();
    } catch (fallo) {
      setError(fallo.message || 'No se pudo completar la acción.');
      throw fallo;
    } finally {
      setOcupado(false);
    }
  }

  const agregar = (momento) => (texto, destacado) =>
    ejecutar(() => agregarRenglon(idSesion, { momento, texto, destacado }));
  const destacar = (r) => ejecutar(() => editarRenglon(r.id, { texto: r.texto, destacado: !r.destacado })).catch(() => {});
  const marcarObjetivo = (o, marcado) =>
    ejecutar(() => marcarObjetivoDelPlan(idSesion, o.id, marcado)).catch(() => {});
  const borrar = (r) => ejecutar(() => borrarRenglon(r.id)).catch(() => {});
  // Sin catch: si falla, la fila sigue en edición con el mensaje (T4.1).
  const editar = (r, texto) => ejecutar(() => editarRenglon(r.id, { texto, destacado: r.destacado }));
  const cerrar = (r, cierre) => ejecutar(() => cerrarRenglon(r.id, cierre)).catch(() => {});

  // "Ausente" y su deshacer pasan por el mismo editar de la sesión, con los
  // demás datos tal cual: el servidor aplica sus reglas (no se puede marcar
  // ausente con evolución ni registro escritos).
  async function cambiarAsistencia(estado, ausenciaDe, horaFin) {
    await ejecutar(() => editarSesion(sesion.id, {
      estado,
      ausencia_de: ausenciaDe,
      notas: sesion.notas ?? null,
      fecha: sesion.fecha,
      hora_inicio: sesion.hora_inicio?.slice(0, 5),
      hora_fin: horaFin ?? sesion.hora_fin?.slice(0, 5) ?? null,
    }), { recargarSesion: true });
    setMarcandoAusencia(false);
    setQuienFalto('');
    setCortando(false);
    setHoraCorte('');
  }

  // La hora de corte tiene que caer dentro de la sesión; si no, se avisa antes
  // de mandar nada. En duplas no se toca el horario: es compartido.
  const puedeFijarHoraCorte = Boolean(sesion && !sesion.companero);
  const inicioHHMM = sesion?.hora_inicio?.slice(0, 5) ?? '';
  const finHHMM = sesion?.hora_fin?.slice(0, 5) ?? '';
  const horaCorteInvalida = Boolean(
    horaCorte && (horaCorte <= inicioHHMM || (finHHMM && horaCorte > finHHMM)),
  );

  // Una sesión cerrada sin calificar (pendiente de antes de la V3) se reabre
  // sola al calificar: así sigue el ciclo Sin registrar -> Terminar, en vez de
  // saltar a «Completa» con la primera calificación.
  async function calificar(objetivo, valor, observaciones) {
    if (sesion.estado === 'completa' && evolucionPorObjetivo.size === 0) {
      await editarSesion(sesion.id, {
        estado: ESTADO_SIN_CERRAR,
        ausencia_de: null,
        notas: sesion.notas ?? null,
        fecha: sesion.fecha,
        hora_inicio: sesion.hora_inicio?.slice(0, 5),
        hora_fin: sesion.hora_fin?.slice(0, 5) ?? null,
      });
    }
    await registrarEvolucion({ id_sesion: sesion.id, id_objetivo: objetivo.id, valor, observaciones });
    // Calificar un objetivo es haberlo trabajado: se tilda solo en
    // «Objetivos a trabajar» (antes quedaba «0 de 3 marcados»).
    if (!lista.objetivos_plan.includes(objetivo.id)) {
      await marcarObjetivoDelPlan(sesion.id, objetivo.id, true).catch(() => {});
    }
  }

  const subtitulo = datos
    ? `${datos.paciente.nombre_completo} · ${formatearFecha(sesion.fecha)} · ${formatearHora(sesion.hora_inicio)}`
    : undefined;

  return (
    <ModalFormulario
      abierto={abierto}
      ancho={680}
      titulo="Registro del día"
      subtitulo={subtitulo}
      soloCerrar
      onPedirCierre={onCerrar}
      // La acción de terminar va al pie, siempre a la vista: antes aparecía en
      // el medio recién después de calificar y parecía que no había cómo guardar.
    >
      {(detalle.cargando || renglones.cargando) && !datos && <Cargando texto="Abriendo la sesión..." minHeight={140} />}
      {detalle.error && <EstadoError error={detalle.error} onReintentar={detalle.recargar} />}
      {renglones.error && <EstadoError error={renglones.error} onReintentar={renglones.recargar} />}

      {datos && lista && (
        <>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, flexWrap: 'wrap', mb: 2 }}>
            <SesionEstadoChip {...estadoVisible(sesion)} />
            <Typography variant="body2" color="text.secondary">
              Atendió {datos.terapeuta?.nombre_completo ?? 'un terapeuta del centro'}
              {esPropia ? '' : ' · otro terapeuta'}
            </Typography>
          </Box>

          {!esPropia && (
            <Alert severity="info" sx={{ mb: 2 }}>
              Es una sesión de otro terapeuta: puede consultarla, pero solo quien la atendió puede modificarla.
            </Alert>
          )}
          {esAusencia && (
            <Alert severity="info" sx={{ mb: 2 }}>
              <strong>Ausente{sesion.ausencia_de ? `: faltó ${ETIQUETA_AUSENCIA_DE[sesion.ausencia_de]}` : ''}.</strong>{' '}
              La sesión quedó cerrada: no se carga registro ni evolución. El plan que había
              escrito sigue pendiente y pasa a la próxima sesión.
            </Alert>
          )}
          {esCortada && (
            <Alert
              severity="warning" sx={{ mb: 2 }}
              action={puedeEscribir && (
                <Button color="inherit" size="small" disabled={ocupado} sx={{ whiteSpace: 'nowrap' }}
                  onClick={() => cambiarAsistencia(ESTADO_SIN_CERRAR, null).catch(() => {})}>
                  Reabrir el registro
                </Button>
              )}
            >
              <strong>Se cortó antes de tiempo{finHHMM ? `: terminó a las ${finHHMM}` : ''}.</strong>{' '}
              Lo que se alcanzó a trabajar queda registrado.
            </Alert>
          )}
          {terminada && puedeEscribir && !esCortada && (
            <Alert
              severity="success" sx={{ mb: 2 }}
              action={(
                <Button color="inherit" size="small" disabled={ocupado} sx={{ whiteSpace: 'nowrap' }}
                  onClick={() => cambiarAsistencia(ESTADO_SIN_CERRAR, null).catch(() => {})}>
                  Reabrir el registro
                </Button>
              )}
            >
              La sesión está terminada y se muestra como quedó. Para corregir una nota o una calificación,
              reabra el registro; lo escrito se conserva.
            </Alert>
          )}
          {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>{error}</Alert>}

          {!futura && (esAusencia || abierta) && puedeEscribir && (
            <Bloque
              titulo="¿Cómo fue la sesión?"
              nota={esAusencia ? undefined : 'Mientras no la cierre, figura «Sin registrar». Todo lo que cargue abajo se guarda al momento.'}
            >
          {cortando ? (
            <Box sx={(t) => ({ p: 1.5, mb: 1, borderRadius: `${t.formas.sm}px`, backgroundColor: t.palette.superficie.hundida })}>
              <Typography variant="body2" sx={{ fontWeight: 500, mb: 0.5 }}>
                La sesión se cortó antes de tiempo
              </Typography>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
                Queda cerrada como «Se cortó». Lo ya calificado y anotado se conserva.
              </Typography>
              {puedeFijarHoraCorte && (
                <TextField
                  type="time" size="small" label="Hora real de fin (opcional)"
                  value={horaCorte} onChange={(e) => setHoraCorte(e.target.value)}
                  disabled={ocupado} InputLabelProps={{ shrink: true }}
                  error={horaCorteInvalida}
                  helperText={horaCorteInvalida ? `Tiene que estar entre ${inicioHHMM} y ${finHHMM || 'el fin previsto'}.` : ' '}
                />
              )}
              <Box sx={{ display: 'flex', gap: 1, mt: 0.5 }}>
                <Button variant="contained" size="small" disabled={ocupado || horaCorteInvalida}
                  onClick={() => cambiarAsistencia(ESTADO_CORTADA, null, puedeFijarHoraCorte && horaCorte ? horaCorte : undefined).catch(() => {})}>
                  Confirmar «Se cortó»
                </Button>
                <Button size="small" disabled={ocupado} onClick={() => { setCortando(false); setHoraCorte(''); }}>
                  Cancelar
                </Button>
              </Box>
            </Box>
          ) : marcandoAusencia ? (
            <Box sx={(t) => ({ p: 1.5, mb: 1, borderRadius: `${t.formas.sm}px`, backgroundColor: t.palette.superficie.hundida })}>
              <Typography variant="body2" sx={{ fontWeight: 500, mb: 0.5 }}>¿Quién faltó?</Typography>
              <RadioGroup value={quienFalto} onChange={(e) => setQuienFalto(e.target.value)}>
                {OPCIONES_AUSENCIA_DE.map((o) => (
                  <FormControlLabel key={o.valor} value={o.valor} disabled={ocupado}
                    control={<Radio size="small" />} label={<Box component="span" sx={{ fontSize: 14 }}>{o.etiqueta}</Box>} />
                ))}
              </RadioGroup>
              <Box sx={{ display: 'flex', gap: 1, mt: 1 }}>
                <Button variant="contained" size="small" disabled={!quienFalto || ocupado}
                  onClick={() => cambiarAsistencia(ESTADO_AUSENCIA, quienFalto).catch(() => {})}>
                  Confirmar ausencia
                </Button>
                <Button size="small" disabled={ocupado} onClick={() => { setMarcandoAusencia(false); setQuienFalto(''); }}>
                  Cancelar
                </Button>
              </Box>
            </Box>
          ) : (
            puedeEscribir && (esAusencia || abierta) && (
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, alignItems: 'center' }}>
                {esAusencia ? (
                  <Button variant="outlined" disabled={ocupado}
                    onClick={() => cambiarAsistencia(ESTADO_SIN_CERRAR, null).catch(() => {})}>
                    Deshacer ausencia
                  </Button>
                ) : abierta && (
                  // Solo mientras la sesión está sin registrar: con la sesión ya
                  // cerrada no se ofrece (era fácil tocarlo sin querer).
                  <>
                    <Button variant="contained" disabled={ocupado || futura || evolucionPorObjetivo.size === 0}
                      onClick={() => cambiarAsistencia('completa', null).catch(() => {})}>
                      Completa
                    </Button>
                    <Button variant="outlined" disabled={ocupado || futura} onClick={() => setCortando(true)}>
                      Se cortó
                    </Button>
                    <Button variant="outlined" disabled={ocupado || futura} onClick={() => setMarcandoAusencia(true)}>
                      Marcar ausente
                    </Button>
                  </>
                )}
                {!esAusencia && !futura && evolucionPorObjetivo.size === 0 && (
                  <Typography variant="caption" color="text.secondary" sx={{ flexBasis: '100%' }}>
                    Para cerrarla como «Completa», califique al menos un objetivo. Si no se pudo trabajar, marque «Se cortó» o «Ausente».
                  </Typography>
                )}
              </Box>
            )
          )}
            </Bloque>
          )}

          {lista.arrastre.length > 0 && (
            <Bloque
              titulo="Pendiente de antes"
              contador={lista.arrastre.length}
              nota="Quedó sin cerrar en sesiones anteriores. Se sigue arrastrando hasta que se lo marque como hecho o se lo descarte."
            >
              <ListaRenglones
                renglones={lista.arrastre}
                editable={editable}
                conCierre
                ocupado={ocupado}
                onDestacar={destacar}
                onCerrar={cerrar}
              />
            </Bloque>
          )}

          <Bloque
            titulo="Objetivos de la sesión"
            contador={`${lista.objetivos_plan.length} marcados · ${evolucionPorObjetivo.size} calificados`}
            nota={futura
              ? 'Marque los que se van a trabajar. La calificación se carga cuando la sesión termine.'
              : (esAusencia
                ? 'Sesión cerrada por ausencia: no lleva evolución.'
                : (calificable ? 'Marque lo que se trabajó y califique cómo evolucionó cada objetivo. Los que no se trabajaron pueden quedar sin calificar.' : undefined))}
          >
            {datos.objetivos_activos.length === 0 && evolucionPorObjetivo.size === 0 ? (
              <Typography variant="body2" color="text.secondary" sx={{ fontStyle: 'italic', py: 0.5 }}>
                El paciente aún no tiene objetivos activos. Se cargan desde su ficha.
              </Typography>
            ) : (
              <Box component="ul" sx={{ listStyle: 'none', m: 0, p: 0 }}>
                {datos.evoluciones
                  .filter((e) => !datos.objetivos_activos.some((o) => o.id === e.id_objetivo))
                  .map((e) => (
                    <FilaEvolucion key={`ev-${e.id}`} objetivo={e.objetivo ?? { id: e.id_objetivo, descripcion: 'Objetivo archivado' }}
                      evolucion={e} habilitada={false} ocupado={ocupado} onGuardar={() => {}} />
                  ))}
                {datos.objetivos_activos.map((o) => {
                  const marcado = lista.objetivos_plan.includes(o.id);
                  const calificado = evolucionPorObjetivo.has(o.id);
                  return (
                    <FilaEvolucion
                      key={o.id}
                      objetivo={o}
                      evolucion={evolucionPorObjetivo.get(o.id)}
                      planeado={marcado}
                      prefijo={(
                        <Checkbox
                          size="small"
                          checked={marcado}
                          // Con calificación no se desmarca: quedaba «no trabajado» pero calificado.
                          disabled={!editable || ocupado || (marcado && calificado)}
                          title={marcado && calificado ? 'Tiene una calificación: para desmarcarlo, quite primero la calificación.' : undefined}
                          onChange={(e) => marcarObjetivo(o, e.target.checked)}
                          inputProps={{ 'aria-label': `Trabajar hoy: ${o.descripcion}` }}
                          sx={{ p: 0.5, mt: 0.25 }}
                        />
                      )}
                      habilitada={calificable}
                      corregible={calificable && sesion.estado === ESTADO_SIN_CERRAR}
                      ocupado={ocupado}
                      onGuardar={(valor, observaciones) => {
                        const ev = evolucionPorObjetivo.get(o.id);
                        return ejecutar(
                          () => (ev
                            ? corregirEvolucion(ev.id, { valor, observaciones })
                            : calificar(o, valor, observaciones)),
                          { recargarSesion: true },
                        );
                      }}
                      onQuitar={() => ejecutar(() => quitarEvolucion(evolucionPorObjetivo.get(o.id).id), { recargarSesion: true })}
                    />
                  );
                })}
              </Box>
            )}
          </Bloque>

          <Bloque titulo="Plan: otras actividades previstas" contador={lista.plan.length}>
            <ListaRenglones
              renglones={lista.plan}
              editable={editable}
              conCierre
              ocupado={ocupado}
              etiquetaVacio="Sin otras actividades previstas."
              onDestacar={destacar}
              onBorrar={borrar}
              onCerrar={cerrar}
              onEditar={editar}
              alPie={editable && (
                <CampoRenglon placeholder="Otra actividad prevista" onAgregar={agregar(MOMENTO_PLAN)} deshabilitado={ocupado} />
              )}
            />
          </Bloque>

          <Bloque
            titulo="Qué pasó en la sesión"
            contador={lista.registro.length}
            nota={futura ? 'La sesión todavía no ocurrió: por ahora solo admite plan.' : undefined}
          >
            <ListaRenglones
              renglones={lista.registro}
              editable={registrable}
              ocupado={ocupado}
              etiquetaVacio={esAusencia ? 'Sesión cerrada por ausencia: no hay registro.' : 'Todavía no se registró lo ocurrido en la sesión.'}
              onDestacar={destacar}
              onBorrar={borrar}
              onEditar={editar}
              alPie={registrable && (
                <CampoRenglon placeholder="Qué pasó en la sesión" onAgregar={agregar(MOMENTO_REGISTRO)} deshabilitado={ocupado} />
              )}
            />
          </Bloque>


          {sesion.notas && (
            <Bloque titulo="Notas escritas antes" nota="Cargadas con el formato anterior del sistema, en un solo texto.">
              <Typography variant="body2" className="texto-libre" sx={{ whiteSpace: 'pre-wrap' }}>{sesion.notas}</Typography>
            </Bloque>
          )}

        </>
      )}
    </ModalFormulario>
  );
}

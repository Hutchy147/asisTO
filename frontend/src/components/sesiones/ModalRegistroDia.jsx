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
import { etiquetaDeValor, registrarEvolucion } from '../../services/evolucionesService.js';
import {
  editarSesion, estadoVisible, ESTADO_AUSENCIA, ETIQUETA_AUSENCIA_DE,
  OPCIONES_AUSENCIA_DE, obtenerSesion,
} from '../../services/sesionesService.js';
import { formatearFecha } from '../../utils/fechas.js';

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
function FilaEvolucion({ objetivo, evolucion, planeado = false, habilitada, ocupado, onGuardar }) {
  const [abierta, setAbierta] = useState(false);
  const [valor, setValor] = useState('');
  const [observaciones, setObservaciones] = useState('');
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
      <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
        <Box className="texto-libre" sx={{ flex: 1, minWidth: 0, fontSize: 14, lineHeight: 1.4, fontWeight: planeado ? 600 : 400 }}>
          {objetivo.descripcion}
          {planeado && !evolucion && (
            <Box component="span" sx={{ ml: 1, fontSize: 11, fontWeight: 400, color: 'text.secondary' }}>planeado para hoy</Box>
          )}
        </Box>
        {evolucion ? (
          <Box sx={{ flex: 'none', fontSize: 13, fontWeight: 600 }}>{etiquetaDeValor(evolucion.valor)}</Box>
        ) : (
          habilitada && !abierta && (
            <Button size="small" variant="outlined" disabled={ocupado} onClick={() => setAbierta(true)}
              aria-label={`Calificar el objetivo: ${objetivo.descripcion}`}>
              Calificar
            </Button>
          )
        )}
      </Box>
      {evolucion?.observaciones && (
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
              {guardando ? 'Guardando…' : 'Guardar evolución'}
            </Button>
            <Button size="small" onClick={() => { setAbierta(false); setError(''); }} disabled={guardando}>Cancelar</Button>
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

  const datos = detalle.datos;
  const sesion = datos?.sesion;
  const lista = renglones.datos;

  const esPropia = sesion?.es_propia !== false;
  const esAusencia = sesion?.estado === ESTADO_AUSENCIA;
  const futura = Boolean(sesion && sesion.fecha > hoyIso());
  const puedeEscribir = Boolean(sesion && esPropia);
  const puedeRegistrar = puedeEscribir && !esAusencia && !futura;
  const puedeCargarEvolucion = Boolean(
    puedeEscribir && !futura && sesion?.admite_evolucion && (datos?.objetivos_activos?.length ?? 0) > 0,
  );
  const evolucionPorObjetivo = new Map((datos?.evoluciones ?? []).map((e) => [e.id_objetivo, e]));

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
  async function cambiarAsistencia(estado, ausenciaDe) {
    await ejecutar(() => editarSesion(sesion.id, {
      estado,
      ausencia_de: ausenciaDe,
      notas: sesion.notas ?? null,
      fecha: sesion.fecha,
      hora_inicio: sesion.hora_inicio?.slice(0, 5),
      hora_fin: sesion.hora_fin?.slice(0, 5) ?? null,
    }), { recargarSesion: true });
    setMarcandoAusencia(false);
    setQuienFalto('');
  }

  const subtitulo = datos
    ? `${datos.paciente.nombre_completo} · ${formatearFecha(sesion.fecha)} · ${sesion.hora_inicio?.slice(0, 5)}`
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
      accionPie={datos && lista && puedeRegistrar && !esAusencia && sesion.estado === ESTADO_SIN_CERRAR && (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, flex: 1, flexWrap: 'wrap' }}>
          <Typography variant="caption" color="text.secondary" sx={{ flex: 1, minWidth: 180 }}>
            {evolucionPorObjetivo.size > 0
              ? 'Todo lo escrito ya quedó guardado. Al terminar, la sesión figura «Realizada».'
              : 'Todo se guarda al momento. Para terminar, califique al menos un objetivo.'}
          </Typography>
          <Button variant="contained" disabled={ocupado || evolucionPorObjetivo.size === 0}
            onClick={() => cambiarAsistencia('completa', null).catch(() => {})}>
            Terminar la sesión
          </Button>
        </Box>
      )}
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
          {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>{error}</Alert>}

          {lista.arrastre.length > 0 && (
            <Bloque
              titulo="Pendiente de antes"
              contador={lista.arrastre.length}
              nota="Quedó sin cerrar en sesiones anteriores. Se sigue arrastrando hasta que se lo marque como hecho o se lo descarte."
            >
              <ListaRenglones
                renglones={lista.arrastre}
                editable={puedeEscribir}
                conCierre
                ocupado={ocupado}
                onDestacar={destacar}
                onCerrar={cerrar}
              />
            </Bloque>
          )}

          <Bloque
            titulo="Objetivos a trabajar"
            contador={`${lista.objetivos_plan.length} de ${datos.objetivos_activos.length} marcados`}
            nota={puedeEscribir ? 'Los objetivos activos del paciente. Marque los que se trabajarán en esta sesión.' : undefined}
          >
            {datos.objetivos_activos.length === 0 ? (
              <Typography variant="body2" color="text.secondary" sx={{ fontStyle: 'italic', py: 0.5 }}>
                El paciente aún no tiene objetivos activos. Se cargan desde su ficha.
              </Typography>
            ) : (
              <Box component="ul" sx={{ listStyle: 'none', m: 0, p: 0 }}>
                {datos.objetivos_activos.map((o) => {
                  const marcado = lista.objetivos_plan.includes(o.id);
                  return (
                    <Box
                      component="li"
                      key={o.id}
                      sx={(t) => ({
                        display: 'flex', alignItems: 'flex-start', gap: 0.5, py: 0.25,
                        borderBottom: `1px solid ${t.palette.superficie.hundida}`,
                      })}
                    >
                      <Checkbox
                        size="small"
                        checked={marcado}
                        disabled={!puedeEscribir || ocupado}
                        onChange={(e) => marcarObjetivo(o, e.target.checked)}
                        inputProps={{ 'aria-label': `Trabajar hoy: ${o.descripcion}` }}
                        sx={{ p: 0.5, mt: 0.25 }}
                      />
                      <Box className="texto-libre" sx={{ flex: 1, minWidth: 0, fontSize: 14, lineHeight: 1.4, py: 0.5, fontWeight: marcado ? 600 : 400 }}>
                        {o.descripcion}
                      </Box>
                    </Box>
                  );
                })}
              </Box>
            )}
          </Bloque>

          <Bloque titulo="Otras notas del plan" contador={lista.plan.length}>
            <ListaRenglones
              renglones={lista.plan}
              editable={puedeEscribir}
              conCierre
              ocupado={ocupado}
              etiquetaVacio="Sin otras notas."
              onDestacar={destacar}
              onBorrar={borrar}
              onCerrar={cerrar}
              onEditar={editar}
              alPie={puedeEscribir && (
                <CampoRenglon placeholder="Otra actividad prevista" onAgregar={agregar(MOMENTO_PLAN)} deshabilitado={ocupado} />
              )}
            />
          </Bloque>

          <Bloque
            titulo="Registro"
            contador={lista.registro.length}
            nota={futura ? 'La sesión todavía no ocurrió: por ahora solo admite plan.' : undefined}
          >
            <ListaRenglones
              renglones={lista.registro}
              editable={puedeRegistrar}
              ocupado={ocupado}
              etiquetaVacio={esAusencia ? 'Sesión cerrada por ausencia: no hay registro.' : 'Todavía no se registró lo ocurrido en la sesión.'}
              onDestacar={destacar}
              onBorrar={borrar}
              onEditar={editar}
              alPie={puedeRegistrar && (
                <CampoRenglon placeholder="Qué pasó en la sesión" onAgregar={agregar(MOMENTO_REGISTRO)} deshabilitado={ocupado} />
              )}
            />
          </Bloque>

          <Bloque
            titulo="Evolución por objetivo"
            contador={`${evolucionPorObjetivo.size} de ${datos.objetivos_activos.length + [...evolucionPorObjetivo.keys()].filter((id) => !datos.objetivos_activos.some((o) => o.id === id)).length} calificados`}
            nota={puedeCargarEvolucion ? 'Califique cómo evolucionó cada objetivo trabajado. Los que no se trabajaron pueden quedar sin calificar.' : undefined}
          >
            {esAusencia ? (
              <Typography variant="body2" color="text.secondary" sx={{ fontStyle: 'italic' }}>
                Sesión cerrada por ausencia: no lleva evolución.
              </Typography>
            ) : futura ? (
              <Typography variant="body2" color="text.secondary" sx={{ fontStyle: 'italic' }}>
                La sesión todavía no ocurrió: la evolución se carga cuando termine.
              </Typography>
            ) : datos.objetivos_activos.length === 0 && evolucionPorObjetivo.size === 0 ? (
              <Typography variant="body2" color="text.secondary" sx={{ fontStyle: 'italic' }}>
                El paciente no tiene objetivos activos.
              </Typography>
            ) : (
              <Box component="ul" sx={{ listStyle: 'none', m: 0, p: 0 }}>
                {datos.evoluciones
                  .filter((e) => !datos.objetivos_activos.some((o) => o.id === e.id_objetivo))
                  .map((e) => (
                    <FilaEvolucion key={`ev-${e.id}`} objetivo={e.objetivo ?? { id: e.id_objetivo, descripcion: 'Objetivo archivado' }}
                      evolucion={e} habilitada={false} ocupado={ocupado} onGuardar={() => {}} />
                  ))}
                {datos.objetivos_activos.map((o) => (
                  <FilaEvolucion
                    key={o.id}
                    objetivo={o}
                    evolucion={evolucionPorObjetivo.get(o.id)}
                    planeado={lista.objetivos_plan.includes(o.id)}
                    habilitada={puedeCargarEvolucion}
                    ocupado={ocupado}
                    onGuardar={(valor, observaciones) => ejecutar(
                      async () => {
                        await registrarEvolucion({ id_sesion: sesion.id, id_objetivo: o.id, valor, observaciones });
                        // Calificar un objetivo es haberlo trabajado: se tilda solo en
                        // «Objetivos a trabajar» (antes quedaba «0 de 3 marcados»).
                        if (!lista.objetivos_plan.includes(o.id)) {
                          await marcarObjetivoDelPlan(sesion.id, o.id, true).catch(() => {});
                        }
                      },
                      { recargarSesion: true },
                    )}
                  />
                ))}
              </Box>
            )}
            {puedeRegistrar && evolucionPorObjetivo.size > 0 && (
              <Box sx={{ pt: 1.25, display: 'flex', alignItems: 'center', gap: 1.5, flexWrap: 'wrap' }}>
                {sesion.estado === ESTADO_SIN_CERRAR ? (
                  <>
                    <Typography variant="caption" color="text.secondary">
                      Mientras no se termine (botón «Terminar la sesión», al pie), la sesión figura «En registro».
                    </Typography>
                  </>
                ) : (
                  <>
                    <Button size="small" variant="text" disabled={ocupado}
                      onClick={() => cambiarAsistencia(ESTADO_SIN_CERRAR, null).catch(() => {})}>
                      Reabrir el registro
                    </Button>
                    {/* H11: qué hace reabrir, dicho antes de tocarlo. */}
                    <Typography variant="caption" color="text.secondary">
                      Vuelve a «En registro» para corregir; las calificaciones y los renglones se conservan.
                    </Typography>
                  </>
                )}
              </Box>
            )}
          </Bloque>

          {sesion.notas && (
            <Bloque titulo="Notas escritas antes" nota="Cargadas con el formato anterior del sistema, en un solo texto.">
              <Typography variant="body2" className="texto-libre" sx={{ whiteSpace: 'pre-wrap' }}>{sesion.notas}</Typography>
            </Bloque>
          )}

          {marcandoAusencia ? (
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
            puedeEscribir && (
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, pt: 0.5 }}>
                {esAusencia ? (
                  <Button variant="outlined" disabled={ocupado}
                    onClick={() => cambiarAsistencia(ESTADO_SIN_CERRAR, null).catch(() => {})}>
                    Deshacer ausencia
                  </Button>
                ) : sesion.estado !== 'completa' && (
                  // Con la sesión ya realizada no se ofrece: era fácil tocarlo sin querer.
                  <Button variant="outlined" disabled={ocupado || futura} onClick={() => setMarcandoAusencia(true)}>
                    Marcar ausente
                  </Button>
                )}
              </Box>
            )
          )}
        </>
      )}
    </ModalFormulario>
  );
}

// frontend/src/components/sesiones/ModalRegistroDia.jsx
// Registro del día de UNA sesión (Entrega 3): plan y registro son el mismo
// objeto en dos momentos, como la página del cuaderno que se escribe antes y
// se anota encima después.
//
//   Pendiente de antes  lo que quedó sin cerrar en sesiones anteriores del
//                       mismo paciente (se arrastra hasta cerrarlo).
//   Plan                lo que se piensa hacer; se puede escribir antes y después.
//   Registro            lo que pasó; solo si la sesión ya ocurrió y no fue ausencia.
//
// "Ausente" CIERRA la sesión: no se carga registro ni evolución. El plan
// queda y pasa a la próxima sesión del paciente.

import { useState } from 'react';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import FormControlLabel from '@mui/material/FormControlLabel';
import Radio from '@mui/material/Radio';
import RadioGroup from '@mui/material/RadioGroup';
import Typography from '@mui/material/Typography';

import SesionEstadoChip from '../data/SesionEstadoChip.jsx';
import { Cargando, EstadoError } from '../estado/index.js';
import ModalFormulario from '../modal/ModalFormulario.jsx';
import ListaRenglones, { CampoRenglon } from '../renglones/ListaRenglones.jsx';
import { usePeticion } from '../../hooks/usePeticion.js';
import {
  agregarRenglon, borrarRenglon, cerrarRenglon, editarRenglon, listarRenglones,
  MOMENTO_PLAN, MOMENTO_REGISTRO,
} from '../../services/renglonesService.js';
import {
  editarSesion, ESTADO_AUSENCIA, ETIQUETA_AUSENCIA_DE,
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

export default function ModalRegistroDia({
  abierto, idSesion, onCerrar, onCambio, onCargarEvolucion,
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
    onCargarEvolucion && puedeEscribir && sesion?.admite_evolucion && (datos?.objetivos_activos?.length ?? 0) > 0,
  );

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
  const borrar = (r) => ejecutar(() => borrarRenglon(r.id)).catch(() => {});
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
    >
      {(detalle.cargando || renglones.cargando) && !datos && <Cargando texto="Abriendo la sesión..." minHeight={140} />}
      {detalle.error && <EstadoError error={detalle.error} onReintentar={detalle.recargar} />}
      {renglones.error && <EstadoError error={renglones.error} onReintentar={renglones.recargar} />}

      {datos && lista && (
        <>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, flexWrap: 'wrap', mb: 2 }}>
            <SesionEstadoChip estado={sesion.estado} />
            <Typography variant="body2" color="text.secondary">
              Atendió {datos.terapeuta?.nombre_completo ?? 'un terapeuta del centro'}
              {esPropia ? '' : ' · otro terapeuta'}
            </Typography>
          </Box>

          {!esPropia && (
            <Alert severity="info" sx={{ mb: 2 }}>
              Es una sesión de otro terapeuta: la podés leer, pero solo quien la atendió escribe en ella.
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
              nota="Quedó sin cerrar en sesiones anteriores. Se sigue arrastrando hasta que lo marques como hecho o lo descartes."
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

          <Bloque titulo="Plan" contador={lista.plan.length}>
            <ListaRenglones
              renglones={lista.plan}
              editable={puedeEscribir}
              conCierre
              ocupado={ocupado}
              etiquetaVacio="Todavía no escribiste qué pensás trabajar."
              onDestacar={destacar}
              onBorrar={borrar}
              onCerrar={cerrar}
              alPie={puedeEscribir && (
                <CampoRenglon placeholder="Qué pensás trabajar" onAgregar={agregar(MOMENTO_PLAN)} deshabilitado={ocupado} />
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
              etiquetaVacio={esAusencia ? 'Sesión cerrada por ausencia: no hay registro.' : 'Todavía no anotaste qué pasó.'}
              onDestacar={destacar}
              onBorrar={borrar}
              alPie={puedeRegistrar && (
                <CampoRenglon placeholder="Qué pasó en la sesión" onAgregar={agregar(MOMENTO_REGISTRO)} deshabilitado={ocupado} />
              )}
            />
          </Bloque>

          {sesion.notas && (
            <Bloque titulo="Notas anteriores" nota="Texto libre cargado antes de que existieran los renglones.">
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
                {puedeCargarEvolucion && (
                  <Button variant="contained" onClick={() => onCargarEvolucion(sesion.id)} disabled={ocupado}>
                    Cargar evolución
                  </Button>
                )}
                {esAusencia ? (
                  <Button variant="outlined" disabled={ocupado}
                    onClick={() => cambiarAsistencia(ESTADO_SIN_CERRAR, null).catch(() => {})}>
                    Deshacer ausencia
                  </Button>
                ) : (
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

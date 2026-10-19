// frontend/src/pages/CalendarioSemanal.jsx
// Calendario del terapeuta (Entrega 3): una SEMANA TIPO, de lunes a viernes.
// El trabajo es semanal y los pacientes se repiten: un turno cargado el lunes
// a las 8 vale para todos los lunes a las 8. Por eso el calendario muestra los
// turnos fijos y no los días sueltos.
//
// Las sesiones de cada día se agendan solas a partir de los turnos: al
// agregar un turno y al abrir esta pantalla se completan las próximas
// semanas (la operación es idempotente: lo que ya existe no se duplica). El
// registro de lo ocurrido se hace desde el Panel del día.

import { useEffect, useMemo, useState } from 'react';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import MenuItem from '@mui/material/MenuItem';
import Snackbar from '@mui/material/Snackbar';
import Typography from '@mui/material/Typography';
import { useNavigate } from 'react-router-dom';

import AppLayout from '../components/layout/AppLayout.jsx';
import CampoTexto from '../components/forms/CampoTexto.jsx';
import { Cargando, EstadoError } from '../components/estado/index.js';
import { usePeticion } from '../hooks/usePeticion.js';
import { hayCapacidad } from '../config/entregas.js';
import {
  crearTurno, DIAS_SEMANA, generarAgenda, listarAgendaSemanal, quitarTurno,
  SEMANAS_POR_DEFECTO, sumarCompanero,
} from '../services/agendaRecurrenteService.js';
import { listarPacientes } from '../services/pacientesService.js';

// Rango por omisión de la grilla; se amplía si hay un turno fuera de él.
const HORA_INICIO_BASE = 8;
const HORA_FIN_BASE = 19;
const ALTO_HORA = 56;
const ANCHO_GUTTER = 62;

function aDecimal(hora) {
  const [h, m] = hora.split(':').map(Number);
  return h + m / 60;
}

const hh = (n) => `${String(n).padStart(2, '0')}:00`;

function BloqueTurno({ turno, onAbrir, horaInicio }) {
  const inicio = aDecimal(turno.hora_inicio);
  const fin = aDecimal(turno.hora_fin);
  // Un turno de menos de una hora ocupa poco alto: nombre y horario van en una línea.
  const compacto = fin - inicio < 1;
  const enDupla = Boolean(turno.companero);
  const nombres = enDupla ? `${turno.paciente} y ${turno.companero.paciente}` : turno.paciente;
  return (
    <Box
      component="button"
      type="button"
      onClick={(e) => { e.stopPropagation(); onAbrir(turno); }}
      title={`${nombres} · ${turno.hora_inicio.slice(0, 5)} a ${turno.hora_fin.slice(0, 5)}`}
      aria-label={`Turno del ${turno.dia} a las ${turno.hora_inicio.slice(0, 5)}: ${nombres}`}
      sx={(t) => ({
        position: 'absolute', left: 5, right: 5,
        top: (inicio - horaInicio) * ALTO_HORA + 3,
        height: Math.max(0.5, fin - inicio) * ALTO_HORA - 6,
        backgroundColor: t.palette.sesionEstado.completa.bg,
        border: '1px solid transparent',
        borderLeft: `3px solid ${t.palette.sesionEstado.completa.fg}`,
        borderRadius: '6px', padding: compacto ? '0 8px' : '5px 8px', textAlign: 'left',
        cursor: 'pointer', font: 'inherit', color: t.palette.text.primary,
        display: 'flex', flexDirection: compacto && !enDupla ? 'row' : 'column',
        justifyContent: 'center',
        alignItems: compacto && !enDupla ? 'center' : 'stretch', gap: compacto ? '8px' : '1px', overflow: 'hidden',
        '&:focus-visible': { outline: 'none', boxShadow: t.foco.anillo },
      })}
    >
      <Box component="span" sx={{ fontSize: 12.5, fontWeight: 600, lineHeight: 1.2, overflow: 'hidden', textOverflow: 'ellipsis', minWidth: 0,
        ...(enDupla
          ? { display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', whiteSpace: 'normal' }
          : { whiteSpace: 'nowrap' }) }}>
        {nombres}
      </Box>
      {!(enDupla && compacto) && (
      <Box component="span" className="tabular" sx={{ fontSize: 11, color: 'text.secondary', whiteSpace: 'nowrap', flex: 'none' }}>
        {turno.hora_inicio.slice(0, 5)} a {turno.hora_fin.slice(0, 5)}
      </Box>
      )}
    </Box>
  );
}

function DialogoNuevoTurno({ base, pacientes, onCerrar, onGuardar }) {
  const [paciente, setPaciente] = useState('');
  const [companero, setCompanero] = useState('');
  const [dia, setDia] = useState(base.dia);
  const [inicio, setInicio] = useState(base.hora);
  const [fin, setFin] = useState('');
  const [error, setError] = useState('');
  const [campo, setCampo] = useState('');
  const [ocupado, setOcupado] = useState(false);

  async function guardar() {
    if (!paciente || !inicio) {
      setError('Elija el paciente y la hora de inicio.');
      return;
    }
    setError(''); setCampo(''); setOcupado(true);
    try {
      await onGuardar({
        id_paciente: Number(paciente),
        id_paciente_2: companero ? Number(companero) : null,
        dia_semana: Number(dia), hora_inicio: inicio, hora_fin: fin || null,
      });
    } catch (fallo) {
      setError(fallo.message || 'No se pudo guardar el turno.');
      setCampo(fallo.campo || '');
      setOcupado(false);
    }
  }

  return (
    <Dialog open onClose={ocupado ? undefined : onCerrar} PaperProps={{ sx: { width: 460, maxWidth: '95vw' } }}>
      <Box sx={{ px: 3, pt: 2.5 }}>
        <Typography variant="h5">Nuevo turno semanal</Typography>
        <Typography variant="body2" color="text.secondary">
          Se repite todas las semanas, el mismo día y a la misma hora.
        </Typography>
      </Box>
      <DialogContent sx={{ px: 3, py: 2 }}>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        <Box sx={{ display: 'grid', gap: 1.5 }}>
          <CampoTexto id="turno-paciente" etiqueta="Paciente" select valor={paciente}
            onChange={(e) => setPaciente(e?.target?.value ?? e)} deshabilitado={ocupado}
            error={campo === 'id_paciente' ? ' ' : undefined}
            ayuda={pacientes.length === 0 ? 'No tiene pacientes asignados.' : undefined}>
            {pacientes.map((p) => (
              <MenuItem key={p.id} value={p.id} className="texto-libre">{p.nombre_completo} · {p.nro_historia}</MenuItem>
            ))}
          </CampoTexto>
          {hayCapacidad('duplas.vincular') && (
            <CampoTexto id="turno-companero" etiqueta="Compañero de dupla" select valor={companero}
              onChange={(e) => setCompanero(e?.target?.value ?? e)} deshabilitado={ocupado}
              ayuda="Opcional. Dos pacientes que usted atiende juntos en el mismo horario."
              error={campo === 'id_paciente_2' ? ' ' : undefined}>
              <MenuItem value="">Ninguno (turno individual)</MenuItem>
              {pacientes.filter((p) => p.id !== Number(paciente)).map((p) => (
                <MenuItem key={p.id} value={p.id} className="texto-libre">{p.nombre_completo} · {p.nro_historia}</MenuItem>
              ))}
            </CampoTexto>
          )}
          <CampoTexto id="turno-dia" etiqueta="Día" select valor={dia}
            onChange={(e) => setDia(e?.target?.value ?? e)} deshabilitado={ocupado}>
            {DIAS_SEMANA.map((d) => <MenuItem key={d.valor} value={d.valor}>{d.etiqueta}</MenuItem>)}
          </CampoTexto>
          <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1.5 }}>
            <CampoTexto id="turno-inicio" etiqueta="Hora de inicio" tipo="time" tabular valor={inicio}
              onChange={(e) => setInicio(e?.target?.value ?? e)} deshabilitado={ocupado}
              error={campo === 'hora_inicio' ? ' ' : undefined} />
            <CampoTexto id="turno-fin" etiqueta="Hora de fin" tipo="time" tabular valor={fin}
              ayuda="Opcional: 45 minutos si se deja vacía." onChange={(e) => setFin(e?.target?.value ?? e)}
              deshabilitado={ocupado} error={campo === 'hora_fin' ? ' ' : undefined} />
          </Box>
        </Box>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2.5, gap: 1 }}>
        <Button variant="outlined" onClick={onCerrar} disabled={ocupado}>Cancelar</Button>
        <Button variant="contained" onClick={guardar} disabled={ocupado}>
          {ocupado ? 'Guardando…' : 'Guardar turno'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

function DialogoTurno({ turno, pacientes, onCerrar, onVerPaciente, onQuitar, onSumar }) {
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState('');
  const [nuevoCompanero, setNuevoCompanero] = useState('');
  const enDupla = Boolean(turno.companero);
  const puedeSumar = hayCapacidad('duplas.vincular') && !enDupla;

  async function sumar() {
    if (!nuevoCompanero) { setError('Elija el compañero de dupla.'); return; }
    setOcupado(true); setError('');
    try {
      await onSumar(turno, Number(nuevoCompanero));
    } catch (fallo) {
      setError(fallo.message || 'No se pudo formar la dupla.');
      setOcupado(false);
    }
  }

  async function quitar(dupla = false) {
    setOcupado(true); setError('');
    try {
      await onQuitar(turno, dupla);
    } catch (fallo) {
      setError(fallo.message || 'No se pudo quitar el turno.');
      setOcupado(false);
    }
  }

  return (
    <Dialog open onClose={ocupado ? undefined : onCerrar} PaperProps={{ sx: { width: 440, maxWidth: '95vw' } }}>
      <Box sx={{ px: 3, pt: 2.5 }}>
        <Typography variant="h5" className="texto-libre">
          {enDupla ? `${turno.paciente} y ${turno.companero.paciente}` : turno.paciente}
        </Typography>
        <Typography variant="body2" color="text.secondary" className="tabular">
          Todos los {turno.dia.toLowerCase()} de {turno.hora_inicio.slice(0, 5)} a {turno.hora_fin.slice(0, 5)}
        </Typography>
      </Box>
      <DialogContent sx={{ px: 3, py: 2 }}>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        {enDupla && (
          <Alert severity="info" sx={{ mb: 2 }}>
            Dupla terapéutica: usted atiende a los dos pacientes en este horario.
            Cada paciente conserva su propia evolución.
          </Alert>
        )}
        {puedeSumar && (
          <Box sx={{ mb: 2, display: 'grid', gap: 1 }}>
            <CampoTexto id="turno-sumar-companero" etiqueta="Agregar compañero de dupla" select
              valor={nuevoCompanero} onChange={(e) => setNuevoCompanero(e?.target?.value ?? e)}
              deshabilitado={ocupado}>
              {pacientes.filter((p) => p.id !== turno.id_paciente).map((p) => (
                <MenuItem key={p.id} value={p.id} className="texto-libre">{p.nombre_completo} · {p.nro_historia}</MenuItem>
              ))}
            </CampoTexto>
            <Box><Button variant="outlined" onClick={sumar} disabled={ocupado}>Formar dupla</Button></Box>
          </Box>
        )}
        <Typography variant="body2" color="text.secondary">
          Al quitar el turno dejan de generarse sesiones nuevas. Las sesiones ya agendadas
          y los registros existentes se conservan.
        </Typography>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2.5, gap: 1 }}>
        <Button variant="outlined" onClick={onCerrar} disabled={ocupado}>Cerrar</Button>
        <Button variant="outlined" onClick={() => onVerPaciente(turno.id_paciente)} disabled={ocupado}>
          Ver paciente
        </Button>
        {enDupla ? (
          <>
            <Button variant="outlined" onClick={() => quitar(false)} disabled={ocupado}>
              {`Quitar solo a ${turno.paciente}`}
            </Button>
            <Button variant="contained" onClick={() => quitar(true)} disabled={ocupado}>
              {ocupado ? 'Quitando…' : 'Quitar la dupla'}
            </Button>
          </>
        ) : (
          <Button variant="contained" onClick={() => quitar(false)} disabled={ocupado}>
            {ocupado ? 'Quitando…' : 'Quitar turno'}
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
}

export default function CalendarioSemanal() {
  const navigate = useNavigate();
  const agenda = usePeticion(listarAgendaSemanal, []);
  const pacientes = usePeticion(listarPacientes, []);
  const [nuevo, setNuevo] = useState(null);      // null | { dia, hora }
  const [abierto, setAbierto] = useState(null);  // null | turno
  const [aviso, setAviso] = useState('');

  const turnos = agenda.datos?.plantillas ?? [];
  // Una dupla se dibuja una sola vez: con el turno de menor id de la pareja.
  const visibles = turnos.filter((t) => !t.companero || t.id < t.companero.id_turno);
  const HORA_INICIO = Math.min(HORA_INICIO_BASE, ...turnos.map((t) => Math.floor(aDecimal(t.hora_inicio))));
  const HORA_FIN = Math.max(HORA_FIN_BASE, ...turnos.map((t) => Math.ceil(aDecimal(t.hora_fin))));
  const HORAS = Array.from({ length: HORA_FIN - HORA_INICIO }, (_, i) => HORA_INICIO + i);
  const asignados = useMemo(
    () => (pacientes.datos?.pacientes ?? []).filter((p) => p.asignado_a_mi !== false),
    [pacientes.datos],
  );

  // Mantiene la agenda agendada hacia adelante sin que el terapeuta tenga que
  // pedirlo: idempotente, no duplica lo que ya existe.
  useEffect(() => {
    if (turnos.length > 0) generarAgenda(SEMANAS_POR_DEFECTO).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [turnos.length]);

  async function guardar(datos) {
    await crearTurno(datos);
    const r = await generarAgenda(SEMANAS_POR_DEFECTO).catch(() => null);
    setNuevo(null);
    agenda.recargar();
    setAviso(
      r && r.omitidas?.length
        ? `Turno guardado. ${r.omitidas.length} sesión(es) no pudieron agendarse por superposición con otro profesional o por el estado del paciente.`
        : 'Turno guardado. Las sesiones de las próximas semanas quedaron agendadas.',
    );
  }

  async function quitar(turno, dupla = false) {
    await quitarTurno(turno.id, { dupla });
    setAbierto(null);
    agenda.recargar();
    setAviso(
      turno.companero && !dupla
        ? `Se quitó el turno de ${turno.paciente}. ${turno.companero.paciente} conserva el horario como turno individual.`
        : 'Turno quitado. No se generarán sesiones nuevas para ese horario.',
    );
  }

  async function sumar(turno, idPaciente) {
    await sumarCompanero(turno.id, idPaciente);
    const r = await generarAgenda(SEMANAS_POR_DEFECTO).catch(() => null);
    setAbierto(null);
    agenda.recargar();
    setAviso(
      r && r.omitidas?.length
        ? `Dupla formada. ${r.omitidas.length} sesión(es) no pudieron agendarse por superposición o por el estado del paciente.`
        : 'Dupla formada. Las sesiones de las próximas semanas quedaron agendadas.',
    );
  }

  return (
    <AppLayout
      titulo="Calendario"
      subtitulo={`Semana tipo, de lunes a viernes${agenda.datos ? ` · ${visibles.length} ${visibles.length === 1 ? 'turno' : 'turnos'}` : ''}`}
      acciones={<Button variant="contained" onClick={() => setNuevo({ dia: 1, hora: '' })}>Nuevo turno</Button>}
    >
      {agenda.cargando && !agenda.datos && <Cargando texto="Cargando la agenda..." />}
      {agenda.error && <EstadoError error={agenda.error} onReintentar={agenda.recargar} />}

      {agenda.datos && (
        <>
          {turnos.length === 0 && (
            <Alert severity="info" sx={{ mb: 2 }}>
              Todavía no hay turnos. Seleccione un horario de la grilla, o use «Nuevo turno»,
              para cargar un paciente que se atiende todas las semanas en ese día y hora.
            </Alert>
          )}
          <Box sx={(t) => ({ border: `1px solid ${t.palette.divider}`, borderRadius: '10px', overflowX: 'auto', backgroundColor: t.palette.background.paper })}>
            <Box sx={{ minWidth: 820 }}>
              <Box sx={(t) => ({ display: 'grid', gridTemplateColumns: `${ANCHO_GUTTER}px repeat(5, 1fr)`, borderBottom: `1px solid ${t.palette.divider}` })}>
                <Box />
                {DIAS_SEMANA.map((d) => (
                  <Box key={d.valor} sx={{ py: 1, textAlign: 'center', fontSize: 13, fontWeight: 600 }}>{d.etiqueta}</Box>
                ))}
              </Box>
              <Box sx={{ display: 'grid', gridTemplateColumns: `${ANCHO_GUTTER}px repeat(5, 1fr)` }}>
                <Box>
                  {HORAS.map((h) => (
                    <Box key={h} className="tabular" sx={{ height: ALTO_HORA, pr: 1, pt: 0.5, textAlign: 'right', fontSize: 11, color: 'text.secondary' }}>
                      {hh(h)}
                    </Box>
                  ))}
                </Box>
                {DIAS_SEMANA.map((d) => (
                  <Box key={d.valor} sx={(t) => ({ position: 'relative', borderLeft: `1px solid ${t.palette.divider}` })}>
                    {HORAS.map((h) => (
                      <Box
                        key={h}
                        component="button"
                        type="button"
                        aria-label={`Agregar un turno el ${d.etiqueta} a las ${hh(h)}`}
                        onClick={() => setNuevo({ dia: d.valor, hora: hh(h) })}
                        sx={(t) => ({
                          display: 'block', width: '100%', height: ALTO_HORA, p: 0, border: 0,
                          borderBottom: `1px solid ${t.palette.superficie.hundida}`,
                          background: 'transparent', cursor: 'pointer',
                          '&:hover': { backgroundColor: t.palette.superficie.hundida },
                          '&:focus-visible': { outline: 'none', boxShadow: t.foco.anillo },
                        })}
                      />
                    ))}
                    {visibles.filter((t) => t.dia_semana === d.valor).map((t) => (
                      <BloqueTurno key={t.id} turno={t} onAbrir={setAbierto} horaInicio={HORA_INICIO} />
                    ))}
                  </Box>
                ))}
              </Box>
            </Box>
          </Box>
        </>
      )}

      {nuevo && (
        <DialogoNuevoTurno base={nuevo} pacientes={asignados} onCerrar={() => setNuevo(null)} onGuardar={guardar} />
      )}
      {abierto && (
        <DialogoTurno turno={abierto} pacientes={asignados} onCerrar={() => setAbierto(null)}
          onQuitar={quitar} onSumar={sumar}
          onVerPaciente={(id) => navigate(`/pacientes/${id}`)} />
      )}
      <Snackbar
        open={Boolean(aviso)} autoHideDuration={5000} onClose={() => setAviso('')}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
        message={aviso}
      />
    </AppLayout>
  );
}

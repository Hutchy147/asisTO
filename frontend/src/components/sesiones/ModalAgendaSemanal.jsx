// frontend/src/components/sesiones/ModalAgendaSemanal.jsx
// Agenda semanal recurrente (Entrega 3): "los lunes a las 9 viene este
// paciente". Los turnos son una plantilla, no sesiones; "Generar" agenda las
// sesiones de las próximas semanas, de lunes a viernes. Las que no se pueden
// agendar (superposición, paciente de baja) se informan, no se pierden.

import { useState } from 'react';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Divider from '@mui/material/Divider';
import MenuItem from '@mui/material/MenuItem';
import Typography from '@mui/material/Typography';

import CampoTexto from '../forms/CampoTexto.jsx';
import { Cargando, EstadoError } from '../estado/index.js';
import ModalFormulario from '../modal/ModalFormulario.jsx';
import { usePeticion } from '../../hooks/usePeticion.js';
import {
  crearTurno, DIAS_SEMANA, generarAgenda, listarAgendaSemanal, quitarTurno,
  SEMANAS_MAXIMAS, SEMANAS_POR_DEFECTO,
} from '../../services/agendaRecurrenteService.js';
import { formatearFecha } from '../../utils/fechas.js';

const VACIO = { id_paciente: '', dia_semana: 1, hora_inicio: '', hora_fin: '' };

export default function ModalAgendaSemanal({ abierto, pacientes = [], onCerrar, onGenerada }) {
  const lista = usePeticion(listarAgendaSemanal, [], { inmediata: abierto });
  const [turno, setTurno] = useState(VACIO);
  const [campoError, setCampoError] = useState({});
  const [error, setError] = useState('');
  const [ocupado, setOcupado] = useState(false);
  const [semanas, setSemanas] = useState(SEMANAS_POR_DEFECTO);
  const [resultado, setResultado] = useState(null);

  const set = (clave) => (e) => setTurno((t) => ({ ...t, [clave]: e?.target?.value ?? e }));

  async function ejecutar(accion) {
    setError('');
    setCampoError({});
    setOcupado(true);
    try {
      return await accion();
    } catch (fallo) {
      setError(fallo.message || 'No se pudo completar la acción.');
      if (fallo.campo) setCampoError({ [fallo.campo]: ' ' });
      return null;
    } finally {
      setOcupado(false);
    }
  }

  async function agregar() {
    if (!turno.id_paciente || !turno.hora_inicio) {
      setError('Elegí el paciente y la hora de inicio.');
      return;
    }
    const ok = await ejecutar(() => crearTurno({
      ...turno, id_paciente: Number(turno.id_paciente), dia_semana: Number(turno.dia_semana),
    }));
    if (ok) {
      setTurno((t) => ({ ...VACIO, dia_semana: t.dia_semana }));
      lista.recargar();
    }
  }

  async function quitar(id) {
    const ok = await ejecutar(() => quitarTurno(id));
    if (ok) lista.recargar();
  }

  async function generar() {
    const r = await ejecutar(() => generarAgenda(Number(semanas)));
    if (r) {
      setResultado(r);
      onGenerada?.(r);
    }
  }

  const turnos = lista.datos?.plantillas ?? [];

  return (
    <ModalFormulario
      abierto={abierto}
      ancho={700}
      titulo="Agenda semanal"
      subtitulo="Los turnos que se repiten cada semana, de lunes a viernes"
      soloCerrar
      onPedirCierre={onCerrar}
    >
      {lista.cargando && !lista.datos && <Cargando texto="Abriendo su agenda..." minHeight={120} />}
      {lista.error && <EstadoError error={lista.error} onReintentar={lista.recargar} />}
      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>{error}</Alert>}

      {lista.datos && (
        <>
          <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 0.5 }}>Tus turnos</Typography>
          {turnos.length === 0 ? (
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Todavía no cargaste turnos. Agregá el primero acá abajo.
            </Typography>
          ) : (
            <Box component="ul" sx={{ listStyle: 'none', p: 0, m: 0, mb: 2 }}>
              {turnos.map((t) => (
                <Box
                  component="li" key={t.id}
                  sx={{ display: 'flex', alignItems: 'center', gap: 1.5, py: 0.75, borderBottom: '1px solid', borderColor: 'divider' }}
                >
                  <Typography variant="body2" sx={{ width: 90, fontWeight: 600 }}>{t.dia}</Typography>
                  <Typography variant="body2" className="tabular" sx={{ width: 120 }}>
                    {t.hora_inicio.slice(0, 5)} a {t.hora_fin.slice(0, 5)}
                  </Typography>
                  <Typography variant="body2" className="texto-libre" sx={{ flex: 1 }}>{t.paciente}</Typography>
                  <Button size="small" variant="text" disabled={ocupado} onClick={() => quitar(t.id)}
                    aria-label={`Quitar el turno del ${t.dia} a las ${t.hora_inicio.slice(0, 5)}`}>
                    Quitar
                  </Button>
                </Box>
              ))}
            </Box>
          )}

          <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 1 }}>Agregar un turno</Typography>
          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1.4fr 1fr' }, gap: 1.5, mb: 1.5 }}>
            <CampoTexto id="rec-paciente" etiqueta="Paciente" select valor={turno.id_paciente}
              onChange={set('id_paciente')} error={campoError.id_paciente} deshabilitado={ocupado}
              ayuda={pacientes.length === 0 ? 'No tiene pacientes asignados.' : undefined}>
              {pacientes.map((p) => (
                <MenuItem key={p.id} value={p.id} className="texto-libre">{p.nombre_completo} · {p.nro_historia}</MenuItem>
              ))}
            </CampoTexto>
            <CampoTexto id="rec-dia" etiqueta="Día" select valor={turno.dia_semana}
              onChange={set('dia_semana')} error={campoError.dia_semana} deshabilitado={ocupado}>
              {DIAS_SEMANA.map((d) => <MenuItem key={d.valor} value={d.valor}>{d.etiqueta}</MenuItem>)}
            </CampoTexto>
            <CampoTexto id="rec-inicio" etiqueta="Hora de inicio" tipo="time" tabular valor={turno.hora_inicio}
              onChange={set('hora_inicio')} error={campoError.hora_inicio} deshabilitado={ocupado} />
            <CampoTexto id="rec-fin" etiqueta="Hora de fin" tipo="time" tabular valor={turno.hora_fin}
              ayuda="Opcional: 45 minutos si se deja vacía." onChange={set('hora_fin')}
              error={campoError.hora_fin} deshabilitado={ocupado} />
          </Box>
          <Button variant="outlined" onClick={agregar} disabled={ocupado}>Agregar turno</Button>

          <Divider sx={{ my: 3 }} />

          <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 0.5 }}>Generar la agenda</Typography>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1.5 }}>
            Agenda las sesiones de sus turnos desde hoy. Si ya existen, no se duplican.
          </Typography>
          <Box sx={{ display: 'flex', gap: 1.5, alignItems: 'flex-start', flexWrap: 'wrap' }}>
            <Box sx={{ width: 180 }}>
              <CampoTexto id="rec-semanas" etiqueta="Semanas" select valor={semanas}
                onChange={(e) => setSemanas(e?.target?.value ?? e)} deshabilitado={ocupado}>
                {Array.from({ length: SEMANAS_MAXIMAS }, (_, i) => i + 1).map((n) => (
                  <MenuItem key={n} value={n}>{n === 1 ? '1 semana' : `${n} semanas`}</MenuItem>
                ))}
              </CampoTexto>
            </Box>
            <Button variant="contained" onClick={generar} disabled={ocupado || turnos.length === 0} sx={{ mt: 0.5 }}>
              Generar agenda
            </Button>
          </Box>

          {resultado && (
            <Alert severity={resultado.omitidas.length ? 'warning' : 'success'} sx={{ mt: 2 }}>
              <strong>
                {resultado.creadas} {resultado.creadas === 1 ? 'sesión agendada' : 'sesiones agendadas'}
              </strong>
              {resultado.existentes > 0 && ` · ${resultado.existentes} ya existían`}
              {` · del ${formatearFecha(resultado.desde)} al ${formatearFecha(resultado.hasta)}`}
              {resultado.omitidas.length > 0 && (
                <Box component="ul" sx={{ m: 0, mt: 1, pl: 2.5 }}>
                  {resultado.omitidas.map((o) => (
                    <li key={`${o.fecha}-${o.hora_inicio}-${o.paciente}`}>
                      {formatearFecha(o.fecha)} {o.hora_inicio.slice(0, 5)} · {o.paciente}: {o.motivo}
                    </li>
                  ))}
                </Box>
              )}
            </Alert>
          )}
        </>
      )}
    </ModalFormulario>
  );
}

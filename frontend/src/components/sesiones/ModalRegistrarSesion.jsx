// frontend/src/components/sesiones/ModalRegistrarSesion.jsx

import Box from '@mui/material/Box';
import FormControlLabel from '@mui/material/FormControlLabel';
import MenuItem from '@mui/material/MenuItem';
import Radio from '@mui/material/Radio';
import RadioGroup from '@mui/material/RadioGroup';
import Typography from '@mui/material/Typography';

import AvisoSesionSinEvolucion from '../avisos/AvisoSesionSinEvolucion.jsx';
import CampoTexto from '../forms/CampoTexto.jsx';
import ModalFormulario from '../modal/ModalFormulario.jsx';
import { useFormularioModal } from '../../hooks/useFormularioModal.js';
import {
  ESTADO_AUSENCIA, ESTADO_COMPLETA, ESTADO_INCOMPLETA, registrarSesion,
} from '../../services/sesionesService.js';
import { formatearFecha } from '../../utils/fechas.js';

const ESTADOS = [
  {
    valor: ESTADO_COMPLETA,
    etiqueta: 'Completa',
    descripcion: 'El paciente asistió y se trabajaron los objetivos previstos.',
  },
  {
    valor: ESTADO_INCOMPLETA,
    etiqueta: 'Incompleta',
    descripcion: 'El paciente asistió pero la sesión se interrumpió o se acortó.',
  },
  {
    valor: ESTADO_AUSENCIA,
    etiqueta: 'Ausencia',
    descripcion: 'El paciente no asistió, con o sin aviso previo.',
  },
];

export default function ModalRegistrarSesion({
  abierto,
  pacientes = [],
  // Precarga cuando se abre desde un hueco de la grilla
  fechaInicial = '',
  horaInicial = '',
  onCerrar,
  onRegistrada,
}) {
  const formulario = useFormularioModal({
    inicial: {
      id_paciente: '',
      fecha: fechaInicial,
      hora_inicio: horaInicial,
      hora_fin: '',
      estado: ESTADO_COMPLETA,
      notas: '',
    },
    obligatorios: ['id_paciente', 'fecha', 'hora_inicio'],
    onEnviar: (valores) =>
      registrarSesion({
        id_paciente: Number(valores.id_paciente),
        fecha: valores.fecha,
        hora_inicio: valores.hora_inicio,
        hora_fin: valores.hora_fin || null,
        estado: valores.estado,
        notas: valores.notas.trim() || null,
      }),
    onExito: (respuesta) => {
      onCerrar?.();
      onRegistrada?.(respuesta);
    },
    onCerrar,
  });

  const { valores, setValor, setCampo, errorDe, guardando } = formulario;
  const esAusencia = valores.estado === ESTADO_AUSENCIA;

  return (
    <ModalFormulario
      abierto={abierto}
      ancho={620}
      titulo="Registrar sesión"
      subtitulo={
        valores.fecha
          ? `${formatearFecha(valores.fecha)}${valores.hora_inicio ? ` · ${valores.hora_inicio.slice(0, 5)}` : ''}`
          : 'Se registra a tu nombre'
      }
      guardando={guardando}
      errorServidor={formulario.errorServidor}
      tituloRechazo="No se pudo registrar la sesión"
      confirmandoDescarte={formulario.confirmandoDescarte}
      onPedirCierre={formulario.pedirCierre}
      onSeguirEditando={formulario.seguirEditando}
      onDescartar={formulario.descartar}
      onEnviar={formulario.enviar}
      etiquetaEnviar="Registrar sesión"
      etiquetaGuardando="Registrando…"
    >
      <CampoTexto
        id="sesion-paciente"
        etiqueta="Paciente"
        select
        obligatorio
        valor={valores.id_paciente}
        onChange={setCampo('id_paciente')}
        error={errorDe('id_paciente')}
        deshabilitado={guardando}
      >
        {pacientes.map((paciente) => (
          <MenuItem key={paciente.id} value={paciente.id}>
            {paciente.nombre_completo} · {paciente.nro_historia}
          </MenuItem>
        ))}
      </CampoTexto>

      <Box sx={{ display: 'flex', gap: 2 }}>
        <CampoTexto
          id="sesion-fecha"
          etiqueta="Fecha"
          tipo="date"
          tabular
          obligatorio
          valor={valores.fecha}
          onChange={setCampo('fecha')}
          error={errorDe('fecha')}
          deshabilitado={guardando}
        />
        <CampoTexto
          id="sesion-inicio"
          etiqueta="Hora de inicio"
          tipo="time"
          tabular
          obligatorio
          valor={valores.hora_inicio}
          onChange={setCampo('hora_inicio')}
          error={errorDe('hora_inicio')}
          deshabilitado={guardando}
        />
        <CampoTexto
          id="sesion-fin"
          etiqueta="Hora de fin"
          tipo="time"
          tabular
          ayuda="Opcional. Sin dato se asume una hora."
          valor={valores.hora_fin}
          onChange={setCampo('hora_fin')}
          error={errorDe('hora_fin')}
          deshabilitado={guardando}
        />
      </Box>

      <Box>
        <Typography variant="body2" sx={{ fontWeight: 500, mb: 0.5 }}>
          Estado de la sesión <Box component="span" sx={{ color: 'error.main' }}>*</Box>
        </Typography>
        <RadioGroup
          value={valores.estado}
          onChange={(evento) => setValor('estado', evento.target.value)}
        >
          {ESTADOS.map((estado) => (
            <FormControlLabel
              key={estado.valor}
              value={estado.valor}
              disabled={guardando}
              control={<Radio size="small" />}
              label={
                <Box sx={{ py: 0.25 }}>
                  <Box component="span" sx={{ fontSize: 14 }}>
                    {estado.etiqueta}
                  </Box>
                  <Typography variant="caption" sx={{ display: 'block' }}>
                    {estado.descripcion}
                  </Typography>
                </Box>
              }
            />
          ))}
        </RadioGroup>
      </Box>

      {/* El aviso aparece AL ELEGIR ausencia, no al guardar: para eso está
          el radio ahí arriba, para que la consecuencia se vea antes de
          confirmar y todavía se pueda cambiar de opinión. */}
      {esAusencia && <AvisoSesionSinEvolucion modo="registro" />}

      <CampoTexto
        id="sesion-notas"
        etiqueta={esAusencia ? 'Motivo de la ausencia' : 'Notas de la sesión'}
        multilinea
        filas={3}
        ayuda="Opcional."
        valor={valores.notas}
        onChange={setCampo('notas')}
        deshabilitado={guardando}
      />
    </ModalFormulario>
  );
}

// frontend/src/components/sesiones/ModalAgendarSesion.jsx
// Agenda una sesión desde el calendario (Entrega 3). El calendario planifica:
// no pide el estado ni quién faltó, que se declaran al registrar lo ocurrido.
// La sesión nace "incompleta" (todavía sin registro) y dura 45 minutos salvo
// que se indique otra hora de fin. Solo lunes a viernes.

import MenuItem from '@mui/material/MenuItem';

import CampoTexto from '../forms/CampoTexto.jsx';
import ModalFormulario from '../modal/ModalFormulario.jsx';
import { useFormularioModal } from '../../hooks/useFormularioModal.js';
import { ErrorApi } from '../../services/api.js';
import { registrarSesion } from '../../services/sesionesService.js';
import { formatearFecha } from '../../utils/fechas.js';

/** ¿La fecha AAAA-MM-DD cae en sábado o domingo? (local, sin pasar por UTC) */
export function esFinDeSemana(fechaIso) {
  const [a, m, d] = (fechaIso ?? '').split('-').map(Number);
  if (!a || !m || !d) return false;
  const dia = new Date(a, m - 1, d).getDay();
  return dia === 0 || dia === 6;
}

export default function ModalAgendarSesion({
  abierto, pacientes = [], fechaInicial = '', horaInicial = '', onCerrar, onAgendada,
}) {
  const formulario = useFormularioModal({
    inicial: {
      id_paciente: '',
      fecha: fechaInicial,
      hora_inicio: horaInicial,
      hora_fin: '',
      notas: '',
    },
    obligatorios: ['id_paciente', 'fecha', 'hora_inicio'],
    onEnviar: (valores) => {
      // Mismo criterio que el servidor, antes de gastar un viaje. El servidor
      // lo vuelve a validar: esta es la primera línea, no la única.
      if (esFinDeSemana(valores.fecha)) {
        throw new ErrorApi('Las sesiones se agendan de lunes a viernes.', { campo: 'fecha' });
      }
      return registrarSesion({
        id_paciente: Number(valores.id_paciente),
        fecha: valores.fecha,
        hora_inicio: valores.hora_inicio,
        hora_fin: valores.hora_fin || null, // vacío: el servidor pone 45 minutos
        estado: 'incompleta',
        ausencia_de: null,
        notas: valores.notas.trim() || null,
      });
    },
    onExito: (respuesta) => {
      onCerrar?.();
      onAgendada?.(respuesta);
    },
    onCerrar,
  });

  const { valores, setCampo, errorDe, guardando } = formulario;

  return (
    <ModalFormulario
      abierto={abierto}
      ancho={560}
      titulo="Agendar sesión"
      subtitulo={
        valores.fecha
          ? `${formatearFecha(valores.fecha)}${valores.hora_inicio ? ` · ${valores.hora_inicio.slice(0, 5)}` : ''}`
          : 'Se agenda a su nombre'
      }
      guardando={guardando}
      errorServidor={formulario.errorServidor}
      tituloRechazo="No se pudo agendar la sesión"
      confirmandoDescarte={formulario.confirmandoDescarte}
      onPedirCierre={formulario.pedirCierre}
      onSeguirEditando={formulario.seguirEditando}
      onDescartar={formulario.descartar}
      onEnviar={formulario.enviar}
      etiquetaEnviar="Agendar"
      etiquetaGuardando="Agendando…"
    >
      <CampoTexto
        id="agenda-paciente"
        etiqueta="Paciente"
        select
        obligatorio
        ayuda={pacientes.length === 0
          ? 'No tiene pacientes asignados. Solicite la asignación al administrador.'
          : undefined}
        valor={valores.id_paciente}
        onChange={setCampo('id_paciente')}
        error={errorDe('id_paciente')}
        deshabilitado={guardando}
      >
        {pacientes.map((p) => (
          <MenuItem key={p.id} value={p.id} className="texto-libre">
            {p.nombre_completo} · {p.nro_historia}
          </MenuItem>
        ))}
      </CampoTexto>
      <CampoTexto
        id="agenda-fecha"
        etiqueta="Fecha"
        tipo="date"
        tabular
        obligatorio
        ayuda="De lunes a viernes."
        valor={valores.fecha}
        onChange={setCampo('fecha')}
        error={errorDe('fecha')}
        deshabilitado={guardando}
      />
      <CampoTexto
        id="agenda-hora-inicio"
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
        id="agenda-hora-fin"
        etiqueta="Hora de fin"
        tipo="time"
        tabular
        ayuda="Opcional. Si se deja vacía, la sesión dura 45 minutos."
        valor={valores.hora_fin}
        onChange={setCampo('hora_fin')}
        error={errorDe('hora_fin')}
        deshabilitado={guardando}
      />
      <CampoTexto
        id="agenda-notas"
        etiqueta="Notas"
        multilinea
        filas={3}
        ayuda="Opcional. Aspectos que desea tener presentes para esta sesión."
        valor={valores.notas}
        onChange={setCampo('notas')}
        error={errorDe('notas')}
        deshabilitado={guardando}
      />
    </ModalFormulario>
  );
}

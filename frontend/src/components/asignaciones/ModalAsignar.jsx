// frontend/src/components/asignaciones/ModalAsignar.jsx
// Asigna un paciente a un terapeuta (HDU 11). Mismo patrón que el resto de
// los modales: useFormularioModal + ModalFormulario.

import MenuItem from '@mui/material/MenuItem';

import CampoTexto from '../forms/CampoTexto.jsx';
import ModalFormulario from '../modal/ModalFormulario.jsx';
import { useFormularioModal } from '../../hooks/useFormularioModal.js';
import { abrirAsignacion } from '../../services/asignacionesService.js';

export default function ModalAsignar({
  abierto, paciente, terapeutas = [], idTerapeutaActual, onCerrar, onAsignado,
}) {
  const formulario = useFormularioModal({
    inicial: { id_terapeuta: idTerapeutaActual ?? '', fecha_desde: '' },
    obligatorios: ['id_terapeuta'],
    onEnviar: (valores) =>
      abrirAsignacion(paciente.id, {
        idTerapeuta: Number(valores.id_terapeuta),
        fechaDesde: valores.fecha_desde,
      }),
    onExito: (respuesta) => {
      onCerrar?.();
      onAsignado?.(respuesta);
    },
    onCerrar,
  });

  const { valores, setCampo, errorDe, guardando } = formulario;

  return (
    <ModalFormulario
      abierto={abierto}
      titulo="Asignar terapeuta"
      subtitulo={paciente ? `Responsable de ${paciente.nombre_completo}` : ''}
      guardando={guardando}
      errorServidor={formulario.errorServidor}
      tituloRechazo="No se pudo asignar el paciente"
      confirmandoDescarte={formulario.confirmandoDescarte}
      onPedirCierre={formulario.pedirCierre}
      onSeguirEditando={formulario.seguirEditando}
      onDescartar={formulario.descartar}
      onEnviar={formulario.enviar}
      etiquetaEnviar="Asignar"
      etiquetaGuardando="Asignando…"
    >
      <CampoTexto
        id="asignacion-terapeuta"
        etiqueta="Terapeuta responsable"
        select
        obligatorio
        ayuda="Solo el terapeuta asignado puede registrar las sesiones y evoluciones del paciente. Los demás terapeutas pueden consultarlo."
        valor={valores.id_terapeuta}
        onChange={setCampo('id_terapeuta')}
        error={errorDe('id_terapeuta')}
        deshabilitado={guardando}
      >
        {terapeutas.map((t) => (
          <MenuItem key={t.id} value={t.id} className="texto-libre">
            {t.nombre_completo}{t.especialidad ? ` · ${t.especialidad}` : ''}
          </MenuItem>
        ))}
      </CampoTexto>
      <CampoTexto
        id="asignacion-desde"
        etiqueta="Desde"
        tipo="date"
        tabular
        ayuda="Opcional. Si se deja vacía, rige desde hoy. Una fecha anterior permite cargar sesiones retroactivas."
        valor={valores.fecha_desde}
        onChange={setCampo('fecha_desde')}
        error={errorDe('fecha_desde')}
        deshabilitado={guardando}
      />
    </ModalFormulario>
  );
}

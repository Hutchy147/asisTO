// frontend/src/components/familiares/ModalVincularExistente.jsx
// Vincula al paciente una cuenta de familiar que ya existe (por ejemplo, un
// hermano que ya accede por otro paciente).

import MenuItem from '@mui/material/MenuItem';

import CampoTexto from '../forms/CampoTexto.jsx';
import ModalFormulario from '../modal/ModalFormulario.jsx';
import { useFormularioModal } from '../../hooks/useFormularioModal.js';
import { vincularExistente } from '../../services/familiaresService.js';

export default function ModalVincularExistente({
  abierto, paciente, candidatos = [], onCerrar, onVinculado,
}) {
  const formulario = useFormularioModal({
    inicial: { id_familiar: '' },
    obligatorios: ['id_familiar'],
    onEnviar: (valores) => vincularExistente(paciente.id, Number(valores.id_familiar)),
    onExito: (respuesta) => {
      onCerrar?.();
      onVinculado?.(respuesta);
    },
    onCerrar,
  });
  const { valores, setCampo, errorDe, guardando } = formulario;

  return (
    <ModalFormulario
      abierto={abierto}
      titulo="Vincular cuenta existente"
      subtitulo={paciente ? `Acceso a la evolución de ${paciente.nombre_completo}` : ''}
      guardando={guardando}
      errorServidor={formulario.errorServidor}
      tituloRechazo="No se pudo vincular al familiar"
      confirmandoDescarte={formulario.confirmandoDescarte}
      onPedirCierre={formulario.pedirCierre}
      onSeguirEditando={formulario.seguirEditando}
      onDescartar={formulario.descartar}
      onEnviar={formulario.enviar}
      etiquetaEnviar="Vincular"
      etiquetaGuardando="Vinculando…"
    >
      <CampoTexto
        id="vinculo-familiar"
        etiqueta="Familiar"
        select
        obligatorio
        ayuda={
          candidatos.length === 0
            ? 'No hay otras cuentas de familiar disponibles. Cree una cuenta nueva.'
            : 'Quedará habilitado para consultar la evolución del paciente y recibir sus avisos.'
        }
        valor={valores.id_familiar}
        onChange={setCampo('id_familiar')}
        error={errorDe('id_familiar')}
        deshabilitado={guardando || candidatos.length === 0}
      >
        {candidatos.map((f) => (
          <MenuItem key={f.id} value={f.id} className="texto-libre">
            {f.nombre_completo} · {f.email}
          </MenuItem>
        ))}
      </CampoTexto>
    </ModalFormulario>
  );
}

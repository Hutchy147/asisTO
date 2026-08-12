// frontend/src/components/pacientes/ModalEditarPaciente.jsx
// Edición de los datos del paciente. Mismo patrón que ModalAltaPaciente:
// ver useFormularioModal y ModalFormulario.
//
// Es un componente aparte y no un modo del modal de alta, y es a propósito:
// los dos formularios se parecen hoy pero no responden a lo mismo. El alta
// crea un registro clínico y no ofrece obra social; la edición corrige datos
// ya cargados, incluidos el número de historia y la fecha de nacimiento, que
// son justamente los que se tipean mal. Unificarlos obligaría a que cada
// campo preguntara en qué modo está.

import CampoTexto from '../forms/CampoTexto.jsx';
import ModalFormulario from '../modal/ModalFormulario.jsx';
import { useFormularioModal } from '../../hooks/useFormularioModal.js';
import {
  MAXIMO_CARACTERES_APELLIDO,
  MAXIMO_CARACTERES_NOMBRE,
  MAXIMO_CARACTERES_NRO_HISTORIA,
  MAXIMO_CARACTERES_OBRA_SOCIAL,
  editarPaciente,
} from '../../services/pacientesService.js';

const OBLIGATORIOS = ['nombre', 'apellido', 'fecha_nacimiento', 'nro_historia'];

export default function ModalEditarPaciente({ abierto, paciente, onCerrar, onGuardado }) {
  const formulario = useFormularioModal({
    // El formulario arranca con lo que ya está cargado. Los dos opcionales
    // pueden venir null desde la base y el input necesita string.
    inicial: {
      nombre: paciente?.nombre ?? '',
      apellido: paciente?.apellido ?? '',
      fecha_nacimiento: paciente?.fecha_nacimiento ?? '',
      nro_historia: paciente?.nro_historia ?? '',
      obra_social: paciente?.obra_social ?? '',
      diagnostico: paciente?.diagnostico ?? '',
    },
    obligatorios: OBLIGATORIOS,
    onEnviar: (valores) =>
      editarPaciente(paciente.id, {
        nombre: valores.nombre.trim(),
        apellido: valores.apellido.trim(),
        fecha_nacimiento: valores.fecha_nacimiento,
        nro_historia: valores.nro_historia.trim(),
        // Vacío se manda como null y no como '': son campos opcionales, y
        // guardar la cadena vacía dejaría un dato que "existe" y no dice nada.
        obra_social: valores.obra_social.trim() || null,
        diagnostico: valores.diagnostico.trim() || null,
      }),
    onExito: (respuesta) => {
      onCerrar?.();
      onGuardado?.(respuesta);
    },
    onCerrar,
  });

  const { valores, setCampo, errorDe, guardando } = formulario;

  return (
    <ModalFormulario
      abierto={abierto}
      titulo="Editar paciente"
      // El subtítulo interpola dos campos que escribió una persona. Lleva
      // `texto-libre` explícito y no se apoya en que ModalFormulario lo
      // herede: es la decisión 14 bis, y el test estático de auditoría marcó
      // este archivo el mismo día en que se escribió.
      subtitulo={(
        <span className="texto-libre">
          {`${paciente?.nombre_completo ?? ''} · ${paciente?.nro_historia ?? ''}`}
        </span>
      )}
      guardando={guardando}
      errorServidor={formulario.errorServidor}
      tituloRechazo="No se pudieron guardar los cambios"
      confirmandoDescarte={formulario.confirmandoDescarte}
      onPedirCierre={formulario.pedirCierre}
      onSeguirEditando={formulario.seguirEditando}
      onDescartar={formulario.descartar}
      onEnviar={formulario.enviar}
      etiquetaEnviar="Guardar cambios"
      etiquetaGuardando="Guardando…"
    >
      <CampoTexto
        id="editar-nombre"
        etiqueta="Nombre"
        obligatorio
        maximoCaracteres={MAXIMO_CARACTERES_NOMBRE}
        valor={valores.nombre}
        onChange={setCampo('nombre')}
        error={errorDe('nombre')}
        deshabilitado={guardando}
        autoFocus
      />
      <CampoTexto
        id="editar-apellido"
        etiqueta="Apellido"
        obligatorio
        maximoCaracteres={MAXIMO_CARACTERES_APELLIDO}
        valor={valores.apellido}
        onChange={setCampo('apellido')}
        error={errorDe('apellido')}
        deshabilitado={guardando}
      />
      <CampoTexto
        id="editar-nacimiento"
        etiqueta="Fecha de nacimiento"
        tipo="date"
        tabular
        obligatorio
        valor={valores.fecha_nacimiento}
        onChange={setCampo('fecha_nacimiento')}
        error={errorDe('fecha_nacimiento')}
        deshabilitado={guardando}
      />
      <CampoTexto
        id="editar-historia"
        etiqueta="N° de historia"
        tabular
        obligatorio
        maximoCaracteres={MAXIMO_CARACTERES_NRO_HISTORIA}
        ayuda="Único en el centro. Se puede corregir si se cargó mal."
        valor={valores.nro_historia}
        onChange={setCampo('nro_historia')}
        error={errorDe('nro_historia')}
        deshabilitado={guardando}
      />
      <CampoTexto
        id="editar-obra-social"
        etiqueta="Obra social"
        maximoCaracteres={MAXIMO_CARACTERES_OBRA_SOCIAL}
        ayuda="Opcional. Dato administrativo, no clínico."
        valor={valores.obra_social}
        onChange={setCampo('obra_social')}
        error={errorDe('obra_social')}
        deshabilitado={guardando}
      />
      <CampoTexto
        id="editar-diagnostico"
        etiqueta="Diagnóstico"
        multilinea
        filas={3}
        valor={valores.diagnostico}
        onChange={setCampo('diagnostico')}
        error={errorDe('diagnostico')}
        deshabilitado={guardando}
      />
    </ModalFormulario>
  );
}

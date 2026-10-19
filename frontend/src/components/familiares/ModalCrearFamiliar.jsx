// frontend/src/components/familiares/ModalCrearFamiliar.jsx
// Crea la cuenta de un familiar y la vincula al paciente. La contraseña
// temporal la genera el servidor y se muestra una sola vez (ver
// DialogoContrasenaTemporal).

import CampoTexto from '../forms/CampoTexto.jsx';
import ModalFormulario from '../modal/ModalFormulario.jsx';
import { useFormularioModal } from '../../hooks/useFormularioModal.js';
import { crearYVincular } from '../../services/familiaresService.js';

const INICIAL = { nombre: '', apellido: '', email: '', parentesco: '', telefono: '' };

export default function ModalCrearFamiliar({ abierto, paciente, onCerrar, onCreado }) {
  const formulario = useFormularioModal({
    inicial: INICIAL,
    obligatorios: ['nombre', 'apellido', 'email'],
    onEnviar: (valores) => crearYVincular(paciente.id, valores),
    onExito: (respuesta) => {
      onCerrar?.();
      onCreado?.(respuesta);
    },
    onCerrar,
  });
  const { valores, setCampo, errorDe, guardando } = formulario;

  return (
    <ModalFormulario
      abierto={abierto}
      titulo="Crear cuenta de familiar"
      subtitulo={paciente ? `Se vinculará a ${paciente.nombre_completo}` : ''}
      guardando={guardando}
      errorServidor={formulario.errorServidor}
      tituloRechazo="No se pudo crear al familiar"
      confirmandoDescarte={formulario.confirmandoDescarte}
      onPedirCierre={formulario.pedirCierre}
      onSeguirEditando={formulario.seguirEditando}
      onDescartar={formulario.descartar}
      onEnviar={formulario.enviar}
      etiquetaEnviar="Crear y vincular"
      etiquetaGuardando="Creando…"
    >
      <CampoTexto
        id="familiar-nombre" etiqueta="Nombre" obligatorio maximoCaracteres={100}
        valor={valores.nombre} onChange={setCampo('nombre')}
        error={errorDe('nombre')} deshabilitado={guardando}
      />
      <CampoTexto
        id="familiar-apellido" etiqueta="Apellido" obligatorio maximoCaracteres={100}
        valor={valores.apellido} onChange={setCampo('apellido')}
        error={errorDe('apellido')} deshabilitado={guardando}
      />
      <CampoTexto
        id="familiar-email" etiqueta="Correo electrónico" tipo="email" obligatorio
        ayuda="Es el usuario con el que ingresará al portal."
        valor={valores.email} onChange={setCampo('email')}
        error={errorDe('email')} deshabilitado={guardando}
      />
      <CampoTexto
        id="familiar-parentesco" etiqueta="Parentesco" maximoCaracteres={60}
        ayuda="Opcional. Por ejemplo: madre, padre, hermana."
        valor={valores.parentesco} onChange={setCampo('parentesco')}
        error={errorDe('parentesco')} deshabilitado={guardando}
      />
      <CampoTexto
        id="familiar-telefono" etiqueta="Teléfono" maximoCaracteres={40} tabular
        ayuda="Opcional."
        valor={valores.telefono} onChange={setCampo('telefono')}
        error={errorDe('telefono')} deshabilitado={guardando}
      />
    </ModalFormulario>
  );
}

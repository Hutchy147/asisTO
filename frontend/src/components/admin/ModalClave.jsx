// frontend/src/components/admin/ModalClave.jsx
// El administrador fija una clave nueva para una cuenta (la persona la olvidó
// o la cuenta estaba bloqueada). Cierra las sesiones abiertas de esa cuenta.

import ModalFormulario from '../modal/ModalFormulario.jsx';
import CampoClave from './CampoClave.jsx';
import { useFormularioModal } from '../../hooks/useFormularioModal.js';
import { restablecerContrasenaDeUsuario } from '../../services/usuariosService.js';

export default function ModalClave({ abierto, cuenta, onCerrar, onRestablecida }) {
  const formulario = useFormularioModal({
    inicial: { contrasena: '' },
    obligatorios: ['contrasena'],
    onEnviar: (v) => restablecerContrasenaDeUsuario(cuenta.id, v.contrasena)
      .then((respuesta) => ({ ...respuesta, contrasena: v.contrasena })),
    onExito: (respuesta) => {
      onCerrar?.();
      onRestablecida?.(respuesta);
    },
    onCerrar,
  });

  return (
    <ModalFormulario
      abierto={abierto}
      titulo="Restablecer la contraseña"
      subtitulo={cuenta ? `${cuenta.nombre_completo} · ${cuenta.email}` : ''}
      guardando={formulario.guardando}
      errorServidor={formulario.errorServidor}
      tituloRechazo="No se pudo restablecer la contraseña"
      confirmandoDescarte={formulario.confirmandoDescarte}
      onPedirCierre={formulario.pedirCierre}
      onSeguirEditando={formulario.seguirEditando}
      onDescartar={formulario.descartar}
      onEnviar={formulario.enviar}
      etiquetaEnviar="Restablecer"
      etiquetaGuardando="Guardando…"
    >
      <CampoClave
        id="clave-nueva" valor={formulario.valores.contrasena}
        onChange={(valor) => formulario.setValor('contrasena', valor)}
        error={formulario.errorDe('contrasena')} deshabilitado={formulario.guardando}
      />
    </ModalFormulario>
  );
}

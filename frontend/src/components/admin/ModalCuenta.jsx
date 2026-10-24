// frontend/src/components/admin/ModalCuenta.jsx
// Alta de una cuenta: correo, clave y el dato propio del rol. Mismo patrón que
// el resto de los modales: useFormularioModal + ModalFormulario.

import MenuItem from '@mui/material/MenuItem';

import CampoTexto from '../forms/CampoTexto.jsx';
import ModalFormulario from '../modal/ModalFormulario.jsx';
import CampoClave from './CampoClave.jsx';
import { useFormularioModal } from '../../hooks/useFormularioModal.js';
import { crearUsuario, NOMBRE_DE_ROL, ROLES_CREABLES } from '../../services/usuariosService.js';

const INICIAL = {
  rol: '', nombre: '', apellido: '', email: '', contrasena: '',
  matricula: '', especialidad: '', nro_legajo: '', sector: '', parentesco: '', telefono: '',
};

export default function ModalCuenta({ abierto, onCerrar, onCreada }) {
  const formulario = useFormularioModal({
    inicial: INICIAL,
    obligatorios: ['rol', 'nombre', 'apellido', 'email', 'contrasena'],
    onEnviar: (v) => {
      const cuerpo = { rol: v.rol, nombre: v.nombre, apellido: v.apellido, email: v.email, contrasena: v.contrasena };
      if (v.rol === 'terapeuta') Object.assign(cuerpo, { matricula: v.matricula, especialidad: v.especialidad });
      if (v.rol === 'rrhh') Object.assign(cuerpo, { nro_legajo: v.nro_legajo, sector: v.sector });
      if (v.rol === 'familiar') Object.assign(cuerpo, { parentesco: v.parentesco, telefono: v.telefono });
      return crearUsuario(cuerpo).then((respuesta) => ({ ...respuesta, contrasena: v.contrasena }));
    },
    onExito: (respuesta) => {
      onCerrar?.();
      onCreada?.(respuesta);
    },
    onCerrar,
  });

  const { valores, setCampo, setValor, errorDe, guardando } = formulario;
  const campo = (clave, etiqueta, extra = {}) => (
    <CampoTexto
      id={`cuenta-${clave}`} etiqueta={etiqueta} valor={valores[clave]} onChange={setCampo(clave)}
      error={errorDe(clave)} deshabilitado={guardando} {...extra}
    />
  );

  return (
    <ModalFormulario
      abierto={abierto}
      titulo="Nueva cuenta"
      subtitulo="Habilita un correo para que la persona pueda ingresar"
      guardando={guardando}
      errorServidor={formulario.errorServidor}
      tituloRechazo="No se pudo crear la cuenta"
      confirmandoDescarte={formulario.confirmandoDescarte}
      onPedirCierre={formulario.pedirCierre}
      onSeguirEditando={formulario.seguirEditando}
      onDescartar={formulario.descartar}
      onEnviar={formulario.enviar}
      etiquetaEnviar="Crear cuenta"
      etiquetaGuardando="Creando…"
    >
      <CampoTexto
        id="cuenta-rol" etiqueta="Rol" select obligatorio valor={valores.rol} onChange={setCampo('rol')}
        error={errorDe('rol')} deshabilitado={guardando}
        ayuda="Define qué pantallas ve la persona. El acceso de un paciente se habilita desde su ficha."
      >
        {ROLES_CREABLES.map((r) => <MenuItem key={r} value={r}>{NOMBRE_DE_ROL[r]}</MenuItem>)}
      </CampoTexto>
      {campo('nombre', 'Nombre', { obligatorio: true })}
      {campo('apellido', 'Apellido', { obligatorio: true })}
      {campo('email', 'Correo electrónico', { obligatorio: true, tipo: 'email', autoComplete: 'off' })}
      <CampoClave
        id="cuenta-contrasena" valor={valores.contrasena} onChange={(valor) => setValor('contrasena', valor)}
        error={errorDe('contrasena')} deshabilitado={guardando}
      />
      {valores.rol === 'terapeuta' && (
        <>
          {campo('matricula', 'Matrícula', { obligatorio: true })}
          {campo('especialidad', 'Especialidad (opcional)')}
        </>
      )}
      {valores.rol === 'rrhh' && (
        <>
          {campo('nro_legajo', 'Número de legajo', { obligatorio: true })}
          {campo('sector', 'Sector (opcional)')}
        </>
      )}
      {valores.rol === 'familiar' && (
        <>
          {campo('parentesco', 'Parentesco (opcional)')}
          {campo('telefono', 'Teléfono (opcional)')}
        </>
      )}
    </ModalFormulario>
  );
}

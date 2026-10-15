// frontend/src/components/pacientes/ModalAltaPaciente.jsx
// Alta de paciente. Es el más simple de los cuatro modales y el que fija
// el patrón: ver useFormularioModal y ModalFormulario.

import MenuItem from '@mui/material/MenuItem';

import CampoTexto from '../forms/CampoTexto.jsx';
import ModalFormulario from '../modal/ModalFormulario.jsx';
import { useFormularioModal } from '../../hooks/useFormularioModal.js';
import { hayCapacidad } from '../../config/entregas.js';
import { crearPaciente } from '../../services/pacientesService.js';

const INICIAL = {
  nombre: '',
  apellido: '',
  fecha_nacimiento: '',
  nro_historia: '',
  diagnostico: '',
  id_terapeuta: '',
};

// El diagnóstico es el único opcional: se puede completar después desde la
// ficha, y exigirlo en el alta obligaría a inventar algo.
const OBLIGATORIOS = ['nombre', 'apellido', 'fecha_nacimiento', 'nro_historia'];

// Qué campo marcar ante un rechazo lo dice el SERVIDOR, en el campo
// `campo` de la respuesta de error. Acá no hay nada que decidir: antes
// había una heurística que miraba el texto del mensaje y se rompía en
// silencio si el mensaje de un trigger cambiaba.

export default function ModalAltaPaciente({
  abierto, onCerrar, onCreado, terapeutas = [], idTerapeutaActual = null,
}) {
  // HDU 11: el responsable se elige en el alta; por omision, quien lo da de alta.
  const conAsignaciones = hayCapacidad('asignaciones.gestionar');
  const formulario = useFormularioModal({
    inicial: { ...INICIAL, id_terapeuta: idTerapeutaActual ?? '' },
    obligatorios: OBLIGATORIOS,
    onEnviar: (valores) =>
      crearPaciente({
        nombre: valores.nombre.trim(),
        apellido: valores.apellido.trim(),
        fecha_nacimiento: valores.fecha_nacimiento,
        nro_historia: valores.nro_historia.trim(),
        diagnostico: valores.diagnostico.trim() || null,
        id_terapeuta: conAsignaciones && valores.id_terapeuta ? Number(valores.id_terapeuta) : null,
        id_usuario: null, // el alta no crea cuenta: es un registro clínico
      }),
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
      titulo="Nuevo paciente"
      subtitulo="Se da de alta como registro clínico. La cuenta de acceso es aparte y opcional."
      guardando={guardando}
      errorServidor={formulario.errorServidor}
      tituloRechazo="No se pudo dar de alta el paciente"
      confirmandoDescarte={formulario.confirmandoDescarte}
      onPedirCierre={formulario.pedirCierre}
      onSeguirEditando={formulario.seguirEditando}
      onDescartar={formulario.descartar}
      onEnviar={formulario.enviar}
      // "Ingresar" y no "Ingreso": el botón nombra la ACCIÓN, como el resto
      // de la app —"Registrar sesión", "Guardar evolución"—. La palabra la
      // confirmó una terapeuta ocupacional usando el sistema; lo que se
      // descartó fue "Dar de alta", que en el rubro significa lo contrario.
      etiquetaEnviar="Ingresar"
      etiquetaGuardando="Ingresando…"
    >
      <CampoTexto
        id="paciente-nombre"
        etiqueta="Nombre"
        obligatorio
        valor={valores.nombre}
        onChange={setCampo('nombre')}
        error={errorDe('nombre')}
        deshabilitado={guardando}
        autoFocus
      />
      <CampoTexto
        id="paciente-apellido"
        etiqueta="Apellido"
        obligatorio
        valor={valores.apellido}
        onChange={setCampo('apellido')}
        error={errorDe('apellido')}
        deshabilitado={guardando}
      />
      <CampoTexto
        id="paciente-nacimiento"
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
        id="paciente-historia"
        etiqueta="N° de historia"
        tabular
        obligatorio
        placeholder="HC-0017"
        ayuda="Único en el centro."
        valor={valores.nro_historia}
        onChange={setCampo('nro_historia')}
        error={errorDe('nro_historia')}
        deshabilitado={guardando}
      />
      <CampoTexto
        id="paciente-diagnostico"
        etiqueta="Diagnóstico"
        multilinea
        filas={3}
        ayuda="Opcional. Se puede completar más adelante desde la ficha."
        valor={valores.diagnostico}
        onChange={setCampo('diagnostico')}
        deshabilitado={guardando}
      />
      {conAsignaciones && (
        <CampoTexto
          id="paciente-responsable"
          etiqueta="Terapeuta responsable"
          select
          ayuda="Solo quien tiene asignado al paciente puede registrarle sesiones."
          valor={valores.id_terapeuta}
          onChange={setCampo('id_terapeuta')}
          error={errorDe('id_terapeuta')}
          deshabilitado={guardando}
        >
          {terapeutas.map((t) => (
            <MenuItem key={t.id} value={t.id}>{t.nombre_completo ?? t.nombre}</MenuItem>
          ))}
        </CampoTexto>
      )}
    </ModalFormulario>
  );
}

// frontend/src/components/objetivos/ModalObjetivo.jsx
// Alta y edición de objetivo. Un solo componente con dos modos: cambian el
// título, el verbo y poco más. Todo el comportamiento viene del patrón
// (useFormularioModal + ModalFormulario).

import Box from '@mui/material/Box';

import GoalMeter from '../data/GoalMeter.jsx';
import CampoTexto from '../forms/CampoTexto.jsx';
import ModalFormulario from '../modal/ModalFormulario.jsx';
import Aviso from '../estado/Aviso.jsx';
import { useFormularioModal } from '../../hooks/useFormularioModal.js';
import {
  MAXIMO_CARACTERES_DESCRIPCION, crearObjetivo, editarObjetivo,
} from '../../services/objetivosService.js';

export default function ModalObjetivo({
  abierto,
  paciente,
  cupo,
  objetivo, // presente = edición; ausente = alta
  onCerrar,
  onGuardado,
}) {
  const esEdicion = Boolean(objetivo);
  // El tope solo bloquea el ALTA. Editar uno que ya existe no consume cupo.
  const enTope = !esEdicion && cupo?.disponibles <= 0;

  const formulario = useFormularioModal({
    inicial: { descripcion: objetivo?.descripcion ?? '' },
    obligatorios: ['descripcion'],
    onEnviar: ({ descripcion }) =>
      esEdicion
        ? editarObjetivo(objetivo.id, descripcion.trim())
        : crearObjetivo({ id_paciente: paciente.id, descripcion: descripcion.trim() }),
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
      titulo={esEdicion ? 'Editar objetivo' : 'Nuevo objetivo terapéutico'}
      subtitulo={paciente ? `${paciente.nombre_completo} · ${paciente.nro_historia}` : undefined}
      guardando={guardando}
      errorServidor={formulario.errorServidor}
      tituloRechazo={
        esEdicion ? 'No se pudo guardar el objetivo' : 'No se pudo crear el objetivo'
      }
      confirmandoDescarte={formulario.confirmandoDescarte}
      onPedirCierre={formulario.pedirCierre}
      onSeguirEditando={formulario.seguirEditando}
      onDescartar={formulario.descartar}
      onEnviar={formulario.enviar}
      etiquetaEnviar={esEdicion ? 'Guardar cambios' : 'Crear objetivo'}
      etiquetaGuardando={esEdicion ? 'Guardando…' : 'Creando…'}
      enviarDeshabilitado={enTope}
    >
      {cupo && (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <Box component="span" sx={{ fontSize: 13, color: 'text.secondary' }}>
            Objetivos activos
          </Box>
          <GoalMeter valor={cupo.usados} maximo={cupo.maximo} />
        </Box>
      )}

      {enTope && (
        <Aviso severidad="warning" titulo="Hay 4 objetivos activos">
          El tope del sistema son 4 por paciente. Archivá uno desde la ficha
          para poder crear este. Archivar no borra su historial de
          calificaciones.
        </Aviso>
      )}

      <CampoTexto
        id="objetivo-descripcion"
        etiqueta="Descripción del objetivo"
        obligatorio
        multilinea
        // 5 filas y no 3: el formato real de un objetivo —conducta, nivel de
        // apoyo, criterio, contexto y plazo— ocupa unas cinco líneas. Con
        // tres, escribirlo era mirar el texto por una ranura.
        filas={5}
        autoFocus
        // El tope y el contador salen de este único prop. El número es el
        // mismo que el del servicio y el de la columna.
        maximoCaracteres={MAXIMO_CARACTERES_DESCRIPCION}
        ayuda={
          esEdicion
            ? 'Qué se busca lograr, con su criterio y su plazo.'
            : 'Qué se busca lograr, en positivo y observable, con su criterio y su plazo.'
        }
        valor={valores.descripcion}
        onChange={setCampo('descripcion')}
        error={errorDe('descripcion')}
        // Con el cupo lleno el campo se deshabilita: no tiene sentido
        // escribir algo que no se va a poder guardar.
        deshabilitado={guardando || enTope}
      />
    </ModalFormulario>
  );
}

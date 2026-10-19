// frontend/src/components/objetivos/ModalPlantillaObjetivo.jsx
// Alta y edición de una plantilla de objetivo (administrador).

import CampoTexto from '../forms/CampoTexto.jsx';
import ModalFormulario from '../modal/ModalFormulario.jsx';
import { useFormularioModal } from '../../hooks/useFormularioModal.js';
import { crearPlantilla, editarPlantilla } from '../../services/plantillasObjetivosService.js';
import { MAXIMO_CARACTERES_DESCRIPCION } from '../../services/objetivosService.js';

export default function ModalPlantillaObjetivo({ abierto, plantilla, areaInicial = '', onCerrar, onGuardado }) {
  const edicion = Boolean(plantilla);
  const formulario = useFormularioModal({
    inicial: { area: plantilla?.area ?? areaInicial, descripcion: plantilla?.descripcion ?? '' },
    obligatorios: ['area', 'descripcion'],
    onEnviar: (v) => {
      const datos = { area: v.area.trim(), descripcion: v.descripcion.trim() };
      return edicion ? editarPlantilla(plantilla.id, datos) : crearPlantilla(datos);
    },
    onExito: (respuesta) => { onCerrar?.(); onGuardado?.(respuesta); },
    onCerrar,
  });
  const { valores, setCampo, errorDe, guardando } = formulario;

  return (
    <ModalFormulario
      abierto={abierto}
      titulo={edicion ? 'Editar plantilla' : 'Nueva plantilla'}
      subtitulo="Texto sugerido para crear objetivos"
      guardando={guardando}
      errorServidor={formulario.errorServidor}
      tituloRechazo="No se pudo guardar la plantilla"
      confirmandoDescarte={formulario.confirmandoDescarte}
      onPedirCierre={formulario.pedirCierre}
      onSeguirEditando={formulario.seguirEditando}
      onDescartar={formulario.descartar}
      onEnviar={formulario.enviar}
      etiquetaEnviar="Guardar"
      etiquetaGuardando="Guardando…"
    >
      <CampoTexto
        id="plantilla-area" etiqueta="Área" obligatorio maximoCaracteres={120}
        ayuda="Por ejemplo: Motricidad fina. Una plantilla nueva con un área nueva crea el área."
        valor={valores.area} onChange={setCampo('area')}
        error={errorDe('area')} deshabilitado={guardando}
      />
      <CampoTexto
        id="plantilla-descripcion" etiqueta="Texto del objetivo" obligatorio multilinea filas={4}
        maximoCaracteres={MAXIMO_CARACTERES_DESCRIPCION}
        ayuda="Qué se busca lograr, en positivo y observable. La terapeuta puede ajustarlo al crear el objetivo."
        valor={valores.descripcion} onChange={setCampo('descripcion')}
        error={errorDe('descripcion')} deshabilitado={guardando}
      />
    </ModalFormulario>
  );
}

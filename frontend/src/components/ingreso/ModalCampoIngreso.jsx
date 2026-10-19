// frontend/src/components/ingreso/ModalCampoIngreso.jsx
// Alta y edición de un campo del formulario de ingreso (administrador). La
// clave y el tipo no se cambian una vez creado el campo: las respuestas ya
// guardadas dependen de ellos.

import MenuItem from '@mui/material/MenuItem';

import CampoTexto from '../forms/CampoTexto.jsx';
import ModalFormulario from '../modal/ModalFormulario.jsx';
import { useFormularioModal } from '../../hooks/useFormularioModal.js';
import { crearCampoDeIngreso, editarCampoDeIngreso } from '../../services/ingresoService.js';

const TIPOS = [
  { valor: 'texto', etiqueta: 'Texto corto' },
  { valor: 'texto_largo', etiqueta: 'Texto largo' },
  { valor: 'fecha', etiqueta: 'Fecha' },
  { valor: 'opcion', etiqueta: 'Opción única' },
];

export default function ModalCampoIngreso({ abierto, etapa, campo, onCerrar, onGuardado }) {
  const edicion = Boolean(campo);
  const formulario = useFormularioModal({
    inicial: {
      clave: campo?.clave ?? '',
      etiqueta: campo?.etiqueta ?? '',
      ayuda: campo?.ayuda ?? '',
      tipo: campo?.tipo ?? 'texto_largo',
      opciones: (campo?.opciones ?? []).join('\n'),
      orden: campo?.orden ?? '',
    },
    obligatorios: edicion ? ['etiqueta'] : ['clave', 'etiqueta'],
    onEnviar: (v) => {
      const opciones = v.opciones.split('\n').map((o) => o.trim()).filter(Boolean);
      if (edicion) {
        return editarCampoDeIngreso(campo.id, {
          etiqueta: v.etiqueta, ayuda: v.ayuda, orden: v.orden === '' ? undefined : Number(v.orden),
          ...(campo.tipo === 'opcion' ? { opciones } : {}),
        });
      }
      return crearCampoDeIngreso({
        etapa: etapa.etapa, clave: v.clave, etiqueta: v.etiqueta, ayuda: v.ayuda,
        tipo: v.tipo, opciones, orden: v.orden === '' ? undefined : Number(v.orden),
      });
    },
    onExito: (respuesta) => {
      onCerrar?.();
      onGuardado?.(respuesta);
    },
    onCerrar,
  });
  const { valores, setCampo, errorDe, guardando } = formulario;
  const conOpciones = (edicion ? campo.tipo : valores.tipo) === 'opcion';

  return (
    <ModalFormulario
      abierto={abierto}
      titulo={edicion ? 'Editar campo' : 'Agregar campo'}
      subtitulo={etapa?.nombre ?? ''}
      guardando={guardando}
      errorServidor={formulario.errorServidor}
      tituloRechazo="No se pudo guardar el campo"
      confirmandoDescarte={formulario.confirmandoDescarte}
      onPedirCierre={formulario.pedirCierre}
      onSeguirEditando={formulario.seguirEditando}
      onDescartar={formulario.descartar}
      onEnviar={formulario.enviar}
      etiquetaEnviar="Guardar"
      etiquetaGuardando="Guardando…"
    >
      {!edicion && (
        <CampoTexto
          id="campo-clave" etiqueta="Clave" obligatorio maximoCaracteres={40}
          ayuda="Identificador interno: minúsculas, números y guion bajo. No se puede cambiar después."
          valor={valores.clave} onChange={setCampo('clave')}
          error={errorDe('clave')} deshabilitado={guardando}
        />
      )}
      <CampoTexto
        id="campo-etiqueta" etiqueta="Pregunta o título" obligatorio maximoCaracteres={150}
        valor={valores.etiqueta} onChange={setCampo('etiqueta')}
        error={errorDe('etiqueta')} deshabilitado={guardando}
      />
      <CampoTexto
        id="campo-ayuda" etiqueta="Texto de ayuda" maximoCaracteres={300}
        ayuda="Opcional. Se muestra debajo del campo."
        valor={valores.ayuda} onChange={setCampo('ayuda')}
        error={errorDe('ayuda')} deshabilitado={guardando}
      />
      {!edicion && (
        <CampoTexto
          id="campo-tipo" etiqueta="Tipo de campo" select
          valor={valores.tipo} onChange={setCampo('tipo')}
          error={errorDe('tipo')} deshabilitado={guardando}
        >
          {TIPOS.map((t) => <MenuItem key={t.valor} value={t.valor}>{t.etiqueta}</MenuItem>)}
        </CampoTexto>
      )}
      {conOpciones && (
        <CampoTexto
          id="campo-opciones" etiqueta="Opciones" multilinea filas={3}
          ayuda="Una opción por renglón (al menos dos)."
          valor={valores.opciones} onChange={setCampo('opciones')}
          error={errorDe('opciones')} deshabilitado={guardando}
        />
      )}
      <CampoTexto
        id="campo-orden" etiqueta="Orden" tipo="number" tabular
        ayuda="Opcional. Los campos se muestran de menor a mayor."
        valor={valores.orden} onChange={setCampo('orden')}
        error={errorDe('orden')} deshabilitado={guardando}
      />
    </ModalFormulario>
  );
}

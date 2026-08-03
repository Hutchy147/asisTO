// frontend/src/hooks/useFormularioModal.js
//
// Estado y ciclo de vida de un formulario dentro de un modal. Lo comparten
// los cuatro modales del sistema: alta de paciente, objetivo, sesión y
// evolución. Si algo de esto se reimplementa en un modal suelto, los
// cuatro empiezan a comportarse distinto.
//
// Resuelve las cuatro cosas del patrón:
//   1. guardando  -> deshabilitar campos, bloquear cierre, verbo en gerundio
//   2. rechazo    -> mensaje del servidor VERBATIM + campo culpable marcado
//   3. validación -> campos obligatorios antes de gastar un viaje al servidor
//   4. descarte   -> solo pregunta si hay algo cargado

import { useCallback, useMemo, useState } from 'react';

export const MENSAJE_CAMPO_OBLIGATORIO = 'Este campo es obligatorio.';

export function useFormularioModal({
  inicial = {},
  obligatorios = [],
  onEnviar,
  onExito,
  onCerrar,
  // Decide qué campo marcar ante un rechazo del servidor. Ver el comentario
  // en errorDe(): es presentación, no validación.
  campoDelRechazo = () => null,
}) {
  const [valores, setValores] = useState(inicial);
  const [sucio, setSucio] = useState(false);
  const [validado, setValidado] = useState(false);
  const [guardando, setGuardando] = useState(false);
  const [errorServidor, setErrorServidor] = useState(null);
  const [confirmandoDescarte, setConfirmandoDescarte] = useState(false);

  const reiniciar = useCallback(() => {
    setValores(inicial);
    setSucio(false);
    setValidado(false);
    setGuardando(false);
    setErrorServidor(null);
    setConfirmandoDescarte(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const setValor = useCallback((clave, valor) => {
    setValores((previos) => ({ ...previos, [clave]: valor }));
    setSucio(true);
    // Al corregir un campo se limpia el rechazo anterior: dejarlo puesto
    // haría que el usuario siga viendo un error que ya está resolviendo.
    setErrorServidor(null);
  }, []);

  const setCampo = useCallback(
    (clave) => (evento) => setValor(clave, evento?.target?.value ?? evento),
    [setValor]
  );

  const faltantes = useMemo(
    () => obligatorios.filter((clave) => !String(valores[clave] ?? '').trim()),
    [obligatorios, valores]
  );

  const campoRechazado = errorServidor ? campoDelRechazo(errorServidor) : null;

  /**
   * Error a mostrar en un campo.
   *
   * El campo marcado por el servidor gana sobre el de obligatorio: si el
   * servidor ya se pronunció, su veredicto es el que vale.
   */
  const errorDe = useCallback(
    (clave) => {
      if (campoRechazado === clave) return ' '; // marca sin repetir el texto
      if (validado && obligatorios.includes(clave) && !String(valores[clave] ?? '').trim()) {
        return MENSAJE_CAMPO_OBLIGATORIO;
      }
      return undefined;
    },
    [campoRechazado, validado, obligatorios, valores]
  );

  const enviar = useCallback(async () => {
    setValidado(true);
    setErrorServidor(null);

    // Validación previa: campos vacíos y formatos, nada más. Las reglas de
    // negocio las aplica la base y su mensaje se propaga tal cual.
    if (obligatorios.some((clave) => !String(valores[clave] ?? '').trim())) return;

    setGuardando(true);
    try {
      const resultado = await onEnviar(valores);
      reiniciar();
      onExito?.(resultado);
    } catch (error) {
      setErrorServidor(error);
    } finally {
      setGuardando(false);
    }
  }, [obligatorios, valores, onEnviar, onExito, reiniciar]);

  /** Cancelar o clic afuera. Solo interrumpe si hay algo cargado. */
  const pedirCierre = useCallback(() => {
    if (guardando) return; // mientras guarda no se cierra
    if (!sucio) {
      reiniciar();
      onCerrar?.();
      return;
    }
    setConfirmandoDescarte(true);
  }, [guardando, sucio, reiniciar, onCerrar]);

  const seguirEditando = useCallback(() => setConfirmandoDescarte(false), []);

  const descartar = useCallback(() => {
    reiniciar();
    onCerrar?.();
  }, [reiniciar, onCerrar]);

  return {
    valores,
    setValor,
    setCampo,
    sucio,
    validado,
    guardando,
    errorServidor,
    campoRechazado,
    faltantes,
    confirmandoDescarte,
    errorDe,
    enviar,
    pedirCierre,
    seguirEditando,
    descartar,
    reiniciar,
  };
}

// frontend/src/hooks/useEstadoEnUrl.js
// Estado de pantalla guardado en la URL (?clave=valor): la pestaña elegida, el
// paciente del portal, los filtros y la página de un listado. Así F5, el botón
// Atrás o un enlace copiado vuelven exactamente al mismo lugar.

import { useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';

/**
 * Como useState, pero el valor vive en el parámetro `clave` de la URL.
 * El valor por defecto no se escribe: la URL queda limpia mientras no se
 * cambie nada. Usa `replace` para no llenar el historial con cada clic.
 */
export function useEstadoEnUrl(clave, porDefecto = '') {
  const [params, setParams] = useSearchParams();
  const valor = params.get(clave) ?? porDefecto;

  const cambiar = useCallback((nuevo) => {
    setParams((actual) => {
      const siguiente = new URLSearchParams(actual);
      const texto = nuevo === null || nuevo === undefined ? '' : String(nuevo);
      if (texto === '' || texto === String(porDefecto)) siguiente.delete(clave);
      else siguiente.set(clave, texto);
      return siguiente;
    }, { replace: true });
  }, [clave, porDefecto, setParams]);

  return [valor, cambiar];
}

/**
 * Varios valores a la vez (filtros de un listado). `porDefecto` define las
 * claves y sus valores iniciales; los números se devuelven como número.
 */
export function useFiltrosEnUrl(porDefecto) {
  const [params, setParams] = useSearchParams();
  const filtros = {};
  Object.entries(porDefecto).forEach(([clave, base]) => {
    const crudo = params.get(clave);
    if (crudo === null) filtros[clave] = base;
    else if (typeof base === 'number') filtros[clave] = Number(crudo) || base;
    else filtros[clave] = crudo;
  });

  const cambiar = useCallback((actualizar) => {
    setParams((actual) => {
      const previos = {};
      Object.entries(porDefecto).forEach(([clave, base]) => {
        const crudo = actual.get(clave);
        previos[clave] = crudo === null ? base : (typeof base === 'number' ? Number(crudo) || base : crudo);
      });
      const nuevos = typeof actualizar === 'function' ? actualizar(previos) : actualizar;
      const siguiente = new URLSearchParams(actual);
      Object.entries(porDefecto).forEach(([clave, base]) => {
        const v = nuevos[clave];
        if (v === undefined || v === null || v === '' || String(v) === String(base)) siguiente.delete(clave);
        else siguiente.set(clave, String(v));
      });
      return siguiente;
    }, { replace: true });
    // porDefecto se arma en cada render del llamador: se compara por contenido.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(porDefecto), setParams]);

  return [filtros, cambiar];
}

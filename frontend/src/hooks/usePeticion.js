// frontend/src/hooks/usePeticion.js
// Estandariza el ciclo cargando / datos / error de una llamada a la API,
// para que las cuatro pantallas no lo reimplementen cada una a su manera.

import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * @param {Function} peticion  funcion async que devuelve los datos
 * @param {Array} dependencias cuando cambian, se vuelve a pedir
 * @param {Object} opciones    { inmediata: bool }
 */
export function usePeticion(peticion, dependencias = [], { inmediata = true } = {}) {
  const [datos, setDatos] = useState(null);
  const [cargando, setCargando] = useState(inmediata);
  const [error, setError] = useState(null);

  // Evita el "setState sobre componente desmontado" y, mas importante, que
  // una respuesta lenta pise a otra mas nueva cuando cambian los filtros.
  const peticionVigente = useRef(0);
  const montado = useRef(true);

  useEffect(() => {
    montado.current = true;
    return () => {
      montado.current = false;
    };
  }, []);

  const ejecutar = useCallback(async () => {
    const identificador = ++peticionVigente.current;
    setCargando(true);
    setError(null);

    try {
      const resultado = await peticion();
      if (montado.current && identificador === peticionVigente.current) {
        setDatos(resultado);
      }
      return resultado;
    } catch (fallo) {
      if (montado.current && identificador === peticionVigente.current) {
        // Se guarda el ErrorApi entero: la pantalla decide segun status y
        // codigo, y muestra fallo.message tal cual vino del servidor.
        setError(fallo);
      }
      return null;
    } finally {
      if (montado.current && identificador === peticionVigente.current) {
        setCargando(false);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, dependencias);

  useEffect(() => {
    if (inmediata) ejecutar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ejecutar, inmediata]);

  return { datos, cargando, error, recargar: ejecutar, setDatos };
}

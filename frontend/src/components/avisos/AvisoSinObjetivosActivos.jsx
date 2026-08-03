// frontend/src/components/avisos/AvisoSinObjetivosActivos.jsx

import Aviso from '../estado/Aviso.jsx';

/**
 * El paciente no tiene objetivos activos: no hay contra que calificar.
 *
 * El backend devuelve 409 con este mismo motivo si se intenta igual, pero
 * conviene mostrarlo antes: un formulario de evolucion sin ninguna opcion
 * para elegir no se entiende.
 */
export default function AvisoSinObjetivosActivos({ objetivosActivos, onCrearObjetivo }) {
  if (objetivosActivos === null || objetivosActivos === undefined) return null;
  if (objetivosActivos.length > 0) return null;

  return (
    <Aviso severidad="warning" titulo="El paciente no tiene objetivos activos">
      No hay contra qué calificar todavía. Hay que crear al menos un
      objetivo antes de poder cargar la evolución.
      {onCrearObjetivo && (
        <>
          {' '}
          <a
            href="#crear-objetivo"
            onClick={(e) => {
              e.preventDefault();
              onCrearObjetivo();
            }}
          >
            Crear un objetivo
          </a>
        </>
      )}
    </Aviso>
  );
}

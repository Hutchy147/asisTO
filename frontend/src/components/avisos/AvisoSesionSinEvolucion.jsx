// frontend/src/components/avisos/AvisoSesionSinEvolucion.jsx

import Aviso from '../estado/Aviso.jsx';

/**
 * La sesión está (o va a quedar) marcada como ausencia, así que no admite
 * evolución. Es la regla 2.
 *
 * Dos modos, porque el momento cambia el tiempo verbal y lo que sirve
 * ofrecer:
 *
 *  - `registro`: se está eligiendo el estado en el alta. Todavía se puede
 *    cambiar de opinión, así que se ofrece la salida de "incompleta".
 *  - `consulta`: la sesión ya existe. No hay nada que ofrecer, solo
 *    explicar por qué no aparece el formulario.
 *
 * El tono es informativo y no de advertencia en los dos casos: una
 * ausencia es un dato clínico normal, no un problema que alguien tenga
 * que resolver.
 */
export default function AvisoSesionSinEvolucion({ sesion, modo = 'consulta' }) {
  // En modo registro lo decide el estado elegido, no una sesión guardada
  if (modo === 'consulta' && (!sesion || sesion.admite_evolucion)) return null;

  if (modo === 'registro') {
    return (
      <Aviso severidad="info" titulo="Esta sesión no va a poder tener evolución">
        El paciente no asistió, así que no hay nada que calificar: los
        objetivos no se puntúan en una ausencia. Si en realidad asistió y la
        sesión se cortó, elegí <strong>Incompleta</strong>.
      </Aviso>
    );
  }

  return (
    <Aviso severidad="info" titulo="Esta sesión no lleva evolución">
      La sesión está marcada como <strong>ausencia</strong>: el paciente no
      asistió, así que no hay nada que evaluar. No figura como pendiente ni
      cuenta como trabajo sin completar.
    </Aviso>
  );
}

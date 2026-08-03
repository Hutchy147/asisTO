// frontend/src/components/avisos/AvisoSesionSinEvolucion.jsx

import Aviso from '../estado/Aviso.jsx';

/**
 * La sesion no admite evolucion porque esta marcada como ausencia
 * (regla 2). No es que falte cargarla: no puede tenerla.
 *
 * Se muestra en lugar del formulario. Dejar el formulario visible con un
 * boton que siempre falla es peor que no mostrarlo.
 */
export default function AvisoSesionSinEvolucion({ sesion }) {
  if (!sesion || sesion.admite_evolucion) return null;

  return (
    <Aviso severidad="info" titulo="Esta sesión no lleva evolución">
      La sesión está marcada como <strong>ausencia</strong>: el paciente no
      asistió, así que no hay nada que evaluar. No figura como pendiente ni
      cuenta como trabajo sin completar.
    </Aviso>
  );
}

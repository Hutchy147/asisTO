// frontend/src/components/avisos/AvisoSesionDeOtroTerapeuta.jsx

import Aviso from '../estado/Aviso.jsx';

/**
 * La sesion la atendio otro terapeuta (`es_propia: false`).
 *
 * La LECTURA esta permitida: en esta entrega todos los terapeutas ven
 * todos los pacientes. Lo que no se permite es cargarle evolucion, porque
 * una evolucion es la valoracion clinica de quien atendio y cargarla en
 * nombre de otro falsea la autoria de la historia clinica.
 */
export default function AvisoSesionDeOtroTerapeuta({ sesion, terapeuta }) {
  if (!sesion || sesion.es_propia !== false) return null;

  const nombre = terapeuta?.nombre_completo;

  return (
    <Aviso severidad="info" titulo="Sesión de otro terapeuta">
      {nombre ? <>Esta sesión la atendió <strong>{nombre}</strong>.</> : 'Esta sesión la atendió otro terapeuta.'}
      {' '}Podés consultarla, pero la evolución solo puede cargarla quien la
      atendió.
    </Aviso>
  );
}

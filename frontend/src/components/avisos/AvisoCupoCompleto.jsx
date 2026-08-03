// frontend/src/components/avisos/AvisoCupoCompleto.jsx

import Aviso from '../estado/Aviso.jsx';

/**
 * El paciente llego al tope de 4 objetivos activos.
 *
 * Se muestra ANTES de intentar el alta, con el dato que ya viene en
 * `cupo` del listado de objetivos. La validacion real la hace el trigger:
 * esto solo evita ofrecer una accion que se sabe que va a fallar.
 *
 * El mensaje explica la salida (archivar uno) porque el limite no es un
 * tope arbitrario: un objetivo archivado no consume cupo y su historia se
 * conserva.
 */
export default function AvisoCupoCompleto({ cupo }) {
  if (!cupo || cupo.disponibles > 0) return null;

  return (
    <Aviso severidad="warning" titulo="Sin cupo para objetivos nuevos">
      El paciente tiene {cupo.usados} de {cupo.maximo} objetivos activos.
      Para agregar otro hay que archivar alguno de los actuales: archivar no
      borra nada, las evoluciones cargadas se conservan y el objetivo deja
      de ocupar cupo.
    </Aviso>
  );
}

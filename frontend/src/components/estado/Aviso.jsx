// frontend/src/components/estado/Aviso.jsx

import Alert from '@mui/material/Alert';
import AlertTitle from '@mui/material/AlertTitle';

/**
 * Aviso en linea para los estados particulares del dominio (cupo lleno,
 * sesion que no admite evolucion, sesion de otro terapeuta).
 *
 * Base comun de los componentes de components/avisos/.
 */
export default function Aviso({ severidad = 'info', titulo, children, accion }) {
  return (
    // texto-libre en el cuerpo: varios avisos interpolan un nombre de la base
    // ("Esta sesión la atendió <b>X</b>", "Los N objetivos activos de X"), y un
    // nombre sin espacios se sale del Alert. Se pone acá una sola vez y lo
    // heredan los cuatro componentes de components/avisos/.
    <Alert severity={severidad} action={accion} className="texto-libre" sx={{ mb: 2 }}>
      {titulo && <AlertTitle>{titulo}</AlertTitle>}
      {children}
    </Alert>
  );
}

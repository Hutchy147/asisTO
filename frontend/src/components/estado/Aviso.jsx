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
    <Alert severity={severidad} action={accion} sx={{ mb: 2 }}>
      {titulo && <AlertTitle>{titulo}</AlertTitle>}
      {children}
    </Alert>
  );
}

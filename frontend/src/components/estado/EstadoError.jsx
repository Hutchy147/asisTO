// frontend/src/components/estado/EstadoError.jsx

import Alert from '@mui/material/Alert';
import AlertTitle from '@mui/material/AlertTitle';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';

/**
 * Error al traer datos.
 *
 * El mensaje que se muestra es el que devolvio el servidor, SIN reescribir.
 * El backend los redacta en castellano y para una persona; varios salen de
 * los triggers de la base. Ver el comentario de ErrorApi en services/api.js.
 *
 * Solo se elige el titulo segun el tipo de error, para dar contexto.
 */
export default function EstadoError({ error, onReintentar }) {
  if (!error) return null;

  const titulo = (() => {
    if (error.esDeRed) return 'Sin conexión con el servidor';
    if (error.esDePermisos) return 'No tiene permiso';
    if (error.esNoEncontrado) return 'No encontrado';
    return 'No se pudo completar la operación';
  })();

  // Reintentar solo sirve si el problema puede haber sido transitorio.
  // Ante un 403 o un 404, volver a pedir da exactamente lo mismo.
  const permiteReintentar =
    Boolean(onReintentar) && !error.esDePermisos && !error.esNoEncontrado;

  return (
    <Box sx={{ p: 2 }}>
      <Alert
        severity={error.esDePermisos ? 'warning' : 'error'}
        action={
          permiteReintentar ? (
            <Button color="inherit" size="small" onClick={onReintentar}>
              Reintentar
            </Button>
          ) : null
        }
      >
        <AlertTitle>{titulo}</AlertTitle>
        {error.message}
      </Alert>
    </Box>
  );
}

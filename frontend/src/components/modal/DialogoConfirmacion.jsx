// frontend/src/components/modal/DialogoConfirmacion.jsx
// Confirmación de una acción que no se puede deshacer desde la interfaz.

import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import Typography from '@mui/material/Typography';

export default function DialogoConfirmacion({
  abierto,
  titulo,
  children,
  etiquetaConfirmar = 'Confirmar',
  etiquetaProcesando = 'Procesando…',
  procesando = false,
  // Bloquea el botón sin que haya nada en curso. Es para el caso en que el
  // diálogo todavía no puede decir QUÉ va a pasar —porque está buscando ese
  // dato— y confirmar a ciegas sería justo lo que la confirmación evita.
  // Distinto de `procesando`, que además bloquea Cancelar y el Escape.
  confirmarDeshabilitado = false,
  // Contenido interactivo (un campo de texto, por ejemplo) debajo del texto.
  // Va aparte de `children`, que es el texto de la confirmación.
  extra = null,
  onConfirmar,
  onCancelar,
}) {
  return (
    <Dialog
      open={abierto}
      onClose={procesando ? undefined : onCancelar}
      disableEscapeKeyDown={procesando}
      PaperProps={{ sx: { width: 480, maxWidth: '95vw' } }}
    >
      <Box sx={{ px: 3, pt: 2.5 }}>
        <Typography variant="h5">{titulo}</Typography>
      </Box>
      <DialogContent sx={{ px: 3, py: 2 }}>
        {/* div y no p: hay confirmaciones que traen una lista, y un <ul> dentro de un <p> es HTML inválido. */}
        <Typography component="div" variant="body2" color="text.secondary" sx={{ lineHeight: 1.6 }}>
          {children}
        </Typography>
        {extra}
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2.5, gap: 1 }}>
        <Button variant="outlined" onClick={onCancelar} disabled={procesando}>
          Cancelar
        </Button>
        <Button
          variant="contained"
          onClick={onConfirmar}
          disabled={procesando || confirmarDeshabilitado}
          startIcon={procesando ? <CircularProgress size={14} color="inherit" thickness={5} /> : null}
        >
          {procesando ? etiquetaProcesando : etiquetaConfirmar}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

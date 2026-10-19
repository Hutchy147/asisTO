// frontend/src/components/familiares/DialogoContrasenaTemporal.jsx
// Muestra UNA sola vez la contraseña temporal de una cuenta recién creada.
// El servidor no la guarda en claro: si se cierra sin copiarla, hay que
// restablecerla desde "¿Olvidó su contraseña?".

import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import Typography from '@mui/material/Typography';

export default function DialogoContrasenaTemporal({ datos, onCerrar }) {
  if (!datos) return null;
  const { familiar, contrasena } = datos;

  return (
    <Dialog open onClose={onCerrar} PaperProps={{ sx: { width: 480, maxWidth: '95vw' } }}>
      <Box sx={{ px: 3, pt: 2.5 }}>
        <Typography variant="h5">Cuenta creada</Typography>
      </Box>
      <DialogContent sx={{ px: 3, py: 2 }}>
        <Typography variant="body2" sx={{ mb: 1.5 }}>
          Se creó la cuenta de <strong className="texto-libre">{familiar.nombre_completo}</strong>.
          Entréguele estos datos de acceso.
        </Typography>
        <Box
          sx={(t) => ({
            border: `1px solid ${t.palette.superficie.borde}`,
            borderRadius: `${t.formas.md}px`,
            p: 1.5, mb: 1.5,
          })}
        >
          <Typography variant="caption" color="text.secondary">Usuario</Typography>
          <Typography className="texto-libre" sx={{ mb: 1 }}>{familiar.email}</Typography>
          <Typography variant="caption" color="text.secondary">Contraseña temporal</Typography>
          <Typography className="tabular" data-testid="contrasena-temporal" sx={{ fontSize: 18, letterSpacing: 1 }}>
            {contrasena}
          </Typography>
        </Box>
        <Alert severity="warning">
          Esta contraseña se muestra una sola vez. Si se pierde, la persona puede
          restablecerla desde la opción de recuperación de contraseña.
        </Alert>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button variant="contained" onClick={onCerrar}>Entendido</Button>
      </DialogActions>
    </Dialog>
  );
}

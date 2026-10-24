// frontend/src/components/admin/DatosDeEntrega.jsx
// Lo que el administrador le entrega a la persona: correo y clave. La clave
// se muestra UNA vez, acá; después no hay forma de verla (solo restablecerla).

import { useState } from 'react';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';

export default function DatosDeEntrega({ datos, onCerrar }) {
  const [copiado, setCopiado] = useState(false);
  if (!datos) return null;

  const texto = `Ingreso a AsisTO\nCorreo: ${datos.email}\nContraseña: ${datos.contrasena}`;

  const copiar = async () => {
    try {
      await navigator.clipboard.writeText(texto);
      setCopiado(true);
    } catch {
      setCopiado(false); // sin portapapeles: los campos de abajo se pueden seleccionar
    }
  };

  return (
    <Dialog open onClose={onCerrar} PaperProps={{ sx: { width: 480, maxWidth: '95vw' } }}>
      <Box sx={{ px: 3, pt: 2.5 }}>
        <Typography variant="h5">{datos.titulo}</Typography>
        <Typography variant="body2" color="text.secondary" className="texto-libre">{datos.persona}</Typography>
      </Box>
      <DialogContent sx={{ px: 3, py: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
        <Alert severity="warning">
          Anote o copie estos datos ahora: la contraseña no se vuelve a mostrar. Si se pierde,
          se restablece desde esta misma pantalla.
        </Alert>
        <TextField label="Correo" size="small" value={datos.email} InputProps={{ readOnly: true }} fullWidth />
        <TextField
          label="Contraseña" size="small" value={datos.contrasena} fullWidth
          InputProps={{ readOnly: true, sx: { fontFamily: 'monospace', letterSpacing: 1 } }}
          onFocus={(e) => e.target.select()}
        />
        <Typography variant="caption" color="text.secondary">
          Recomiende a la persona cambiarla al entrar por primera vez (pantalla de ingreso,
          «¿Olvidó su contraseña?»), porque usted la conoce.
        </Typography>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2.5, gap: 1 }}>
        <Button variant="outlined" onClick={copiar}>
          {copiado ? 'Copiado' : 'Copiar correo y contraseña'}
        </Button>
        <Button variant="contained" onClick={onCerrar}>Listo</Button>
      </DialogActions>
    </Dialog>
  );
}

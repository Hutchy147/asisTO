// frontend/src/components/modal/ModalFormulario.jsx
//
// Marco de los cuatro modales de formulario del sistema. Lo que define acá
// se aplica a alta de paciente, objetivo, sesión y evolución por igual.
//
// Se usa junto con useFormularioModal, que aporta el estado.

import Alert from '@mui/material/Alert';
import AlertTitle from '@mui/material/AlertTitle';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import Typography from '@mui/material/Typography';

export default function ModalFormulario({
  abierto,
  titulo,
  subtitulo,
  ancho = 560,
  guardando,
  errorServidor,
  tituloRechazo = 'El servidor rechazó los datos',
  confirmandoDescarte,
  onPedirCierre,
  onSeguirEditando,
  onDescartar,
  onEnviar,
  etiquetaEnviar,
  etiquetaGuardando,
  enviarDeshabilitado = false,
  // El modal no puede guardar nada: el pie se reduce a cerrar. Se usa
  // cuando lo que falta no se resuelve desde acá (un paciente sin
  // objetivos activos, una sesión de otro terapeuta). Ofrecer "Guardar"
  // sería ofrecer algo imposible.
  soloCerrar = false,
  children,
}) {
  return (
    <Dialog
      open={abierto}
      // Mientras guarda no se cierra por Escape ni por clic afuera: la
      // request ya salió y cerrar dejaría al usuario sin saber si terminó.
      disableEscapeKeyDown={guardando}
      onClose={onPedirCierre}
      maxWidth={false}
      PaperProps={{ sx: { width: ancho, maxWidth: '95vw' } }}
      aria-labelledby="modal-titulo"
    >
      <Box
        sx={(t) => ({
          px: 3,
          pt: 2.5,
          pb: 2,
          borderBottom: `1px solid ${t.palette.superficie.borde}`,
        })}
      >
        <Typography variant="h4" id="modal-titulo">
          {titulo}
        </Typography>
        {subtitulo && (
          <Typography variant="caption" sx={{ display: 'block', mt: 0.25 }}>
            {subtitulo}
          </Typography>
        )}
      </Box>

      <DialogContent sx={{ px: 3, py: 2.5 }}>
        {errorServidor && (
          <Alert severity="error" sx={{ mb: 2.5 }}>
            <AlertTitle>{tituloRechazo}</AlertTitle>
            {/* Mensaje del servidor TAL CUAL. Está redactado en castellano
                y para una persona; varios salen de los triggers de la base.
                Reescribirlo acá solo puede empeorarlo y lo desincroniza
                cuando cambia del otro lado. */}
            {errorServidor.message}
          </Alert>
        )}

        <Box
          component="form"
          noValidate
          onSubmit={(evento) => {
            evento.preventDefault();
            onEnviar();
          }}
          sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}
        >
          {children}
          {/* Permite enviar con Enter sin mostrar un segundo botón */}
          <button type="submit" hidden aria-hidden="true" tabIndex={-1} />
        </Box>
      </DialogContent>

      <DialogActions
        sx={(t) => ({
          px: 3,
          py: 2,
          gap: 1,
          borderTop: `1px solid ${t.palette.superficie.borde}`,
        })}
      >
        {soloCerrar ? (
          <Button variant="outlined" onClick={onPedirCierre}>
            Cerrar
          </Button>
        ) : confirmandoDescarte ? (
          <>
            <Typography
              variant="body2"
              color="text.secondary"
              sx={{ flex: 1, alignSelf: 'center', lineHeight: 1.4 }}
            >
              Cargaste datos sin guardar. Si cerrás ahora se pierden.
            </Typography>
            <Button variant="outlined" onClick={onSeguirEditando}>
              Seguir editando
            </Button>
            <Button color="error" variant="contained" onClick={onDescartar}>
              Descartar
            </Button>
          </>
        ) : (
          <>
            <Button variant="outlined" disabled={guardando} onClick={onPedirCierre}>
              Cancelar
            </Button>
            <Button
              variant="contained"
              disabled={guardando || enviarDeshabilitado}
              onClick={onEnviar}
              startIcon={
                guardando ? <CircularProgress size={14} color="inherit" thickness={5} /> : null
              }
            >
              {guardando ? etiquetaGuardando : etiquetaEnviar}
            </Button>
          </>
        )}
      </DialogActions>
    </Dialog>
  );
}

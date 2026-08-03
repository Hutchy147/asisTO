// frontend/src/components/forms/CampoTexto.jsx
// Campo de texto de los formularios. Envuelve TextField para que la
// etiqueta, el asterisco de obligatorio, la ayuda y el error se vean igual
// en los cuatro modales.

import TextField from '@mui/material/TextField';

export default function CampoTexto({
  id,
  etiqueta,
  valor,
  onChange,
  obligatorio = false,
  ayuda,
  error,
  deshabilitado = false,
  tipo = 'text',
  multilinea = false,
  filas = 3,
  tabular = false,
  ...resto
}) {
  // error === ' ' marca el campo sin repetir texto: lo usa el rechazo del
  // servidor, cuyo mensaje ya se muestra completo arriba del formulario.
  const tieneError = Boolean(error);
  const textoAyuda = tieneError && error.trim() ? error : ayuda;

  return (
    <TextField
      id={id}
      label={etiqueta}
      value={valor ?? ''}
      onChange={onChange}
      required={obligatorio}
      error={tieneError}
      helperText={textoAyuda}
      disabled={deshabilitado}
      type={tipo}
      multiline={multilinea}
      minRows={multilinea ? filas : undefined}
      fullWidth
      size="small"
      // Las fechas y los números de historia se leen mejor con cifras de
      // ancho fijo.
      inputProps={{ className: tabular ? 'tabular' : undefined, ...(resto.inputProps ?? {}) }}
      InputLabelProps={tipo === 'date' ? { shrink: true } : undefined}
      {...resto}
    />
  );
}

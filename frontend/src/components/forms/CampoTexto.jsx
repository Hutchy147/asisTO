// frontend/src/components/forms/CampoTexto.jsx
// Campo de texto de los formularios. Envuelve TextField para que la
// etiqueta, el asterisco de obligatorio, la ayuda y el error se vean igual
// en los cuatro modales.

import Box from '@mui/material/Box';
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
  // Un solo prop gobierna el tope duro y el contador. Antes el llamador
  // pasaba `inputProps={{ maxLength }}` y escribia el numero otra vez en el
  // texto de ayuda: dos lugares que podian decir cosas distintas, y de hecho
  // las dijeron. Con esto el numero se escribe una vez.
  maximoCaracteres,
  ...resto
}) {
  // error === ' ' marca el campo sin repetir texto: lo usa el rechazo del
  // servidor, cuyo mensaje ya se muestra completo arriba del formulario.
  const tieneError = Boolean(error);
  const textoAyuda = tieneError && error.trim() ? error : ayuda;

  const usados = (valor ?? '').length;
  const conContador = Number.isFinite(maximoCaracteres);
  // Sin margen: el navegador corta al llegar al tope, y ese es exactamente el
  // momento en que el contador tiene que estar mirado. No es un error —el
  // texto sigue siendo valido— asi que no se usa color de alarma.
  const enElTope = conContador && usados >= maximoCaracteres;

  const ayudaConContador = conContador ? (
    <Box component="span" sx={{ display: 'flex', gap: 1, justifyContent: 'space-between' }}>
      <Box component="span">{textoAyuda}</Box>
      <Box
        component="span"
        className="tabular"
        sx={(t) => ({
          flex: 'none',
          whiteSpace: 'nowrap',
          color: enElTope ? t.palette.text.primary : t.palette.text.secondary,
          fontWeight: enElTope ? 500 : 400,
        })}
      >
        {usados}/{maximoCaracteres}
      </Box>
    </Box>
  ) : (
    textoAyuda
  );

  return (
    <TextField
      id={id}
      label={etiqueta}
      value={valor ?? ''}
      onChange={onChange}
      required={obligatorio}
      error={tieneError}
      helperText={ayudaConContador}
      disabled={deshabilitado}
      type={tipo}
      multiline={multilinea}
      minRows={multilinea ? filas : undefined}
      fullWidth
      size="small"
      {...resto}
      // Después del spread a propósito: si `resto` trae su propio
      // inputProps, se combinan en vez de pisarse. Al revés, pasar
      // inputProps desde afuera borraba la clase tabular sin aviso.
      //
      // maxLength va PRIMERO para que un inputProps del llamador todavía
      // pueda pisarlo si algún caso lo necesita, pero el camino normal es
      // pasar `maximoCaracteres` y no tocar inputProps.
      inputProps={{
        className: tabular ? 'tabular' : undefined,
        ...(conContador ? { maxLength: maximoCaracteres } : {}),
        ...(resto.inputProps ?? {}),
      }}
      InputLabelProps={
        tipo === 'date' || tipo === 'time' ? { shrink: true } : resto.InputLabelProps
      }
    />
  );
}

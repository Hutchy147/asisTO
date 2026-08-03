// frontend/src/components/data/AccountFlag.jsx

import Box from '@mui/material/Box';

/**
 * Si el paciente tiene o no cuenta para entrar al sistema.
 *
 * Los dos casos se dibujan con el MISMO peso y en el mismo gris. No tener
 * cuenta es una situacion normal —la mayoria de los pacientes son menores—
 * y no un dato faltante ni un error: marcarlo en rojo o con un icono de
 * alerta seria mentir sobre el estado del registro.
 */
export default function AccountFlag({ tieneCuenta }) {
  return (
    <Box
      component="span"
      sx={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 0.75,
        fontSize: 13,
        color: 'text.secondary',
        whiteSpace: 'nowrap',
      }}
    >
      <Box
        component="i"
        aria-hidden="true"
        sx={(t) => ({
          width: 8,
          height: 8,
          borderRadius: '50%',
          flex: 'none',
          backgroundColor: tieneCuenta ? t.palette.primary.light : 'transparent',
          boxShadow: tieneCuenta ? 'none' : `inset 0 0 0 1.5px ${t.palette.text.disabled}`,
        })}
      />
      {tieneCuenta ? 'Con cuenta' : 'Sin cuenta'}
    </Box>
  );
}

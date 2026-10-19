// frontend/src/components/ingreso/FormularioEtapa.jsx
// Formulario de una etapa del ingreso. Los campos vienen del servidor
// (formulario configurable): acá no hay ninguna pregunta escrita a mano.

import { useState } from 'react';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import MenuItem from '@mui/material/MenuItem';

import CampoTexto from '../forms/CampoTexto.jsx';

function inicial(campos) {
  return Object.fromEntries(campos.map((c) => [c.clave, c.valor ?? '']));
}

export default function FormularioEtapa({ etapa, editable, onGuardar, onCerrar, onReabrir }) {
  const [valores, setValores] = useState(() => inicial(etapa.campos));
  const [sucio, setSucio] = useState(false);
  const [trabajando, setTrabajando] = useState(false);
  const [error, setError] = useState(null);
  const cerrada = etapa.estado === 'cerrada';
  const bloqueado = !editable || cerrada || trabajando;

  const cambiar = (clave) => (evento) => {
    setValores((previos) => ({ ...previos, [clave]: evento.target.value }));
    setSucio(true);
    setError(null);
  };

  const ejecutar = async (accion, alExito) => {
    setTrabajando(true);
    setError(null);
    try {
      await accion();
      alExito?.();
    } catch (fallo) {
      setError(fallo);
    } finally {
      setTrabajando(false);
    }
  };

  const guardar = () => ejecutar(() => onGuardar(valores), () => setSucio(false));
  // Cerrar guarda primero lo que haya en pantalla: así lo escrito nunca
  // queda fuera del cierre.
  const cerrar = () => ejecutar(async () => {
    if (sucio) await onGuardar(valores);
    await onCerrar();
  }, () => setSucio(false));

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, p: 2.25 }}>
      {cerrada && (
        <Alert severity="info">
          Esta etapa está cerrada. Para modificarla, reábrala primero.
        </Alert>
      )}
      {error && <Alert severity="error">{error.message}</Alert>}

      {etapa.campos.map((campo) => (
        <CampoTexto
          key={campo.clave}
          id={`ingreso-${etapa.etapa}-${campo.clave}`}
          etiqueta={campo.etiqueta}
          obligatorio={campo.obligatorio}
          ayuda={campo.ayuda || undefined}
          tipo={campo.tipo === 'fecha' ? 'date' : 'text'}
          multilinea={campo.tipo === 'texto_largo'}
          filas={3}
          select={campo.tipo === 'opcion'}
          maximoCaracteres={campo.tipo === 'texto' || campo.tipo === 'texto_largo' ? 4000 : undefined}
          valor={valores[campo.clave]}
          onChange={cambiar(campo.clave)}
          error={error?.campo === campo.clave ? ' ' : undefined}
          deshabilitado={bloqueado}
          tabular={campo.tipo === 'fecha'}
        >
          {campo.tipo === 'opcion' && [
            <MenuItem key="vacio" value=""><em>Sin elegir</em></MenuItem>,
            ...campo.opciones.map((o) => <MenuItem key={o} value={o}>{o}</MenuItem>),
          ]}
        </CampoTexto>
      ))}

      {editable && (
        <Box sx={{ display: 'flex', gap: 1, justifyContent: 'flex-end', flexWrap: 'wrap' }}>
          {cerrada ? (
            <Button variant="outlined" disabled={trabajando} onClick={() => ejecutar(onReabrir)}>
              Reabrir etapa
            </Button>
          ) : (
            <>
              <Button variant="outlined" disabled={trabajando || !sucio} onClick={guardar}>
                {trabajando ? 'Guardando…' : 'Guardar'}
              </Button>
              <Button variant="contained" disabled={trabajando} onClick={cerrar}>
                Cerrar etapa
              </Button>
            </>
          )}
        </Box>
      )}
    </Box>
  );
}

// frontend/src/components/admin/CampoClave.jsx
// Clave que el administrador elige para entregarle a la persona. Se ve en
// pantalla (la va a dictar o copiar) y se puede generar una al azar.

import { useState } from 'react';
import Button from '@mui/material/Button';

import CampoTexto from '../forms/CampoTexto.jsx';
import { obtenerContrasenaSugerida } from '../../services/usuariosService.js';

export default function CampoClave({ id, valor, onChange, error, deshabilitado }) {
  const [generando, setGenerando] = useState(false);
  const [falla, setFalla] = useState('');

  const generar = async () => {
    setGenerando(true);
    setFalla('');
    try {
      const { contrasena } = await obtenerContrasenaSugerida();
      onChange(contrasena);
    } catch (fallo) {
      setFalla(fallo.message || 'No se pudo generar una clave.');
    } finally {
      setGenerando(false);
    }
  };

  return (
    <CampoTexto
      id={id}
      etiqueta="Contraseña"
      obligatorio
      valor={valor}
      onChange={(e) => onChange(e.target.value)}
      error={error || (falla ? ' ' : undefined)}
      ayuda={falla || 'Mínimo 8 caracteres, con letras y números. Se la entrega usted a la persona; no se vuelve a mostrar.'}
      deshabilitado={deshabilitado || generando}
      autoComplete="off"
      InputProps={{
        endAdornment: (
          <Button size="small" onClick={generar} disabled={deshabilitado || generando} sx={{ whiteSpace: 'nowrap' }}>
            {generando ? 'Generando…' : 'Generar una'}
          </Button>
        ),
      }}
    />
  );
}

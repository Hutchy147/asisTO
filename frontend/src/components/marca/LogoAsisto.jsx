// frontend/src/components/marca/LogoAsisto.jsx
// Marca oficial de AsisTO. Los archivos viven en frontend/public:
//   logo.png     logo completo (isotipo + palabra), fondo transparente
//   isotipo.png  solo el isotipo
// Para cambiar la marca alcanza con reemplazar esos dos archivos.

import Box from '@mui/material/Box';

export function Isotipo({ alto = 48 }) {
  return <Box component="img" src="/isotipo.png" alt="AsisTO" sx={{ height: alto, width: 'auto', display: 'block' }} />;
}

export default function LogoAsisto({ alto = 72 }) {
  return <Box component="img" src="/logo.png" alt="AsisTO" sx={{ height: alto, width: 'auto', maxWidth: '100%', display: 'block' }} />;
}

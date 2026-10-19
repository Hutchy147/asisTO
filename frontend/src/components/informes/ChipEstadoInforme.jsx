// frontend/src/components/informes/ChipEstadoInforme.jsx
// Estado de un informe: borrador, publicado o reemplazado.

import Chip from '@mui/material/Chip';

import { ETIQUETA_ESTADO_INFORME } from '../../services/informesService.js';

const COLOR = { borrador: 'warning', final: 'success', reemplazado: 'default' };

export default function ChipEstadoInforme({ estado }) {
  return (
    <Chip
      size="small"
      color={COLOR[estado] ?? 'default'}
      variant={estado === 'reemplazado' ? 'outlined' : 'filled'}
      label={ETIQUETA_ESTADO_INFORME[estado] ?? estado}
    />
  );
}

// frontend/src/components/evoluciones/TendenciasObjetivos.jsx
// Tendencia por objetivo y comparación entre dos períodos iguales (Entrega 5).
// Todo en palabras: la escala del producto no muestra números ni porcentajes.
// El criterio (cuántas calificaciones hacen falta y qué se considera cambio)
// lo decide la base, en p_tendencia_paciente; acá solo se muestra.

import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import MenuItem from '@mui/material/MenuItem';
import Typography from '@mui/material/Typography';

import DataTable from '../data/DataTable.jsx';
import { Cargando, EstadoError } from '../estado/index.js';
import CampoTexto from '../forms/CampoTexto.jsx';
import { useState } from 'react';
import { usePeticion } from '../../hooks/usePeticion.js';
import { etiquetaDeValor } from '../../services/evolucionesService.js';
import {
  ETIQUETA_CAMBIO, ETIQUETA_TENDENCIA, obtenerTendencias, PERIODO_TENDENCIA_POR_DEFECTO,
  PERIODOS_TENDENCIA,
} from '../../services/tendenciasService.js';
import { formatearFecha } from '../../utils/fechas.js';

const COLOR_TENDENCIA = {
  mejora: 'success', se_mantiene: 'default', retrocede: 'warning', sin_datos: 'default',
};
const COLOR_CAMBIO = {
  mejoro: 'success', igual: 'default', retrocedio: 'warning', sin_datos: 'default',
};

export default function TendenciasObjetivos({ idPaciente }) {
  const [dias, setDias] = useState(PERIODO_TENDENCIA_POR_DEFECTO);
  const tendencias = usePeticion(() => obtenerTendencias(idPaciente, dias), [idPaciente, dias]);
  const datos = tendencias.datos;

  const columnas = [
    {
      clave: 'objetivo', etiqueta: 'Objetivo',
      render: (o) => (
        <Box sx={{ opacity: o.activo ? 1 : 0.6 }}>
          <span className="texto-libre">{o.descripcion}</span>
          {!o.activo && <Chip size="small" label="Archivado" sx={{ ml: 1 }} />}
        </Box>
      ),
    },
    {
      clave: 'tendencia', etiqueta: 'Tendencia en el período', ancho: 210,
      render: (o) => (
        <Chip
          size="small" variant={o.tendencia === 'sin_datos' ? 'outlined' : 'filled'}
          color={COLOR_TENDENCIA[o.tendencia]} label={ETIQUETA_TENDENCIA[o.tendencia]}
        />
      ),
    },
    {
      clave: 'anterior', etiqueta: 'Período anterior', ancho: 150,
      render: (o) => etiquetaDeValor(o.nivel_anterior) ?? '—',
    },
    {
      clave: 'actual', etiqueta: 'Período actual', ancho: 150,
      render: (o) => etiquetaDeValor(o.nivel_actual) ?? '—',
    },
    {
      clave: 'cambio', etiqueta: 'Comparación', ancho: 200,
      render: (o) => (
        <Chip
          size="small" variant={o.cambio === 'sin_datos' ? 'outlined' : 'filled'}
          color={COLOR_CAMBIO[o.cambio]} label={ETIQUETA_CAMBIO[o.cambio]}
        />
      ),
    },
  ];

  return (
    <Box data-testid="tendencias" sx={{ p: 2.25, display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 2, flexWrap: 'wrap' }}>
        <Typography variant="body2" color="text.secondary" sx={{ flex: 1, minWidth: 260 }}>
          Compara los últimos días elegidos con el mismo lapso anterior. «Nivel» es la palabra de
          la escala que mejor resume las calificaciones de cada período. Hacen falta al menos
          cuatro calificaciones en el período para hablar de tendencia.
        </Typography>
        <Box sx={{ width: 190 }}>
          <CampoTexto id="tendencia-dias" etiqueta="Período" select valor={dias} onChange={(e) => setDias(Number(e?.target?.value ?? e))}>
            {PERIODOS_TENDENCIA.map((d) => <MenuItem key={d} value={d}>Últimos {d} días</MenuItem>)}
          </CampoTexto>
        </Box>
      </Box>

      {tendencias.cargando && !datos && <Cargando texto="Calculando la tendencia..." minHeight={100} />}
      {tendencias.error && <EstadoError error={tendencias.error} onReintentar={tendencias.recargar} />}
      {datos && (
        <>
          <Typography variant="caption" color="text.secondary" className="tabular">
            Período actual: del {formatearFecha(datos.periodo.desde)} al {formatearFecha(datos.periodo.hasta)}.
            Período anterior: del {formatearFecha(datos.periodo_anterior.desde)} al {formatearFecha(datos.periodo_anterior.hasta)}.
          </Typography>
          {datos.objetivos.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              Todavía no hay objetivos con calificaciones en estos períodos.
            </Typography>
          ) : (
            <DataTable columnas={columnas} filas={datos.objetivos} />
          )}
        </>
      )}
    </Box>
  );
}

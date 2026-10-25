// frontend/src/components/informes/SeccionInformes.jsx
// Pestaña "Informes" de la ficha del paciente: historial de versiones y
// generación de uno nuevo. Leer es de cualquier terapeuta; generar, editar y
// publicar es de quien está asignado (la base lo hace cumplir).

import { useMemo, useState } from 'react';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Typography from '@mui/material/Typography';

import ChipEstadoInforme from './ChipEstadoInforme.jsx';
import ModalGenerarInforme from './ModalGenerarInforme.jsx';
import ModalInforme from './ModalInforme.jsx';
import DataTable from '../data/DataTable.jsx';
import { Cargando, EstadoError, EstadoVacio } from '../estado/index.js';
import { usePeticion } from '../../hooks/usePeticion.js';
import { listarInformesDePaciente } from '../../services/informesService.js';
import { formatearFecha } from '../../utils/fechas.js';

export default function SeccionInformes({ paciente, puedeEscribir, onAviso, tieneIngreso = true }) {
  const historial = usePeticion(() => listarInformesDePaciente(paciente.id), [paciente.id]);
  const [generando, setGenerando] = useState(false);
  const [abierto, setAbierto] = useState(null); // { id, advertencia }

  const informes = historial.datos?.informes ?? [];
  const borradores = useMemo(() => informes.filter((i) => i.estado === 'borrador'), [informes]);

  const columnas = useMemo(() => [
    { clave: 'tipo', etiqueta: 'Informe', render: (i) => (
      <Box>
        <Typography variant="body1">{i.tipo_etiqueta}</Typography>
        <Typography variant="body2" color="text.secondary">{i.periodo_etiqueta}</Typography>
      </Box>
    ) },
    { clave: 'version', etiqueta: 'Versión', ancho: 90, render: (i) => <span className="tabular">{i.version}</span> },
    { clave: 'estado', etiqueta: 'Estado', ancho: 130, render: (i) => <ChipEstadoInforme estado={i.estado} /> },
    { clave: 'origen', etiqueta: 'Redacción', ancho: 150, render: (i) => (
      <Chip size="small" variant="outlined" label={i.generado_con === 'ia' ? 'Con inteligencia artificial' : 'Plantilla'} />
    ) },
    { clave: 'autor', etiqueta: 'Profesional', render: (i) => <span className="texto-libre">{i.autor ?? '—'}</span> },
    { clave: 'fecha', etiqueta: 'Fecha', ancho: 120, render: (i) => (
      <span className="tabular">{formatearFecha(i.estado === 'final' ? i.fecha_publicacion : i.fecha_generacion)}</span>
    ) },
    { clave: 'abrir', etiqueta: '', ancho: 100, render: (i) => (
      <Button size="small" onClick={() => setAbierto({ id: i.id, advertencia: '' })}>Abrir</Button>
    ) },
  ], []);

  const alGenerar = (resultado) => {
    setGenerando(false);
    historial.recargar();
    onAviso?.('El borrador está listo para revisar.');
    setAbierto({ id: resultado.id, advertencia: resultado.advertencia ?? '' });
  };

  return (
    <>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2, flexWrap: 'wrap' }}>
        <Box sx={{ flex: 1, minWidth: 260 }}>
          <Typography variant="h5">Informes</Typography>
          <Typography variant="body2" color="text.secondary">
            Mensual, semestral y plan terapéutico integral. Cada uno se genera como borrador, se revisa y recién entonces se publica.
          </Typography>
        </Box>
        {puedeEscribir ? (
          <Button variant="contained" onClick={() => setGenerando(true)} disabled={!paciente.activo}>Generar informe</Button>
        ) : (
          <Typography variant="body2" color="text.secondary">Solo el terapeuta asignado puede generar informes.</Typography>
        )}
      </Box>

      {historial.cargando && <Cargando texto="Cargando los informes..." />}
      {historial.error && <EstadoError error={historial.error} onReintentar={historial.recargar} />}
      {historial.datos && !historial.cargando && (
        informes.length === 0 ? (
          <EstadoVacio titulo="Todavía no hay informes" descripcion="Cuando se genere el primero, su historial aparecerá aquí." />
        ) : (
          <DataTable columnas={columnas} filas={informes} claveFila={(i) => i.id} />
        )
      )}

      <ModalGenerarInforme
        abierto={generando} idPaciente={paciente.id} nombrePaciente={paciente.nombre_completo} iaDisponible={Boolean(historial.datos?.ia_disponible)} iaLocal={Boolean(historial.datos?.ia_local)}
        hayPuedePti={tieneIngreso} borradores={borradores}
        onCerrar={() => setGenerando(false)} onGenerado={alGenerar}
      />
      <ModalInforme
        idInforme={abierto?.id ?? null} advertencia={abierto?.advertencia ?? ''} puedeEscribir={puedeEscribir}
        onCerrar={() => { setAbierto(null); historial.recargar(); }}
        onCambio={(m) => { onAviso?.(m); historial.recargar(); }}
        onAbrir={(id) => setAbierto({ id, advertencia: '' })}
      />
    </>
  );
}

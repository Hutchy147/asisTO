// frontend/src/pages/ControlInformes.jsx
// Control mensual de informes (Entrega 6): para cada paciente del terapeuta,
// qué informes del mes están hechos, cuáles son borrador y cuáles faltan.
// Es la hoja del ritual de cierre de mes: de acá se genera o se abre cada uno.

import { useMemo, useState } from 'react';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Snackbar from '@mui/material/Snackbar';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';

import DataTable from '../components/data/DataTable.jsx';
import StatTile from '../components/data/StatTile.jsx';
import { Cargando, EstadoError, EstadoVacio } from '../components/estado/index.js';
import AppLayout from '../components/layout/AppLayout.jsx';
import ModalGenerarInforme from '../components/informes/ModalGenerarInforme.jsx';
import ModalInforme from '../components/informes/ModalInforme.jsx';
import { usePeticion } from '../hooks/usePeticion.js';
import { useEstadoEnUrl } from '../hooks/useEstadoEnUrl.js';
import { listarInformesDePaciente, obtenerControlMensual } from '../services/informesService.js';

const pad = (n) => String(n).padStart(2, '0');
const mesDeHoy = () => {
  const h = new Date();
  return `${h.getFullYear()}-${pad(h.getMonth() + 1)}`;
};

const ESTADO = {
  publicado: { etiqueta: 'Publicado', color: 'success' },
  borrador: { etiqueta: 'Borrador', color: 'warning' },
  pendiente: { etiqueta: 'Pendiente', color: 'default' },
  no_corresponde: { etiqueta: 'No corresponde', color: 'default' },
};

function Celda({ celda, onAbrir, onGenerar }) {
  if (celda.estado === 'publicado' && celda.hay_borrador && celda.id_borrador) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, flexWrap: 'wrap' }}>
        <Chip size="small" color="warning" label="Corrección en borrador" />
        <Button size="small" onClick={() => onAbrir(celda.id_borrador)}>Seguir</Button>
        <Button size="small" color="inherit" onClick={() => onAbrir(celda.id)}>Ver publicado</Button>
      </Box>
    );
  }
  const info = ESTADO[celda.estado] ?? ESTADO.pendiente;
  if (celda.estado === 'no_corresponde') {
    return <Typography variant="body2" color="text.secondary">—</Typography>;
  }
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
      <Chip size="small" color={info.color} variant={celda.estado === 'pendiente' ? 'outlined' : 'filled'} label={info.etiqueta} />
      {celda.estado === 'pendiente'
        ? <Button size="small" onClick={onGenerar}>Generar</Button>
        : <Button size="small" onClick={() => onAbrir(celda.id)}>Abrir</Button>}
    </Box>
  );
}

export default function ControlInformes() {
  // El mes va en la URL (?mes=2026-09): F5 vuelve al mismo mes.
  const [mes, setMes] = useEstadoEnUrl('mes', mesDeHoy());
  const [generar, setGenerar] = useState(null); // { paciente, tipo, periodo, ia, borradores }
  const [abierto, setAbierto] = useState(null); // { id, puedeEscribir, advertencia }
  const [aviso, setAviso] = useState('');
  const [error, setError] = useState('');

  const mesValido = /^\d{4}-\d{2}$/.test(mes) && mes <= mesDeHoy();
  const control = usePeticion(() => (mesValido ? obtenerControlMensual(mes) : Promise.resolve(null)), [mes, mesValido]);
  const datos = control.datos;

  const abrirGenerar = async (fila, tipo) => {
    setError('');
    try {
      const historial = await listarInformesDePaciente(fila.id_paciente);
      setGenerar({
        id_paciente: fila.id_paciente,
        tipo,
        periodo: tipo === 'mensual' ? datos.mes : tipo === 'semestral' ? datos.semestre : 'pti',
        ia: Boolean(historial.ia_disponible),
        borradores: historial.informes.filter((i) => i.estado === 'borrador'),
      });
    } catch (fallo) {
      setError(fallo.message);
    }
  };

  const columnas = useMemo(() => [
    { clave: 'paciente', etiqueta: 'Paciente', render: (f) => <span className="texto-libre">{f.paciente}</span> },
    { clave: 'sesiones', etiqueta: 'Sesiones del mes', ancho: 140, render: (f) => <span className="tabular">{f.sesiones_registradas}</span> },
    { clave: 'mensual', etiqueta: 'Mensual', ancho: 230, render: (f) => (
      <Celda celda={f.mensual} onAbrir={(id) => setAbierto({ id, puedeEscribir: true, advertencia: '' })} onGenerar={() => abrirGenerar(f, 'mensual')} />
    ) },
    { clave: 'semestral', etiqueta: 'Semestral', ancho: 230, render: (f) => (
      <Celda celda={f.semestral} onAbrir={(id) => setAbierto({ id, puedeEscribir: true, advertencia: '' })} onGenerar={() => abrirGenerar(f, 'semestral')} />
    ) },
    { clave: 'pti', etiqueta: 'PTI', ancho: 230, render: (f) => (
      <Celda celda={f.pti} onAbrir={(id) => setAbierto({ id, puedeEscribir: true, advertencia: '' })} onGenerar={() => abrirGenerar(f, 'pti')} />
    ) },
  // eslint-disable-next-line react-hooks/exhaustive-deps
  ], [datos?.mes, datos?.semestre]);

  return (
    <AppLayout titulo="Informes" subtitulo="Control mensual de los informes de sus pacientes">
      <Box
        sx={(t) => ({
          display: 'flex', flexWrap: 'wrap', gap: 2, alignItems: 'flex-end', p: 2, mb: 2,
          backgroundColor: t.palette.superficie.tarjeta, border: `1px solid ${t.palette.superficie.borde}`,
          borderRadius: `${t.formas.md}px`,
        })}
      >
        <TextField
          id="control-mes" label="Mes" type="month" size="small" value={mes} InputLabelProps={{ shrink: true }}
          onChange={(e) => setMes(e.target.value)} inputProps={{ max: mesDeHoy() }}
          error={!mesValido} helperText={mesValido ? ' ' : 'Elija un mes que ya haya empezado.'}
        />
        {/* El mes ya se lee en el selector: solo se agrega el aviso de semestre. */}
        {datos?.cierra_semestre && (
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2.75 }}>
            Cierre de semestre: corresponde el informe semestral.
          </Typography>
        )}
      </Box>

      {error && <Typography color="error" sx={{ mb: 1 }}>{error}</Typography>}
      {control.cargando && <Cargando texto="Cargando el control..." />}
      {control.error && <EstadoError error={control.error} onReintentar={control.recargar} />}
      {datos && !control.cargando && !control.error && (
        <>
          <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mb: 2 }}>
            <StatTile etiqueta="Mensuales publicados" valor={datos.resumen.publicados} />
            <StatTile etiqueta="En borrador" valor={datos.resumen.en_borrador_total ?? datos.resumen.borradores} />
            <StatTile etiqueta="Pendientes" valor={datos.resumen.pendientes} />
          </Box>
          {datos.pacientes.length === 0 ? (
            <EstadoVacio titulo="No tiene pacientes asignados en este mes" descripcion="Cuando tenga pacientes asignados, aparecerán aquí con el estado de sus informes." />
          ) : (
            <DataTable columnas={columnas} filas={datos.pacientes} claveFila={(f) => f.id_paciente} />
          )}
        </>
      )}

      {generar && (
        <ModalGenerarInforme
          key={`${generar.id_paciente}-${generar.tipo}-${generar.periodo}`}
          abierto idPaciente={generar.id_paciente} iaDisponible={generar.ia}
          borradores={generar.borradores} tipoInicial={generar.tipo} periodoInicial={generar.periodo}
          onCerrar={() => setGenerar(null)}
          onGenerado={(r) => {
            setGenerar(null);
            control.recargar();
            setAbierto({ id: r.id, puedeEscribir: true, advertencia: r.advertencia ?? '' });
          }}
        />
      )}
      <ModalInforme
        idInforme={abierto?.id ?? null} puedeEscribir={abierto?.puedeEscribir ?? false} advertencia={abierto?.advertencia ?? ''}
        onCerrar={() => { setAbierto(null); control.recargar(); }}
        onCambio={(m) => { setAviso(m); control.recargar(); }}
        onAbrir={(id) => setAbierto({ id, puedeEscribir: true, advertencia: '' })}
      />
      <Snackbar open={Boolean(aviso)} autoHideDuration={6000} onClose={() => setAviso('')} message={aviso} />
    </AppLayout>
  );
}

// frontend/src/pages/InformesFamiliar.jsx
// Informes publicados del paciente vinculado (Entrega 6, HDU 8). El familiar
// solo ve informes en estado final: los borradores y las versiones
// reemplazadas no le llegan desde el servidor. Tampoco se muestra el nombre
// de quien lo redactó: firma el equipo.

import { useState } from 'react';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import Tab from '@mui/material/Tab';
import Tabs from '@mui/material/Tabs';
import Typography from '@mui/material/Typography';

import TextoInforme from '../components/informes/TextoInforme.jsx';
import BarraFamiliar from '../components/familiar/BarraFamiliar.jsx';
import DataTable from '../components/data/DataTable.jsx';
import { Aviso, Cargando, EstadoError, EstadoVacio } from '../components/estado/index.js';
import { hayCapacidad } from '../config/entregas.js';
import { usePeticion } from '../hooks/usePeticion.js';
import { useEstadoEnUrl } from '../hooks/useEstadoEnUrl.js';
import { contarNoLeidas, obtenerPreferencias } from '../services/notificacionesService.js';
import {
  descargarPdfInformeVinculado, listarInformesVinculados, listarPacientesVinculados,
  obtenerInformeVinculado,
} from '../services/portalFamiliarService.js';
import { formatearFecha } from '../utils/fechas.js';

function LectorInforme({ idPaciente, idInforme, onCerrar }) {
  const abierto = idInforme !== null;
  const informe = usePeticion(
    () => (abierto ? obtenerInformeVinculado(idPaciente, idInforme) : Promise.resolve(null)),
    [idPaciente, idInforme],
  );
  const [error, setError] = useState('');
  const [descargado, setDescargado] = useState('');
  const datos = informe.datos;

  const descargar = async () => {
    setError('');
    try {
      const nombre = await descargarPdfInformeVinculado(idPaciente, idInforme);
      // Confirmación visible: en el celular la descarga no siempre se nota.
      setDescargado(`Se descargó «${nombre}». Lo encuentra en la carpeta de descargas del teléfono o la computadora.`);
    } catch (fallo) { setError(fallo.message); }
  };

  return (
    <Dialog open={abierto} onClose={onCerrar} maxWidth={false} PaperProps={{ sx: { width: 820, maxWidth: '96vw', height: '90vh' } }}>
      <Box sx={{ px: 3, pt: 2.5, pb: 1 }}>
        <Typography variant="h5">{datos ? `${datos.tipo_etiqueta} · ${datos.periodo_etiqueta}` : 'Informe'}</Typography>
        {datos && (
          <Typography variant="body2" color="text.secondary" className="texto-libre">
            {datos.paciente?.nombre_completo} · Publicado el {formatearFecha(datos.fecha_publicacion)}
            {datos.version > 1 ? ` · versión ${datos.version}` : ''}
          </Typography>
        )}
      </Box>
      <DialogContent sx={{ px: 3, py: 1 }}>
        {informe.cargando && !datos && <Cargando texto="Cargando el informe..." />}
        {informe.error && <EstadoError error={informe.error} onReintentar={informe.recargar} />}
        {error && <Aviso severidad="error">{error}</Aviso>}
        {descargado && <Aviso severidad="success">{descargado}</Aviso>}
        {datos && <TextoInforme contenido={datos.contenido} />}
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2.5, gap: 1 }}>
        <Button color="inherit" onClick={descargar} disabled={!datos}>Descargar PDF (para guardar o imprimir)</Button>
        <Button variant="outlined" onClick={onCerrar}>Cerrar</Button>
      </DialogActions>
    </Dialog>
  );
}

function InformesDe({ paciente, textoAviso }) {
  const lista = usePeticion(() => listarInformesVinculados(paciente.id), [paciente.id]);
  const [abierto, setAbierto] = useState(null);

  // El más reciente se marca: con dos o más no se sabía cuál era el nuevo.
  const masReciente = (lista.datos?.informes ?? []).reduce(
    (a, i) => (!a || (i.fecha_publicacion ?? '') > (a.fecha_publicacion ?? '') ? i : a), null,
  );
  // Sin columna «Versión»: a una familia no le dice nada.
  const columnas = [
    { clave: 'tipo', etiqueta: 'Informe', render: (i) => (
      <Box>
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
          <Typography variant="body1">{i.tipo_etiqueta}</Typography>
          {masReciente?.id === i.id && <Chip size="small" color="primary" label="Más reciente" />}
        </Box>
        <Typography variant="body2" color="text.secondary">
          {i.periodo_etiqueta} · publicado el {formatearFecha(i.fecha_publicacion)}
        </Typography>
      </Box>
    ) },
    { clave: 'leer', etiqueta: '', ancho: 90, render: (i) => <Button size="small" variant="outlined" onClick={() => setAbierto(i.id)}>Leer</Button> },
  ];

  return (
    <>
      {lista.cargando && <Cargando texto="Cargando los informes..." />}
      {lista.error && <EstadoError error={lista.error} onReintentar={lista.recargar} />}
      {lista.datos && !lista.cargando && (
        lista.datos.informes.length === 0 ? (
          <EstadoVacio
            titulo="Todavía no hay informes publicados"
            descripcion={`Cuando el equipo terapéutico publique un informe de ${paciente.nombre_completo}, lo podrá leer y descargar aquí.${textoAviso}`}
          />
        ) : (
          <DataTable columnas={columnas} filas={lista.datos.informes} claveFila={(i) => i.id} />
        )
      )}
      <LectorInforme idPaciente={paciente.id} idInforme={abierto} onCerrar={() => setAbierto(null)} />
    </>
  );
}

export default function InformesFamiliar() {
  const pacientes = usePeticion(() => listarPacientesVinculados(), []);
  const avisos = usePeticion(
    () => (hayCapacidad('notificaciones') ? contarNoLeidas() : Promise.resolve({ no_leidas: 0 })),
    [],
  );
  // Lo que se promete sobre el aviso depende de la preferencia del familiar:
  // decía «Se le avisará» aunque tuviera los avisos de informes apagados.
  const preferencias = usePeticion(
    () => (hayCapacidad('notificaciones') ? obtenerPreferencias() : Promise.resolve(null)),
    [],
  );
  const avisoInforme = preferencias.datos?.preferencias?.find((p) => p.tipo === 'informe_generado');
  const textoAviso = !avisoInforme
    ? ''
    : avisoInforme.habilitada
      ? ' Cuando haya uno nuevo, le aparecerá un aviso en «Avisos».'
      : ' Tiene desactivados los avisos de informes nuevos: puede activarlos en «Avisos».';
  const [elegidoUrl, setElegido] = useEstadoEnUrl('paciente', '');
  const elegido = Number(elegidoUrl) || null;
  const lista = pacientes.datos?.pacientes ?? [];
  const paciente = lista.find((p) => p.id === elegido) ?? lista[0] ?? null;

  return (
    <BarraFamiliar activa="informes" sinLeer={avisos.datos?.no_leidas ?? 0}>
      <Typography variant="h4" sx={{ mb: 0.5 }}>Informes</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Los informes que el equipo terapéutico publicó sobre el tratamiento.
      </Typography>
      {pacientes.cargando && <Cargando texto="Cargando sus datos..." />}
      {pacientes.error && <EstadoError error={pacientes.error} onReintentar={pacientes.recargar} />}
      {pacientes.datos && lista.length === 0 && (
        <EstadoVacio
          titulo="Todavía no tiene pacientes vinculados"
          descripcion="El centro debe vincular su cuenta con el paciente para que pueda consultar sus informes. Comuníquese con el equipo terapéutico."
        />
      )}
      {paciente && (
        <>
          {lista.length > 1 && (
            <Tabs
              variant="scrollable" scrollButtons="auto" allowScrollButtonsMobile
              value={paciente.id} onChange={(e, v) => setElegido(v)}
              sx={(t) => ({ mb: 2, borderBottom: `1px solid ${t.palette.superficie.borde}` })}
            >
              {lista.map((p) => <Tab key={p.id} value={p.id} label={p.nombre_completo} />)}
            </Tabs>
          )}
          <InformesDe key={paciente.id} paciente={paciente} textoAviso={textoAviso} />
        </>
      )}
    </BarraFamiliar>
  );
}

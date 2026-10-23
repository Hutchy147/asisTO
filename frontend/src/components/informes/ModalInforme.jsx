// frontend/src/components/informes/ModalInforme.jsx
// Un informe abierto: lectura, edición del borrador, publicación, corrección
// de uno publicado y PDF. Al costado, los diarios del período para consultar
// mientras se revisa.
//
// Publicar guarda primero lo que se escribió: lo que se publica es lo que se
// ve en pantalla, no la última versión guardada.

import { useEffect, useRef, useState } from 'react';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';

import ChipEstadoInforme from './ChipEstadoInforme.jsx';
import PanelDiarios from './PanelDiarios.jsx';
import TextoInforme from './TextoInforme.jsx';
import DialogoConfirmacion from '../modal/DialogoConfirmacion.jsx';
import { Aviso, Cargando, EstadoError } from '../estado/index.js';
import { usePeticion } from '../../hooks/usePeticion.js';
import {
  corregirInforme, descargarPdfInforme, descartarInforme, guardarInforme,
  obtenerDiariosDeInforme, obtenerInforme, publicarInforme,
} from '../../services/informesService.js';
import { formatearFecha } from '../../utils/fechas.js';

export default function ModalInforme({ idInforme, puedeEscribir, advertencia = '', onCerrar, onCambio, onAbrir }) {
  const abierto = idInforme !== null && idInforme !== undefined;
  const informe = usePeticion(() => (abierto ? obtenerInforme(idInforme) : Promise.resolve(null)), [idInforme]);
  const [texto, setTexto] = useState('');
  const [verDiarios, setVerDiarios] = useState(false);
  const [trabajando, setTrabajando] = useState('');
  const [error, setError] = useState(null);
  const [confirmando, setConfirmando] = useState(null); // 'publicar' | 'descartar' | 'corregir'

  const diarios = usePeticion(
    () => (abierto && verDiarios ? obtenerDiariosDeInforme(idInforme) : Promise.resolve(null)),
    [idInforme, verDiarios],
  );

  const datos = informe.datos;
  useEffect(() => {
    if (datos) setTexto(datos.contenido ?? '');
    setError(null);
  }, [datos]);
  useEffect(() => { if (!abierto) { setVerDiarios(false); setConfirmando(null); } }, [abierto]);

  const esBorrador = datos?.estado === 'borrador';
  const editable = Boolean(esBorrador && puedeEscribir);
  const cambiado = Boolean(datos) && texto !== (datos.contenido ?? '');
  // Misma regla que el servidor (LOCATE('[COMPLETAR', UPPER(...))): cualquier
  // mayúscula y aunque falte el corchete de cierre (F8.4).
  const pendientes = (texto.match(/\[COMPLETAR/gi) ?? []).length;
  // Un rechazo se muestra arriba del texto: si se estaba leyendo más abajo,
  // quedaba fuera de la vista y parecía que no pasaba nada (F8.4).
  const refError = useRef(null);
  useEffect(() => {
    if (error) refError.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }, [error]);

  const ejecutar = async (clave, accion) => {
    setTrabajando(clave);
    setError(null);
    try {
      return await accion();
    } catch (fallo) {
      setError(fallo);
      setConfirmando(null);
      return null;
    } finally {
      setTrabajando('');
    }
  };

  const guardar = () => ejecutar('guardar', async () => {
    const nuevo = await guardarInforme(idInforme, texto);
    informe.setDatos(nuevo);
    onCambio?.('El borrador se guardó.');
  });

  const publicar = async () => {
    const resultado = await ejecutar('publicar', async () => {
      if (cambiado) await guardarInforme(idInforme, texto);
      return publicarInforme(idInforme);
    });
    if (resultado) {
      setConfirmando(null);
      informe.setDatos(resultado);
      const n = resultado.familiares_avisados ?? 0;
      onCambio?.(n > 0
        ? `El informe se publicó y se avisó a ${n} ${n === 1 ? 'familiar' : 'familiares'}.`
        : 'El informe se publicó.');
    }
  };

  const corregir = async () => {
    const nuevo = await ejecutar('corregir', () => corregirInforme(idInforme));
    if (nuevo) {
      setConfirmando(null);
      onCambio?.('Se creó un borrador con la corrección. El informe publicado sigue vigente hasta que se publique el nuevo.');
      onAbrir?.(nuevo.id);
    }
  };

  const descartar = async () => {
    const resultado = await ejecutar('descartar', () => descartarInforme(idInforme));
    if (resultado) {
      setConfirmando(null);
      onCambio?.('El borrador se descartó.');
      onCerrar();
    }
  };

  const pdf = () => ejecutar('pdf', () => descargarPdfInforme(idInforme));

  return (
    <>
      <Dialog
        open={abierto}
        onClose={trabajando ? undefined : onCerrar}
        maxWidth={false}
        PaperProps={{ sx: { width: verDiarios ? 1180 : 820, maxWidth: '96vw', height: '90vh' } }}
      >
        <Box sx={{ px: 3, pt: 2.5, pb: 1, display: 'flex', alignItems: 'center', gap: 1.5, flexWrap: 'wrap' }}>
          <Typography variant="h5" sx={{ flex: 1, minWidth: 220 }}>
            {datos ? `${datos.tipo_etiqueta} · ${datos.periodo_etiqueta}` : 'Informe'}
          </Typography>
          {datos && <ChipEstadoInforme estado={datos.estado} />}
          {datos && datos.version > 1 && <Chip size="small" variant="outlined" label={`Versión ${datos.version}`} />}
        </Box>

        <DialogContent sx={{ px: 3, py: 1, display: 'flex', gap: 3, minHeight: 0 }}>
          <Box sx={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
            {informe.cargando && !datos && <Cargando texto="Cargando el informe..." />}
            {informe.error && <EstadoError error={informe.error} onReintentar={informe.recargar} />}
            {error && <Box ref={refError}><Aviso severidad="error">{error.message}</Aviso></Box>}
            {advertencia && <Aviso severidad="warning">{advertencia}</Aviso>}
            {datos && (
              <>
                <Typography variant="body2" color="text.secondary" className="texto-libre" sx={{ mb: 1.5 }}>
                  {datos.paciente?.nombre_completo ? `${datos.paciente.nombre_completo} · ` : ''}
                  {datos.autor ? `${datos.autor} · ` : ''}
                  {datos.estado === 'final' && datos.fecha_publicacion
                    ? `Publicado el ${formatearFecha(datos.fecha_publicacion)}`
                    : `Generado el ${formatearFecha(datos.fecha_generacion)}`}
                  {datos.generado_con === 'ia' ? ` · Redactado con inteligencia artificial${datos.proveedor ? ` (${datos.proveedor})` : ''}` : ' · Armado con la plantilla del centro'}
                  {datos.editado ? ' · Editado' : ''}
                </Typography>
                {esBorrador && datos.generado_con === 'ia' && (
                  <Aviso severidad="info">
                    Este texto lo redactó una inteligencia artificial. Revíselo completo y corríjalo antes de publicarlo: usted es quien responde por su contenido.
                  </Aviso>
                )}
                {editable && pendientes > 0 && (
                  <Aviso severidad="warning">
                    Quedan {pendientes} {pendientes === 1 ? 'marca' : 'marcas'} [COMPLETAR…] por resolver. Mientras existan, el informe no se puede publicar.
                  </Aviso>
                )}
                {editable && /##\s*Observaciones de las sesiones/i.test(texto) && (
                  <Aviso severidad="info">
                    Al publicar, la familia lee este informe tal como queda, incluida la sección de observaciones de las sesiones. Revise que no incluya detalles clínicos que no deba ver.
                  </Aviso>
                )}
                {datos.estado === 'reemplazado' && (
                  <Aviso severidad="info">Esta versión fue reemplazada por una posterior. Se conserva como constancia.</Aviso>
                )}
                {editable ? (
                  <TextField
                    id="informe-contenido" multiline fullWidth value={texto} onChange={(e) => setTexto(e.target.value)}
                    minRows={18} disabled={Boolean(trabajando)}
                    inputProps={{ 'aria-label': 'Contenido del informe' }}
                    sx={{ '& textarea': { lineHeight: 1.6 } }}
                  />
                ) : (
                  <TextoInforme contenido={datos.contenido} />
                )}
                {editable && (
                  <Typography variant="caption" color="text.secondary" sx={{ mt: 0.75 }}>
                    «## Título» abre una sección y «- » abre un ítem de lista.
                  </Typography>
                )}
              </>
            )}
          </Box>
          {verDiarios && (
            <Box sx={(t) => ({ width: 380, flex: 'none', overflow: 'auto', borderLeft: `1px solid ${t.palette.superficie.borde}`, pl: 2.5 })}>
              <Typography variant="h6" sx={{ mb: 1 }}>Diarios del período</Typography>
              <PanelDiarios peticion={diarios} />
            </Box>
          )}
        </DialogContent>

        <DialogActions sx={{ px: 3, pb: 2.5, pt: 1.5, gap: 1, flexWrap: 'wrap' }}>
          <Button color="inherit" onClick={() => setVerDiarios((v) => !v)} disabled={!datos}>
            {verDiarios ? 'Ocultar diarios' : 'Ver diarios del período'}
          </Button>
          <Button color="inherit" onClick={pdf} disabled={!datos || Boolean(trabajando)}
            startIcon={trabajando === 'pdf' ? <CircularProgress size={16} color="inherit" /> : null}>
            Descargar PDF
          </Button>
          <Box sx={{ flex: 1 }} />
          {editable && (
            <Button color="error" onClick={() => setConfirmando('descartar')} disabled={Boolean(trabajando)}>Descartar borrador</Button>
          )}
          {editable && (
            <Button variant="outlined" onClick={guardar} disabled={!cambiado || Boolean(trabajando)}>
              {trabajando === 'guardar' ? 'Guardando…' : 'Guardar'}
            </Button>
          )}
          {editable && (
            <Button variant="contained" onClick={() => setConfirmando('publicar')} disabled={pendientes > 0 || Boolean(trabajando) || texto.trim() === ''}>
              Publicar
            </Button>
          )}
          {puedeEscribir && datos?.estado === 'final' && (
            <Button variant="contained" onClick={() => setConfirmando('corregir')} disabled={Boolean(trabajando)}>Corregir</Button>
          )}
          <Button variant="outlined" onClick={onCerrar} disabled={Boolean(trabajando)}>Cerrar</Button>
        </DialogActions>
      </Dialog>

      <DialogoConfirmacion
        abierto={confirmando === 'publicar'} titulo="Publicar el informe"
        etiquetaConfirmar="Publicar" etiquetaProcesando="Publicando…" procesando={trabajando === 'publicar'}
        onConfirmar={publicar} onCancelar={() => setConfirmando(null)}
      >
        Al publicarlo, el informe deja de ser editable y los familiares vinculados al paciente podrán leerlo y se les avisará. Si después hay que cambiar algo, se crea una corrección y el historial conserva ambas versiones.
      </DialogoConfirmacion>
      <DialogoConfirmacion
        abierto={confirmando === 'corregir'} titulo="Corregir el informe publicado"
        etiquetaConfirmar="Crear corrección" etiquetaProcesando="Creando…" procesando={trabajando === 'corregir'}
        onConfirmar={corregir} onCancelar={() => setConfirmando(null)}
      >
        Se crea un borrador nuevo a partir de este informe. La versión publicada sigue vigente para la familia hasta que usted publique la corrección.
      </DialogoConfirmacion>
      <DialogoConfirmacion
        abierto={confirmando === 'descartar'} titulo="Descartar el borrador"
        etiquetaConfirmar="Descartar" etiquetaProcesando="Descartando…" procesando={trabajando === 'descartar'}
        peligro
        onConfirmar={descartar} onCancelar={() => setConfirmando(null)}
      >
        El borrador se elimina y no se puede recuperar. Puede generar uno nuevo cuando lo necesite.
      </DialogoConfirmacion>
    </>
  );
}

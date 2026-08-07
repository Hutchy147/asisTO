// frontend/src/pages/PacienteFicha.jsx
// Ficha del paciente: datos, objetivos (activos y archivados) e historial
// de sesiones. Pantalla propia con su URL, no un panel lateral.

import { useState } from 'react';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Snackbar from '@mui/material/Snackbar';
import Tab from '@mui/material/Tab';
import Tabs from '@mui/material/Tabs';
import Typography from '@mui/material/Typography';
import { useNavigate, useParams } from 'react-router-dom';

import AccountFlag from '../components/data/AccountFlag.jsx';
import DataTable from '../components/data/DataTable.jsx';
import GoalMeter from '../components/data/GoalMeter.jsx';
import SesionEstadoChip from '../components/data/SesionEstadoChip.jsx';
import ModalCargarEvolucion from '../components/evoluciones/ModalCargarEvolucion.jsx';
import AppLayout from '../components/layout/AppLayout.jsx';
import DialogoConfirmacion from '../components/modal/DialogoConfirmacion.jsx';
import { ObjetivoActivo, ObjetivoArchivado } from '../components/objetivos/FilaObjetivo.jsx';
import ModalObjetivo from '../components/objetivos/ModalObjetivo.jsx';
import { Cargando, EstadoError, EstadoVacio } from '../components/estado/index.js';
import { usePeticion } from '../hooks/usePeticion.js';
import { archivarObjetivo, listarObjetivosDePaciente } from '../services/objetivosService.js';
import { listarSesionesDePaciente } from '../services/pacientesService.js';
import { formatearFecha, formatearMes, textoEdad } from '../utils/fechas.js';

/** Panel con encabezado, para las secciones de la ficha. */
function Seccion({ titulo, descripcion, acciones, children }) {
  return (
    <Box
      sx={(t) => ({
        backgroundColor: t.palette.superficie.tarjeta,
        border: `1px solid ${t.palette.superficie.borde}`,
        borderRadius: `${t.formas.md}px`,
        mb: 2,
      })}
    >
      <Box
        sx={(t) => ({
          display: 'flex',
          alignItems: 'flex-start',
          gap: 2,
          px: 2.25,
          py: 1.75,
          borderBottom: `1px solid ${t.palette.superficie.borde}`,
        })}
      >
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography variant="h5">{titulo}</Typography>
          {descripcion && (
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.25 }}>
              {descripcion}
            </Typography>
          )}
        </Box>
        {acciones}
      </Box>
      {children}
    </Box>
  );
}

function Dato({ etiqueta, children }) {
  return (
    <Box sx={{ minWidth: 150 }}>
      <Typography variant="overline" component="div" color="text.secondary" sx={{ mb: 0.5 }}>
        {etiqueta}
      </Typography>
      {/* texto-libre acá y no en cada llamador: el valor de un Dato es casi
          siempre un campo de la base —diagnóstico, n° de historia, obra
          social cuando se conecte— y así lo hereda también el que se agregue
          después. */}
      <Box className="texto-libre" sx={{ fontSize: 14 }}>{children ?? '—'}</Box>
    </Box>
  );
}

export default function PacienteFicha() {
  const { id } = useParams();
  const navigate = useNavigate();

  const objetivos = usePeticion(() => listarObjetivosDePaciente(id), [id]);
  const sesiones = usePeticion(() => listarSesionesDePaciente(id), [id]);

  const [pestania, setPestania] = useState('objetivos');
  const [modalObjetivo, setModalObjetivo] = useState(null); // null | { objetivo? }
  const [aArchivar, setAArchivar] = useState(null);
  const [archivando, setArchivando] = useState(false);
  const [idEvolucion, setIdEvolucion] = useState(null);
  const [aviso, setAviso] = useState('');

  if (objetivos.cargando) {
    return (
      <AppLayout titulo="Ficha del paciente">
        <Cargando texto="Cargando la ficha..." />
      </AppLayout>
    );
  }

  // Cubre las dos variantes de 404 del contrato: "no existe" y "está dado
  // de baja". El mensaje distingue cuál es, y viene del servidor.
  if (objetivos.error) {
    return (
      <AppLayout titulo="Ficha del paciente">
        <EstadoError error={objetivos.error} onReintentar={objetivos.recargar} />
      </AppLayout>
    );
  }

  const { paciente, activos, archivados, cupo } = objetivos.datos;
  const enTope = cupo.disponibles <= 0;

  const confirmarArchivado = async () => {
    setArchivando(true);
    try {
      const respuesta = await archivarObjetivo(aArchivar.id);
      setAArchivar(null);
      objetivos.recargar();
      setAviso(respuesta?.mensaje ?? 'Objetivo archivado.');
    } catch (error) {
      setAArchivar(null);
      setAviso(error.message);
    } finally {
      setArchivando(false);
    }
  };

  const columnasSesiones = [
    { clave: 'fecha', etiqueta: 'Fecha', ancho: 110, render: (s) => formatearFecha(s.fecha) },
    { clave: 'hora_inicio', etiqueta: 'Hora', ancho: 78, render: (s) => s.hora_inicio?.slice(0, 5) },
    {
      clave: 'estado',
      etiqueta: 'Estado',
      ancho: 132,
      render: (s) => <SesionEstadoChip estado={s.estado} />,
    },
    {
      clave: 'objetivos',
      etiqueta: 'Objetivos',
      ancho: 110,
      alinear: 'right',
      // En una ausencia no corresponde calificar: se muestra "—" y no
      // "0 de 3", que se leería como trabajo pendiente.
      render: (s) =>
        s.admite_evolucion ? (
          `${s.objetivos.calificados} de ${s.objetivos.total}`
        ) : (
          <Box component="span" sx={{ color: 'text.disabled' }}>
            —
          </Box>
        ),
    },
    {
      clave: 'terapeuta',
      etiqueta: 'Terapeuta',
      ancho: 200,
      truncar: true,
      render: (s) => s.terapeuta?.nombre_completo ?? '—',
    },
  ];

  return (
    <AppLayout
      titulo={paciente.nombre_completo}
      subtitulo={[
        textoEdad(paciente.fecha_nacimiento),
        paciente.fecha_alta ? `en tratamiento desde ${formatearMes(paciente.fecha_alta)}` : null,
      ]
        .filter(Boolean)
        .join(' · ')}
      acciones={
        <Button variant="outlined" onClick={() => navigate('/pacientes')}>
          Volver a pacientes
        </Button>
      }
    >
      {/* --- Cabecera con los datos del paciente --- */}
      <Box
        sx={(t) => ({
          display: 'flex',
          flexWrap: 'wrap',
          gap: 3.5,
          alignItems: 'flex-start',
          backgroundColor: t.palette.superficie.tarjeta,
          border: `1px solid ${t.palette.superficie.borde}`,
          borderRadius: `${t.formas.md}px`,
          p: 2.5,
          mb: 2.5,
        })}
      >
        <Dato etiqueta="Fecha de nacimiento">
          <span className="tabular">{formatearFecha(paciente.fecha_nacimiento)}</span>
        </Dato>
        <Dato etiqueta="N° de historia">
          <span className="tabular">{paciente.nro_historia}</span>
        </Dato>
        <Box sx={{ flex: 1, minWidth: 230 }}>
          <Dato etiqueta="Diagnóstico">{paciente.diagnostico}</Dato>
        </Box>
        <Dato etiqueta="Objetivos activos">
          <GoalMeter valor={cupo.usados} maximo={cupo.maximo} />
        </Dato>
        <Dato etiqueta="Cuenta">
          <AccountFlag tieneCuenta={paciente.tiene_login} />
        </Dato>
      </Box>

      <Tabs
        value={pestania}
        onChange={(evento, valor) => setPestania(valor)}
        sx={(t) => ({ mb: 2, borderBottom: `1px solid ${t.palette.superficie.borde}` })}
      >
        <Tab
          value="objetivos"
          label={
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              Objetivos <Chip size="small" label={activos.length} />
            </Box>
          }
        />
        <Tab
          value="sesiones"
          label={
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              Sesiones <Chip size="small" label={sesiones.datos?.total ?? 0} />
            </Box>
          }
        />
      </Tabs>

      {/* --- Pestaña Objetivos --- */}
      {pestania === 'objetivos' && (
        <>
          <Seccion
            titulo="Objetivos activos"
            descripcion="Hasta 4 por paciente. Se califican en cada sesión."
            acciones={
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                {/* La razón del bloqueo va escrita al lado, no en un
                    tooltip: el terapeuta necesita entender el límite, no
                    descubrirlo pasando el mouse por encima. */}
                {enTope && (
                  <Typography
                    variant="body2"
                    color="text.secondary"
                    sx={{ maxWidth: 260, textAlign: 'right' }}
                  >
                    Llegaste al tope de 4. Archivá uno para crear otro.
                  </Typography>
                )}
                <Button variant="contained" disabled={enTope} onClick={() => setModalObjetivo({})}>
                  Nuevo objetivo
                </Button>
              </Box>
            }
          >
            {activos.length === 0 ? (
              <EstadoVacio
                plano
                titulo="Todavía no hay objetivos cargados"
                descripcion={`Los objetivos son las frases que describen qué se busca lograr con ${paciente.nombre}. Se califican sesión a sesión, así que conviene cargarlos antes de la primera.`}
                acciones={
                  <Button variant="contained" onClick={() => setModalObjetivo({})}>
                    Cargar el primer objetivo
                  </Button>
                }
              />
            ) : (
              activos.map((objetivo, indice) => (
                <ObjetivoActivo
                  key={objetivo.id}
                  objetivo={objetivo}
                  numero={indice + 1}
                  onEditar={(o) => setModalObjetivo({ objetivo: o })}
                  onArchivar={setAArchivar}
                />
              ))
            )}
          </Seccion>

          <Seccion
            titulo="Objetivos archivados"
            descripcion="Ya no se califican y su texto quedó fijo: hay evoluciones puntuadas contra él."
          >
            {archivados.length === 0 ? (
              <EstadoVacio
                plano
                titulo="Ningún objetivo archivado"
                descripcion="Cuando archives un objetivo va a quedar acá, con todas sus calificaciones. Archivar no borra nada."
              />
            ) : (
              archivados.map((objetivo) => (
                <ObjetivoArchivado key={objetivo.id} objetivo={objetivo} />
              ))
            )}
          </Seccion>
        </>
      )}

      {/* --- Pestaña Sesiones --- */}
      {pestania === 'sesiones' && (
        <>
          {sesiones.cargando && <Cargando texto="Cargando el historial..." />}
          {sesiones.error && <EstadoError error={sesiones.error} onReintentar={sesiones.recargar} />}
          {sesiones.datos && !sesiones.cargando && !sesiones.error && (
            <Seccion
              titulo="Historial de sesiones"
              descripcion={
                sesiones.datos.total === 0
                  ? 'Sin registros'
                  : `${sesiones.datos.total} sesiones · de todos los terapeutas que lo atendieron`
              }
            >
              {sesiones.datos.total === 0 ? (
                <EstadoVacio
                  plano
                  titulo="Todavía no hay sesiones registradas"
                  descripcion={`Cuando se registre la primera sesión de ${paciente.nombre} va a aparecer acá, con su estado y los objetivos que se calificaron.`}
                />
              ) : (
                // Las filas se abren. Es el único camino por el que se
                // llega a una sesión de OTRO terapeuta: el calendario solo
                // muestra las propias, y esta pestaña trae las de todos.
                <DataTable
                  columnas={columnasSesiones}
                  filas={sesiones.datos.sesiones}
                  onAbrirFila={(s) => setIdEvolucion(s.id)}
                  etiquetaFila={(s) => `Abrir la sesión del ${formatearFecha(s.fecha)}`}
                />
              )}
            </Seccion>
          )}
        </>
      )}

      <ModalObjetivo
        // key: fuerza un formulario nuevo al pasar de alta a edición o de un
        // objetivo a otro. Sin esto el modal reusaría el valor anterior.
        key={modalObjetivo?.objetivo?.id ?? 'nuevo'}
        abierto={Boolean(modalObjetivo)}
        paciente={paciente}
        cupo={cupo}
        objetivo={modalObjetivo?.objetivo}
        onCerrar={() => setModalObjetivo(null)}
        onGuardado={(respuesta) => {
          objetivos.recargar();
          setAviso(respuesta?.mensaje ?? 'Objetivo guardado.');
        }}
      />

      <ModalCargarEvolucion
        key={idEvolucion ?? 'sin-sesion'}
        abierto={Boolean(idEvolucion)}
        idSesion={idEvolucion}
        onCerrar={() => setIdEvolucion(null)}
        onCargada={(respuesta) => {
          sesiones.recargar();
          objetivos.recargar();
          setAviso(respuesta?.mensaje ?? 'Evolución registrada correctamente');
        }}
      />

      <DialogoConfirmacion
        abierto={Boolean(aArchivar)}
        titulo="¿Archivar este objetivo?"
        etiquetaConfirmar="Archivar"
        etiquetaProcesando="Archivando…"
        procesando={archivando}
        onConfirmar={confirmarArchivado}
        onCancelar={() => setAArchivar(null)}
      >
        Deja de calificarse y libera un lugar de los 4. Las calificaciones ya
        cargadas se conservan. Su descripción queda fija: desde la interfaz no
        se puede volver a activar.
      </DialogoConfirmacion>

      <Snackbar
        open={Boolean(aviso)}
        autoHideDuration={5000}
        onClose={() => setAviso('')}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert severity="success" onClose={() => setAviso('')} variant="filled">
          {aviso}
        </Alert>
      </Snackbar>
    </AppLayout>
  );
}

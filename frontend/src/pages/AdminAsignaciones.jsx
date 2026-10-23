// frontend/src/pages/AdminAsignaciones.jsx
// Pantalla del administrador: asignar y desasignar terapeutas a pacientes.
// Es la única que abre y cierra asignaciones; un terapeuta solo las consulta.
// No muestra datos clínicos (el endpoint tampoco los envía).

import { useMemo, useState } from 'react';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Container from '@mui/material/Container';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import Snackbar from '@mui/material/Snackbar';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';

import BarraAdmin from '../components/admin/BarraAdmin.jsx';
import ModalAsignar from '../components/asignaciones/ModalAsignar.jsx';
import DataTable from '../components/data/DataTable.jsx';
import { Cargando, EstadoError, EstadoVacio } from '../components/estado/index.js';
import DialogoConfirmacion from '../components/modal/DialogoConfirmacion.jsx';
import SeccionFamiliares from '../components/familiares/SeccionFamiliares.jsx';
import { hayCapacidad } from '../config/entregas.js';
import { usePeticion } from '../hooks/usePeticion.js';
import {
  cerrarAsignacion, listarPacientesAdmin, listarTerapeutas,
} from '../services/asignacionesService.js';

function estadoDe(paciente) {
  if (paciente.activo) return { etiqueta: 'En tratamiento', color: 'success' };
  return paciente.tipo_cierre === 'pausa'
    ? { etiqueta: 'En pausa', color: 'warning' }
    : { etiqueta: 'De alta', color: 'default' };
}

export default function AdminAsignaciones() {
  const pacientes = usePeticion(listarPacientesAdmin, []);
  const terapeutas = usePeticion(listarTerapeutas, []);
  const [busqueda, setBusqueda] = useState('');
  const [sinAsignar, setSinAsignar] = useState(false);
  const [familia, setFamilia] = useState(null);
  const [aAsignar, setAAsignar] = useState(null);
  const [aQuitar, setAQuitar] = useState(null); // { paciente, asignacion }
  const [procesando, setProcesando] = useState(false);
  const [aviso, setAviso] = useState('');

  const filas = useMemo(() => {
    const texto = busqueda.trim().toLowerCase();
    return (pacientes.datos?.pacientes ?? []).filter((p) => {
      if (sinAsignar && (!p.activo || p.asignaciones_vigentes.length > 0)) return false;
      if (!texto) return true;
      return `${p.nombre_completo} ${p.nro_historia}`.toLowerCase().includes(texto);
    });
  }, [pacientes.datos, busqueda, sinAsignar]);

  const pendientes = (pacientes.datos?.pacientes ?? [])
    .filter((p) => p.activo && p.asignaciones_vigentes.length === 0).length;

  const confirmarQuitar = async () => {
    setProcesando(true);
    try {
      const respuesta = await cerrarAsignacion(aQuitar.asignacion.id);
      setAviso(respuesta?.mensaje ?? 'Asignación cerrada.');
      pacientes.recargar();
    } catch (error) {
      setAviso(error.message);
    } finally {
      setAQuitar(null);
      setProcesando(false);
    }
  };

  const columnas = [
    {
      clave: 'paciente', etiqueta: 'Paciente', truncar: true,
      render: (p) => (
        <Box>
          <span className="texto-libre">{p.nombre_completo}</span>
          <Typography variant="caption" color="text.secondary" component="div">
            Historia {p.nro_historia}
          </Typography>
        </Box>
      ),
    },
    {
      clave: 'estado', etiqueta: 'Estado', ancho: 140,
      render: (p) => {
        const e = estadoDe(p);
        return <Chip size="small" color={e.color} label={e.etiqueta} />;
      },
    },
    {
      clave: 'responsables', etiqueta: 'Terapeuta asignado',
      render: (p) => (
        p.asignaciones_vigentes.length === 0 ? (
          <Typography variant="body2" color="text.secondary">Sin asignar</Typography>
        ) : (
          <Stack spacing={0.5}>
            {p.asignaciones_vigentes.map((a) => (
              <Stack key={a.id} direction="row" spacing={1} alignItems="center">
                <Chip size="small" className="texto-libre" label={a.terapeuta ?? '—'} />
                <Button
                  size="small" variant="text" color="inherit"
                  aria-label={`Quitar a ${a.terapeuta}`}
                  onClick={() => setAQuitar({ paciente: p, asignacion: a })}
                >
                  Quitar
                </Button>
              </Stack>
            ))}
          </Stack>
        )
      ),
    },
    {
      clave: 'acciones', etiqueta: '', ancho: 220, alinear: 'right',
      render: (p) => (
        <Stack direction="row" spacing={1} justifyContent="flex-end">
          {/* H16: con el paciente de baja nadie más puede quitar el acceso de la familia. */}
          {hayCapacidad('familiar.vincular') && (
            <Button size="small" variant="text" color="inherit" onClick={() => setFamilia(p)}>Familia</Button>
          )}
          {p.activo && (
            <Button size="small" variant="outlined" onClick={() => setAAsignar(p)}>Asignar</Button>
          )}
        </Stack>
      ),
    },
  ];

  return (
    <Box sx={{ minHeight: '100vh' }}>
      <BarraAdmin activa="asignaciones" />

      <Container maxWidth="lg" sx={{ py: 4 }}>
        <Typography variant="h4">Asignación de terapeutas</Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
          Defina qué terapeuta atiende a cada paciente. Solo el terapeuta asignado puede
          registrar sesiones y evoluciones; los terapeutas no pueden modificar estas asignaciones.
        </Typography>

        {pendientes > 0 && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            {pendientes === 1
              ? 'Hay 1 paciente en tratamiento sin terapeuta asignado.'
              : `Hay ${pendientes} pacientes en tratamiento sin terapeuta asignado.`}
          </Alert>
        )}

        <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 2 }}>
          <TextField
            size="small" sx={{ minWidth: 280 }} label="Buscar paciente"
            placeholder="Nombre, apellido o historia"
            value={busqueda} onChange={(e) => setBusqueda(e.target.value)}
          />
          <Button
            variant={sinAsignar ? 'contained' : 'outlined'} size="small"
            aria-pressed={sinAsignar} onClick={() => setSinAsignar((v) => !v)}
          >
            Solo sin asignar
          </Button>
        </Stack>

        {pacientes.cargando && <Cargando texto="Cargando los pacientes..." />}
        {pacientes.error && <EstadoError error={pacientes.error} onReintentar={pacientes.recargar} />}
        {pacientes.datos && !pacientes.cargando && !pacientes.error && (
          filas.length === 0 ? (
            <EstadoVacio titulo="No hay pacientes para mostrar" descripcion="Modifique la búsqueda o quite el filtro." />
          ) : (
            <DataTable columnas={columnas} filas={filas} claveFila={(p) => p.id} />
          )
        )}
      </Container>

      <ModalAsignar
        key={`asignar-${aAsignar?.id ?? 'ninguno'}`}
        abierto={Boolean(aAsignar)}
        paciente={aAsignar}
        terapeutas={terapeutas.datos?.terapeutas ?? []}
        onCerrar={() => setAAsignar(null)}
        onAsignado={(respuesta) => {
          pacientes.recargar();
          setAviso(respuesta?.mensaje ?? 'Asignación registrada.');
        }}
      />

      <DialogoConfirmacion
        abierto={Boolean(aQuitar)}
        titulo="¿Quitar esta asignación?"
        etiquetaConfirmar="Quitar asignación"
        etiquetaProcesando="Quitando…"
        procesando={procesando}
        onConfirmar={confirmarQuitar}
        onCancelar={() => setAQuitar(null)}
      >
        <strong>{aQuitar?.asignacion.terapeuta}</strong> dejará de ser responsable de{' '}
        {aQuitar?.paciente.nombre_completo} a partir de hoy. Las sesiones y evoluciones ya
        registradas se conservan. Si no queda otro terapeuta asignado, nadie podrá registrar
        sesiones nuevas hasta que se asigne uno.
      </DialogoConfirmacion>

      <Dialog open={Boolean(familia)} onClose={() => setFamilia(null)} maxWidth="md" fullWidth>
        <Box sx={{ px: 3, pt: 2.5 }}>
          <Typography variant="h5" className="texto-libre">Familia de {familia?.nombre_completo}</Typography>
          <Typography variant="body2" color="text.secondary">
            {familia?.activo
              ? 'Quiénes tienen acceso al portal con la evolución de este paciente.'
              : 'El paciente no está en tratamiento: solo se pueden quitar accesos.'}
          </Typography>
        </Box>
        <DialogContent sx={{ px: 1 }}>
          {familia && (
            <SeccionFamiliares paciente={familia} soloQuitar={!familia.activo} onAviso={setAviso} />
          )}
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2.5 }}>
          <Button variant="outlined" onClick={() => setFamilia(null)}>Cerrar</Button>
        </DialogActions>
      </Dialog>

      <Snackbar
        open={Boolean(aviso)} autoHideDuration={5000} onClose={() => setAviso('')}
        message={aviso}
      />
    </Box>
  );
}

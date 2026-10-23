// frontend/src/pages/Pacientes.jsx
// Listado de pacientes del centro.

import { useMemo, useState } from 'react';
import ToggleButton from '@mui/material/ToggleButton';
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup';
import Chip from '@mui/material/Chip';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import FormControlLabel from '@mui/material/FormControlLabel';
import Switch from '@mui/material/Switch';
import InputAdornment from '@mui/material/InputAdornment';
import TextField from '@mui/material/TextField';
import { useNavigate } from 'react-router-dom';

import Snackbar from '@mui/material/Snackbar';
import Alert from '@mui/material/Alert';

import AccountFlag from '../components/data/AccountFlag.jsx';
import DataTable from '../components/data/DataTable.jsx';
import GoalMeter from '../components/data/GoalMeter.jsx';
import PersonCell from '../components/data/PersonCell.jsx';
import AppLayout from '../components/layout/AppLayout.jsx';
import ModalAltaPaciente from '../components/pacientes/ModalAltaPaciente.jsx';
import { Cargando, EstadoError, EstadoVacio } from '../components/estado/index.js';
import { hayCapacidad } from '../config/entregas.js';
import { usePeticion } from '../hooks/usePeticion.js';
import { useAuth } from '../context/AuthContext.jsx';
import { listarTerapeutas } from '../services/asignacionesService.js';
import { listarPacientesConFiltros } from '../services/pacientesService.js';
import { useEstadoEnUrl } from '../hooks/useEstadoEnUrl.js';
import { formatearFecha, textoEdad } from '../utils/fechas.js';

export default function Pacientes() {
  const navigate = useNavigate();
  // En tratamiento (por defecto) o en pausa / con alta (F5.3). Va en la URL.
  const [estado, setEstado] = useEstadoEnUrl('estado', 'activos');
  const verInactivos = hayCapacidad('pacientes.pausa') && estado === 'inactivos';
  const { datos, cargando, error, recargar } = usePeticion(
    () => listarPacientesConFiltros(verInactivos ? { estado: 'inactivos' } : {}),
    [verInactivos],
  );
  const terapeutas = usePeticion(listarTerapeutas, []);
  const { perfil } = useAuth();
  const [busqueda, setBusqueda] = useState('');
  // «Mis pacientes» encendido por omisión: con el listado completo una
  // terapeuta nueva creía que todos eran suyos (usabilidad). Va en la URL.
  const [todosUrl, setTodosUrl] = useEstadoEnUrl('todos', '');
  const soloMios = todosUrl !== '1';
  const setSoloMios = (valor) => setTodosUrl(valor ? '' : '1');
  const conAsignaciones = hayCapacidad('asignaciones.gestionar');
  const [modalAbierto, setModalAbierto] = useState(false);
  const [aviso, setAviso] = useState('');

  // El listado se refresca contra el servidor en vez de insertar la fila a
  // mano: la lista es del servidor y así no hay dos versiones que puedan
  // divergir. No recarga la página, solo vuelve a pedir los datos.
  const alCrear = (respuesta) => {
    setBusqueda('');
    recargar();
    setAviso(respuesta?.mensaje ?? 'Paciente registrado correctamente');
  };

  const pacientes = useMemo(
    () => (datos?.pacientes ?? []).map((p) => ({ ...p, edad: textoEdad(p.fecha_nacimiento) })),
    [datos]
  );

  // El backend todavia no filtra por servidor, asi que se filtra aca.
  const filtrados = useMemo(() => {
    const texto = busqueda.trim().toLowerCase();
    return pacientes.filter((p) => {
      if (conAsignaciones && soloMios && !verInactivos && !p.asignado_a_mi) return false;
      if (!texto) return true;
      return `${p.nombre_completo} ${p.nro_historia}`.toLowerCase().includes(texto);
    });
  }, [pacientes, busqueda, soloMios, conAsignaciones, verInactivos]);

  const hayFiltro = Boolean(busqueda.trim()) || (conAsignaciones && soloMios && !verInactivos);

  const columnas = [
    {
      clave: 'nombre',
      etiqueta: 'Paciente',
      render: (p) => <PersonCell nombre={p.nombre_completo} meta={p.edad} />,
    },
    {
      clave: 'nro_historia',
      etiqueta: 'N° de historia',
      ancho: 132,
      render: (p) => (
        <Box component="span" sx={{ color: 'text.secondary' }}>
          {p.nro_historia}
        </Box>
      ),
    },
    {
      clave: 'diagnostico',
      etiqueta: 'Diagnóstico',
      ancho: 340,
      // Los diagnósticos reales son largos. Sin truncar, la fila crece y
      // la tabla pierde el ritmo denso; el texto completo queda en el
      // title del elemento.
      truncar: true,
      render: (p) => p.diagnostico || '—',
    },
    ...(conAsignaciones
      ? [{
          clave: 'responsable',
          etiqueta: 'Responsable',
          ancho: 200,
          truncar: true,
          render: (p) => (p.responsables?.length
            ? p.responsables.join(', ')
            : <Box component="span" sx={{ color: 'warning.main' }}>Sin asignar</Box>),
        }]
      : []),
    verInactivos
      ? {
          clave: 'estado',
          etiqueta: 'Estado',
          ancho: 200,
          render: (p) => (
            <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
              <Chip size="small" label={p.tipo_cierre === 'pausa' ? 'En pausa' : 'Alta'} color={p.tipo_cierre === 'pausa' ? 'warning' : 'default'} />
              {p.fecha_baja && <Box component="span" className="tabular" sx={{ fontSize: 13, color: 'text.secondary' }}>desde {formatearFecha(p.fecha_baja)}</Box>}
            </Box>
          ),
        }
      : {
          clave: 'objetivos_activos',
          etiqueta: 'Objetivos activos',
          ancho: 158,
          render: (p) => <GoalMeter valor={p.objetivos_activos} />,
        },
    {
      clave: 'tiene_login',
      etiqueta: 'Portal del paciente',
      ancho: 190,
      render: (p) => <AccountFlag tieneCuenta={p.tiene_login} />,
    },
  ];

  const total = datos?.total ?? 0;
  const subtitulo = cargando
    ? 'Cargando...'
    : hayFiltro
      ? `${filtrados.length} de ${total} pacientes`
      : verInactivos
        ? `${total} ${total === 1 ? 'paciente en pausa o con alta' : 'pacientes en pausa o con alta'}`
        : `${total} ${total === 1 ? 'paciente activo' : 'pacientes activos'}`;

  return (
    <AppLayout
      titulo="Pacientes"
      subtitulo={subtitulo}
      contadores={{ pacientes: verInactivos ? undefined : (total || undefined) }}
      acciones={
        <Button variant="contained" onClick={() => setModalAbierto(true)}>
          Agregar paciente
        </Button>
      }
    >
      {cargando && <Cargando texto="Cargando pacientes..." />}
      {error && <EstadoError error={error} onReintentar={recargar} />}

      {datos && !cargando && !error && (
        <>
          {hayCapacidad('pacientes.pausa') && (
            <ToggleButtonGroup
              exclusive size="small" value={verInactivos ? 'inactivos' : 'activos'}
              onChange={(_, v) => { if (v) { setEstado(v); setBusqueda(''); } }}
              aria-label="Qué pacientes mostrar" sx={{ mb: 2 }}
            >
              <ToggleButton value="activos" sx={{ textTransform: 'none', fontWeight: 600, px: 1.75 }}>En tratamiento</ToggleButton>
              <ToggleButton value="inactivos" sx={{ textTransform: 'none', fontWeight: 600, px: 1.75 }}>En pausa o con alta</ToggleButton>
            </ToggleButtonGroup>
          )}
          {total > 0 && (
            <Box sx={{ mb: 2, display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
              <TextField
                size="small"
                placeholder="Buscar por nombre o historia"
                value={busqueda}
                onChange={(e) => setBusqueda(e.target.value)}
                sx={{ width: 280 }}
                inputProps={{ 'aria-label': 'Buscar paciente' }}
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <Box component="span" aria-hidden="true" sx={{ color: 'text.disabled', fontSize: 14 }}>
                        ⌕
                      </Box>
                    </InputAdornment>
                  ),
                }}
              />
              {conAsignaciones && !verInactivos && (
                <FormControlLabel
                  control={<Switch checked={soloMios} onChange={(e) => setSoloMios(e.target.checked)} />}
                  label="Mis pacientes"
                />
              )}
            </Box>
          )}

          {total === 0 && verInactivos ? (
            <EstadoVacio
              titulo="No hay pacientes en pausa ni con alta"
              descripcion="Los pacientes cuyo tratamiento se pausa o termina aparecen aquí, para consultarlos o reactivarlos."
            />
          ) : total === 0 ? (
            <EstadoVacio
              titulo="Todavía no hay pacientes cargados"
              descripcion="Cuando se registre el primer paciente del centro aparecerá aquí, con su edad, su N° de historia y sus objetivos activos."
              acciones={
                <Button variant="contained" onClick={() => setModalAbierto(true)}>
                  Agregar paciente
                </Button>
              }
            />
          ) : filtrados.length === 0 ? (
            <EstadoVacio
              titulo="Ningún paciente coincide con la búsqueda"
              descripcion={soloMios && !busqueda.trim()
                ? 'No tiene pacientes asignados. Solicite la asignación al administrador.'
                : `No encontramos a nadie que coincida con “${busqueda.trim()}”. Pruebe con parte del apellido o con el número de historia.`}
              acciones={
                <Button variant="outlined" onClick={() => { setBusqueda(''); setSoloMios(false); }}>
                  Limpiar filtros
                </Button>
              }
            />
          ) : (
            <DataTable
              columnas={columnas}
              filas={filtrados}
              onAbrirFila={(p) => navigate(`/pacientes/${p.id}`)}
              etiquetaFila={(p) => `Abrir la ficha de ${p.nombre_completo}`}
            />
          )}
        </>
      )}

      <ModalAltaPaciente
        abierto={modalAbierto}
        onCerrar={() => setModalAbierto(false)}
        onCreado={alCrear}
        terapeutas={terapeutas.datos?.terapeutas ?? []}
        idTerapeutaActual={perfil?.id ?? null}
        sugerenciaHistoria={datos?.siguiente_nro_historia ?? ''}
      />

      <Snackbar
        open={Boolean(aviso)}
        autoHideDuration={5000}
        onClose={() => setAviso('')}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        {/* El texto es el p_mensaje del procedimiento, sin reescribir */}
        <Alert severity="success" onClose={() => setAviso('')} variant="filled">
          {aviso}
        </Alert>
      </Snackbar>
    </AppLayout>
  );
}

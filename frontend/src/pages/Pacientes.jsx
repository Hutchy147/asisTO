// frontend/src/pages/Pacientes.jsx
// Listado de pacientes del centro.

import { useMemo, useState } from 'react';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
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
import { usePeticion } from '../hooks/usePeticion.js';
import { listarPacientes } from '../services/pacientesService.js';
import { textoEdad } from '../utils/fechas.js';

export default function Pacientes() {
  const navigate = useNavigate();
  const { datos, cargando, error, recargar } = usePeticion(listarPacientes, []);
  const [busqueda, setBusqueda] = useState('');
  const [modalAbierto, setModalAbierto] = useState(false);
  const [aviso, setAviso] = useState('');

  // El listado se refresca contra el servidor en vez de insertar la fila a
  // mano: la lista es del servidor y así no hay dos versiones que puedan
  // divergir. No recarga la página, solo vuelve a pedir los datos.
  const alCrear = (respuesta) => {
    setBusqueda('');
    recargar();
    setAviso(respuesta?.mensaje ?? 'Paciente dado de alta correctamente');
  };

  const pacientes = useMemo(
    () => (datos?.pacientes ?? []).map((p) => ({ ...p, edad: textoEdad(p.fecha_nacimiento) })),
    [datos]
  );

  // El backend todavia no filtra por servidor, asi que se filtra aca.
  const filtrados = useMemo(() => {
    const texto = busqueda.trim().toLowerCase();
    if (!texto) return pacientes;
    return pacientes.filter((p) =>
      `${p.nombre_completo} ${p.nro_historia}`.toLowerCase().includes(texto)
    );
  }, [pacientes, busqueda]);

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
    {
      clave: 'objetivos_activos',
      etiqueta: 'Objetivos activos',
      ancho: 158,
      render: (p) => <GoalMeter valor={p.objetivos_activos} />,
    },
    {
      clave: 'tiene_login',
      etiqueta: 'Cuenta',
      ancho: 128,
      render: (p) => <AccountFlag tieneCuenta={p.tiene_login} />,
    },
  ];

  const total = datos?.total ?? 0;
  const subtitulo = cargando
    ? 'Cargando...'
    : busqueda.trim()
      ? `${filtrados.length} de ${total} pacientes`
      : `${total} ${total === 1 ? 'paciente activo' : 'pacientes activos'}`;

  return (
    <AppLayout
      titulo="Pacientes"
      subtitulo={subtitulo}
      contadores={{ pacientes: total || undefined }}
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
          {total > 0 && (
            <Box sx={{ mb: 2, display: 'flex', gap: 2, alignItems: 'center' }}>
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
            </Box>
          )}

          {total === 0 ? (
            <EstadoVacio
              titulo="Todavía no hay pacientes cargados"
              descripcion="Cuando des de alta al primer paciente del centro va a aparecer acá, con su edad, su N° de historia y sus objetivos activos."
              acciones={
                <Button variant="contained" onClick={() => setModalAbierto(true)}>
                  Agregar paciente
                </Button>
              }
            />
          ) : filtrados.length === 0 ? (
            <EstadoVacio
              titulo="Ningún paciente coincide con la búsqueda"
              descripcion={`No encontramos a nadie que coincida con “${busqueda.trim()}”. Probá con parte del apellido o con el número de historia.`}
              acciones={
                <Button variant="outlined" onClick={() => setBusqueda('')}>
                  Limpiar búsqueda
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

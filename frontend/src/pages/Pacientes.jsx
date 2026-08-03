// frontend/src/pages/Pacientes.jsx
// Listado de pacientes del centro.

import { useMemo, useState } from 'react';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import InputAdornment from '@mui/material/InputAdornment';
import TextField from '@mui/material/TextField';
import { useNavigate } from 'react-router-dom';

import AccountFlag from '../components/data/AccountFlag.jsx';
import DataTable from '../components/data/DataTable.jsx';
import GoalMeter from '../components/data/GoalMeter.jsx';
import PersonCell from '../components/data/PersonCell.jsx';
import AppLayout from '../components/layout/AppLayout.jsx';
import { Cargando, EstadoError, EstadoVacio } from '../components/estado/index.js';
import { usePeticion } from '../hooks/usePeticion.js';
import { listarPacientes } from '../services/pacientesService.js';

/** Edad en años a partir de la fecha de nacimiento en formato ISO. */
export function edadDesde(iso) {
  if (!iso) return null;
  const [anio, mes, dia] = iso.split('-').map(Number);
  const hoy = new Date();
  let edad = hoy.getFullYear() - anio;
  const mesActual = hoy.getMonth() + 1;
  if (mesActual < mes || (mesActual === mes && hoy.getDate() < dia)) edad -= 1;
  return edad;
}

/** "7 años" / "8 meses" para los pacientes de menos de un año. */
function textoEdad(iso) {
  const edad = edadDesde(iso);
  if (edad === null) return '';
  if (edad >= 1) return `${edad} ${edad === 1 ? 'año' : 'años'}`;

  const nacimiento = new Date(iso);
  const hoy = new Date();
  const meses = Math.max(
    0,
    (hoy.getFullYear() - nacimiento.getFullYear()) * 12 + hoy.getMonth() - nacimiento.getMonth()
  );
  return `${meses} ${meses === 1 ? 'mes' : 'meses'}`;
}

export default function Pacientes() {
  const navigate = useNavigate();
  const { datos, cargando, error, recargar } = usePeticion(listarPacientes, []);
  const [busqueda, setBusqueda] = useState('');

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
        // TODO: abre el modal de alta cuando se implemente (fase siguiente)
        <Button variant="contained" disabled>
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
                <Button variant="contained" disabled>
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
    </AppLayout>
  );
}

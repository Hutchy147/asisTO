// frontend/src/pages/Pacientes.jsx
// Listado de pacientes. ESTRUCTURA PROVISORIA, sin diseño final.

import { useMemo, useState } from 'react';
import Chip from '@mui/material/Chip';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import { useNavigate } from 'react-router-dom';

import LayoutTerapeuta from '../components/LayoutTerapeuta.jsx';
import { Cargando, EstadoError, EstadoVacio } from '../components/estado/index.js';
import { usePeticion } from '../hooks/usePeticion.js';
import { MAXIMO_OBJETIVOS_ACTIVOS } from '../services/objetivosService.js';
import { listarPacientes } from '../services/pacientesService.js';

export default function Pacientes() {
  const navigate = useNavigate();
  const { datos, cargando, error, recargar } = usePeticion(listarPacientes, []);
  const [busqueda, setBusqueda] = useState('');

  // El backend todavia no filtra por servidor, asi que se filtra aca.
  const filtrados = useMemo(() => {
    const lista = datos?.pacientes ?? [];
    const texto = busqueda.trim().toLowerCase();
    if (!texto) return lista;
    return lista.filter((p) =>
      `${p.nombre_completo} ${p.nro_historia}`.toLowerCase().includes(texto)
    );
  }, [datos, busqueda]);

  return (
    <LayoutTerapeuta titulo="Pacientes">
      {cargando && <Cargando texto="Cargando pacientes..." />}
      {error && <EstadoError error={error} onReintentar={recargar} />}

      {datos && !cargando && !error && (
        <>
          <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 2 }}>
            <TextField
              size="small"
              label="Buscar por nombre o historia"
              value={busqueda}
              onChange={(e) => setBusqueda(e.target.value)}
              sx={{ minWidth: 320 }}
            />
            <Typography variant="body2" color="text.secondary">
              {filtrados.length} de {datos.total}
            </Typography>
          </Stack>

          {datos.total === 0 ? (
            <EstadoVacio
              titulo="Todavía no hay pacientes cargados"
              descripcion="Cuando se dé de alta el primer paciente va a aparecer acá."
            />
          ) : filtrados.length === 0 ? (
            <EstadoVacio
              titulo="Ningún paciente coincide con la búsqueda"
              descripcion={`No se encontró nada para "${busqueda}".`}
              textoAccion="Limpiar búsqueda"
              onAccion={() => setBusqueda('')}
            />
          ) : (
            <TableContainer component={Paper} elevation={1}>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>Paciente</TableCell>
                    <TableCell>Historia</TableCell>
                    <TableCell>Fecha de nacimiento</TableCell>
                    <TableCell>Objetivos activos</TableCell>
                    <TableCell>Acceso</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {filtrados.map((paciente) => (
                    <TableRow
                      key={paciente.id}
                      hover
                      sx={{ cursor: 'pointer' }}
                      onClick={() => navigate(`/pacientes/${paciente.id}`)}
                    >
                      <TableCell>{paciente.nombre_completo}</TableCell>
                      <TableCell>{paciente.nro_historia}</TableCell>
                      <TableCell>{paciente.fecha_nacimiento}</TableCell>
                      <TableCell>
                        <Chip
                          size="small"
                          label={`${paciente.objetivos_activos} de ${MAXIMO_OBJETIVOS_ACTIVOS}`}
                          color={
                            paciente.objetivos_activos >= MAXIMO_OBJETIVOS_ACTIVOS
                              ? 'warning'
                              : 'default'
                          }
                        />
                      </TableCell>
                      <TableCell>
                        {/* Sin login NO es un dato faltante: es lo normal
                            en los pacientes menores de edad. */}
                        <Typography variant="body2" color="text.secondary">
                          {paciente.tiene_login ? 'Con cuenta' : 'Sin cuenta'}
                        </Typography>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </>
      )}
    </LayoutTerapeuta>
  );
}

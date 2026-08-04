// frontend/src/pages/Panel.jsx
// Panel del día: la pantalla donde cae el terapeuta al entrar.

import { useMemo, useState } from 'react';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Grid from '@mui/material/Grid';
import Snackbar from '@mui/material/Snackbar';
import Typography from '@mui/material/Typography';
import { useNavigate } from 'react-router-dom';

import DataTable from '../components/data/DataTable.jsx';
import PersonCell from '../components/data/PersonCell.jsx';
import SesionEstadoChip from '../components/data/SesionEstadoChip.jsx';
import StatTile from '../components/data/StatTile.jsx';
import ModalCargarEvolucion from '../components/evoluciones/ModalCargarEvolucion.jsx';
import AppLayout from '../components/layout/AppLayout.jsx';
import { Cargando, EstadoError, EstadoVacio } from '../components/estado/index.js';
import { usePeticion } from '../hooks/usePeticion.js';
import { listarPacientes } from '../services/pacientesService.js';
import {
  faltaEvolucion, listarPendientesDeEvolucion, listarSesiones, listarSesionesDeHoy,
} from '../services/sesionesService.js';
import { formatearFecha, textoEdad } from '../utils/fechas.js';

const DIAS_LARGOS = ['domingo', 'lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado'];
const MESES = [
  'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
  'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
];

function aIso(fecha) {
  const mes = String(fecha.getMonth() + 1).padStart(2, '0');
  const dia = String(fecha.getDate()).padStart(2, '0');
  return `${fecha.getFullYear()}-${mes}-${dia}`;
}

/** Lunes a domingo de la semana en curso. */
function semanaEnCurso() {
  const hoy = new Date();
  const lunes = new Date(hoy);
  lunes.setDate(hoy.getDate() - ((hoy.getDay() + 6) % 7));
  const domingo = new Date(lunes);
  domingo.setDate(lunes.getDate() + 6);
  return { desde: aIso(lunes), hasta: aIso(domingo) };
}

/** Panel con encabezado. */
function Bloque({ titulo, descripcion, acciones, children }) {
  return (
    <Box
      sx={(t) => ({
        backgroundColor: t.palette.superficie.tarjeta,
        border: `1px solid ${t.palette.superficie.borde}`,
        borderRadius: `${t.formas.md}px`,
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
      })}
    >
      <Box
        sx={(t) => ({
          display: 'flex',
          alignItems: 'flex-start',
          gap: 2,
          px: 2.25,
          py: 1.5,
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
      <Box sx={{ flex: 1, minWidth: 0 }}>{children}</Box>
    </Box>
  );
}

export default function Panel() {
  const navigate = useNavigate();
  const [idEvolucion, setIdEvolucion] = useState(null);
  const [aviso, setAviso] = useState('');

  const semana = useMemo(semanaEnCurso, []);

  const hoy = usePeticion(listarSesionesDeHoy, []);
  const pendientes = usePeticion(listarPendientesDeEvolucion, []);
  const pacientes = usePeticion(listarPacientes, []);
  const deLaSemana = usePeticion(() => listarSesiones(semana), [semana.desde, semana.hasta]);

  const fecha = new Date();
  const rotuloHoy = `${DIAS_LARGOS[fecha.getDay()]} ${fecha.getDate()} de ${MESES[fecha.getMonth()]} de ${fecha.getFullYear()}`;

  // --- Cifras de la semana en curso ---
  const resumenSemana = useMemo(() => {
    const lista = deLaSemana.datos?.sesiones ?? [];
    const conEvolucion = lista.filter((s) => s.admite_evolucion);
    return {
      ausencias: lista.filter((s) => s.estado === 'ausencia').length,
      calificados: conEvolucion.reduce((suma, s) => suma + s.objetivos.calificados, 0),
      total: conEvolucion.reduce((suma, s) => suma + s.objetivos.total, 0),
    };
  }, [deLaSemana.datos]);

  const faltanHoy = (hoy.datos?.sesiones ?? []).filter(faltaEvolucion).length;

  const recargarTodo = () => {
    hoy.recargar();
    pendientes.recargar();
    deLaSemana.recargar();
  };

  const columnasHoy = [
    {
      clave: 'hora_inicio',
      etiqueta: 'Hora',
      ancho: 78,
      render: (s) => (
        <Box component="span" sx={{ fontWeight: 600 }}>
          {s.hora_inicio?.slice(0, 5)}
        </Box>
      ),
    },
    {
      clave: 'paciente',
      etiqueta: 'Paciente',
      render: (s) => <PersonCell nombre={s.paciente.nombre_completo} meta={s.paciente.nro_historia} />,
    },
    {
      clave: 'objetivos',
      etiqueta: 'Objetivos',
      ancho: 100,
      alinear: 'right',
      // En una ausencia no corresponde calificar: "0 de 3" se leería como
      // trabajo pendiente. Mismo criterio que en la ficha.
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
      clave: 'estado',
      etiqueta: 'Estado',
      ancho: 210,
      render: (s) => (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <SesionEstadoChip estado={s.estado} />
          {/* Mismas palabras que en el calendario: el pendiente NO es un
              estado de la sesión, es trabajo por hacer. */}
          {faltaEvolucion(s) && (
            <Box component="span" sx={{ fontSize: 11, fontWeight: 500 }}>
              Falta la evolución
            </Box>
          )}
        </Box>
      ),
    },
  ];

  return (
    <AppLayout
      titulo="Panel del día"
      subtitulo={rotuloHoy}
      contadores={{ panel: hoy.datos?.total || undefined, pacientes: pacientes.datos?.total || undefined }}
      acciones={
        <Button variant="outlined" onClick={() => navigate('/calendario')}>
          Ir al calendario
        </Button>
      }
    >
      {/* --- Tarjetas de resumen --- */}
      <Grid container spacing={1.5} sx={{ mb: 2 }}>
        <Grid item xs={12} sm={4}>
          <StatTile
            etiqueta="Sesiones de hoy"
            valor={hoy.datos?.total ?? '—'}
            nota={
              faltanHoy > 0
                ? `${faltanHoy} ${faltanHoy === 1 ? 'pendiente' : 'pendientes'} de evolución`
                : 'Todas con evolución cargada'
            }
          />
        </Grid>
        <Grid item xs={12} sm={4}>
          <StatTile
            etiqueta="Ausencias de la semana"
            valor={deLaSemana.datos ? resumenSemana.ausencias : '—'}
            // Solo el total. El desglose entre con aviso y sin aviso no
            // existe en el modelo de datos: mostrarlo sería inventarlo.
            nota="Semana en curso"
          />
        </Grid>
        <Grid item xs={12} sm={4}>
          <StatTile
            etiqueta="Objetivos calificados"
            valor={deLaSemana.datos ? resumenSemana.calificados : '—'}
            unidad={deLaSemana.datos ? `de ${resumenSemana.total}` : undefined}
            nota="Semana en curso"
          />
        </Grid>
      </Grid>

      <Grid container spacing={2}>
        {/* --- Agenda de hoy --- */}
        <Grid item xs={12} lg={8}>
          <Bloque titulo="Agenda de hoy" descripcion="Ordenadas por hora de inicio">
            {hoy.cargando && <Cargando texto="Buscando las sesiones de hoy..." />}
            {hoy.error && <EstadoError error={hoy.error} onReintentar={hoy.recargar} />}
            {hoy.datos && !hoy.cargando && !hoy.error && (
              hoy.datos.total === 0 ? (
                <EstadoVacio
                  plano
                  titulo="No hay sesiones hoy"
                  descripcion="Es lo normal un fin de semana o un día sin agenda. Podés registrar una desde el calendario."
                  acciones={
                    <Button variant="outlined" onClick={() => navigate('/calendario')}>
                      Ir al calendario
                    </Button>
                  }
                />
              ) : (
                <DataTable
                  columnas={columnasHoy}
                  filas={hoy.datos.sesiones}
                  onAbrirFila={(s) => setIdEvolucion(s.id)}
                  etiquetaFila={(s) => `Abrir la sesión de ${s.paciente.nombre_completo}`}
                />
              )
            )}
          </Bloque>
        </Grid>

        <Grid item xs={12} lg={4}>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, height: '100%' }}>
            {/* --- Evoluciones pendientes --- */}
            <Bloque
              titulo="Evoluciones pendientes"
              descripcion={
                pendientes.datos?.total > 0
                  ? `${pendientes.datos.total} ${pendientes.datos.total === 1 ? 'sesión' : 'sesiones'} sin evolución cargada`
                  : 'Sesiones ya ocurridas sin evolución'
              }
            >
              {pendientes.cargando && <Cargando texto="Revisando..." minHeight={120} />}
              {pendientes.error && (
                <EstadoError error={pendientes.error} onReintentar={pendientes.recargar} />
              )}
              {pendientes.datos && !pendientes.cargando && !pendientes.error && (
                pendientes.datos.total === 0 ? (
                  // Este vacío es el estado BUENO: el terapeuta está al
                  // día. No se dibuja como una carencia.
                  <EstadoVacio
                    plano
                    titulo="Estás al día"
                    descripcion="Todas las sesiones ya ocurridas tienen su evolución cargada. Las ausencias no cuentan: no llevan evolución."
                  />
                ) : (
                  <Box sx={{ maxHeight: 320, overflow: 'auto' }}>
                    {pendientes.datos.sesiones.slice(0, 8).map((sesion) => (
                      <Box
                        key={sesion.id}
                        component="button"
                        type="button"
                        aria-label={`Cargar evolución de ${sesion.paciente.nombre_completo}`}
                        onClick={() => setIdEvolucion(sesion.id)}
                        sx={(t) => ({
                          display: 'flex',
                          alignItems: 'center',
                          gap: 1,
                          width: '100%',
                          px: 2.25,
                          py: 1.25,
                          border: 0,
                          borderBottom: `1px solid ${t.palette.superficie.borde}`,
                          background: 'transparent',
                          font: 'inherit',
                          textAlign: 'left',
                          cursor: 'pointer',
                          '&:hover': { backgroundColor: t.palette.superficie.hundida },
                          '&:focus-visible': { outline: 'none', boxShadow: `inset ${t.foco.anillo}` },
                        })}
                      >
                        <Box sx={{ flex: 1, minWidth: 0 }}>
                          <Box sx={{ fontSize: 13, fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {sesion.paciente.nombre_completo}
                          </Box>
                          <Box className="tabular" sx={{ fontSize: 12, color: 'text.secondary' }}>
                            {formatearFecha(sesion.fecha)} · {sesion.hora_inicio?.slice(0, 5)}
                          </Box>
                        </Box>
                        <SesionEstadoChip estado={sesion.estado} />
                      </Box>
                    ))}
                    {pendientes.datos.total > 8 && (
                      <Box sx={{ px: 2.25, py: 1.25, fontSize: 12, color: 'text.secondary' }}>
                        y {pendientes.datos.total - 8} más
                      </Box>
                    )}
                  </Box>
                )
              )}
            </Bloque>

            {/* --- Pacientes activos --- */}
            <Bloque
              titulo="Pacientes activos"
              descripcion={
                pacientes.datos ? `${pacientes.datos.total} en seguimiento` : 'Cargando...'
              }
              acciones={
                <Button size="small" variant="outlined" onClick={() => navigate('/pacientes')}>
                  Ver todos
                </Button>
              }
            >
              {pacientes.cargando && <Cargando texto="Cargando..." minHeight={120} />}
              {pacientes.error && (
                <EstadoError error={pacientes.error} onReintentar={pacientes.recargar} />
              )}
              {pacientes.datos && !pacientes.cargando && !pacientes.error && (
                pacientes.datos.total === 0 ? (
                  <EstadoVacio
                    plano
                    titulo="Todavía no hay pacientes cargados"
                    descripcion="Cuando des de alta al primero va a aparecer acá."
                    acciones={
                      <Button variant="contained" onClick={() => navigate('/pacientes')}>
                        Agregar paciente
                      </Button>
                    }
                  />
                ) : (
                  // Acceso rápido, no la grilla completa: esa ya tiene su
                  // pantalla propia.
                  <Box>
                    {pacientes.datos.pacientes.slice(0, 5).map((paciente) => (
                      <Box
                        key={paciente.id}
                        component="button"
                        type="button"
                        onClick={() => navigate(`/pacientes/${paciente.id}`)}
                        sx={(t) => ({
                          display: 'flex',
                          alignItems: 'center',
                          gap: 1,
                          width: '100%',
                          px: 2.25,
                          py: 1,
                          border: 0,
                          borderBottom: `1px solid ${t.palette.superficie.borde}`,
                          background: 'transparent',
                          font: 'inherit',
                          textAlign: 'left',
                          cursor: 'pointer',
                          '&:hover': { backgroundColor: t.palette.superficie.hundida },
                          '&:focus-visible': { outline: 'none', boxShadow: `inset ${t.foco.anillo}` },
                        })}
                      >
                        <Box sx={{ flex: 1, minWidth: 0 }}>
                          <PersonCell
                            nombre={paciente.nombre_completo}
                            meta={textoEdad(paciente.fecha_nacimiento)}
                          />
                        </Box>
                        <Box className="tabular" sx={{ fontSize: 12, color: 'text.secondary' }}>
                          {paciente.objetivos_activos} de 4
                        </Box>
                      </Box>
                    ))}
                  </Box>
                )
              )}
            </Bloque>
          </Box>
        </Grid>
      </Grid>

      <ModalCargarEvolucion
        key={idEvolucion ?? 'sin-sesion'}
        abierto={Boolean(idEvolucion)}
        idSesion={idEvolucion}
        onCerrar={() => setIdEvolucion(null)}
        onCargada={(respuesta) => {
          recargarTodo();
          setAviso(respuesta?.mensaje ?? 'Evolución registrada correctamente');
        }}
      />

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

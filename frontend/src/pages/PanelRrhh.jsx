// frontend/src/pages/PanelRrhh.jsx
// Panel de RRHH — consulta de asistencias. SOLO LECTURA.
//
// Contrato: docs/api-rrhh.md. Un solo endpoint, GET /rrhh/reporte-sesiones.
//
// QUE NO HAY EN ESTA PANTALLA, Y ES A PROPOSITO:
//
//   * CERO CONTENIDO CLINICO. Ni notas, ni evoluciones, ni objetivos, ni
//     diagnostico. El endpoint directamente no los devuelve (ver
//     COLUMNAS_REPORTE en rrhh_service.py), asi que aca no hay nada que
//     filtrar: lo que no llega no se puede mostrar por accidente.
//
//   * NINGUNA TASA NI PORCENTAJE DE ASISTENCIA. No es un olvido. Hasta el
//     2026-09-10 el formulario traia `completa` preseleccionada, asi que en
//     el periodo viejo ese estado NO distingue una declaracion de una
//     omision: en `asisto` son 502 de 644 sesiones. Un porcentaje calculado
//     sobre eso mezclaria dos cosas distintas en un solo numero que despues
//     nadie puede desarmar. Se muestran RECUENTOS.
//
//   * NO SE ESCRIBE NADA. `observaciones_rrhh` existe como tabla
//     (schema.sql) pero no tiene endpoint ni servicio: es un camino de
//     escritura desde RRHH y eso es otro lote.

import { useEffect, useMemo, useState } from 'react';
import AppBar from '@mui/material/AppBar';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Container from '@mui/material/Container';
import Grid from '@mui/material/Grid';
import MenuItem from '@mui/material/MenuItem';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Toolbar from '@mui/material/Toolbar';
import Typography from '@mui/material/Typography';

import DataTable from '../components/data/DataTable.jsx';
import PersonCell from '../components/data/PersonCell.jsx';
import SesionEstadoChip from '../components/data/SesionEstadoChip.jsx';
import StatTile from '../components/data/StatTile.jsx';
import { Aviso, Cargando, EstadoError, EstadoVacio } from '../components/estado/index.js';
import { useAuth } from '../context/AuthContext.jsx';
import { usePeticion } from '../hooks/usePeticion.js';
import {
  ORIGENES_AUSENCIA, obtenerReporteSesiones, terapeutasDelReporte,
} from '../services/rrhhService.js';
import { formatearFecha } from '../utils/fechas.js';

// Ventana por omision: los ultimos 90 dias.
//
// POR QUE NO "EL MES EN CURSO", que seria lo natural en un panel
// administrativo: un panel que abre vacio se lee como roto, y el mes en
// curso puede tener dos sesiones o ninguna segun el dia que se abra. 90 dias
// es lo bastante ancho para que SIEMPRE haya con que dibujar y lo bastante
// angosto para no acercarse al tope de 366 del backend.
const DIAS_POR_DEFECTO = 90;

// Tope de filas DIBUJADAS. No es un tope de la consulta.
//
// POR QUE EXISTE: con la base de demostracion, 90 dias son 630 sesiones, y
// dibujar 630 filas de una deja al navegador pegado — medido en Chrome real,
// con la pestana dejando de responder a capturas. En una demostracion en
// vivo eso se ve como una aplicacion rota.
//
// LO QUE NO HACE: no toca los numeros. El resumen y los tres baldes salen
// del endpoint y se calculan sobre TODAS las sesiones del periodo, no sobre
// las que se alcanzan a dibujar. Por eso el pie dice cuantas hay en total:
// un listado recortado que no lo dijera si estaria mintiendo.
const MAXIMO_FILAS_VISIBLES = 100;

function iso(fecha) {
  return fecha.toISOString().slice(0, 10);
}

function ventanaInicial() {
  const hasta = new Date();
  const desde = new Date();
  desde.setDate(desde.getDate() - DIAS_POR_DEFECTO);
  return { desde: iso(desde), hasta: iso(hasta) };
}

export default function PanelRrhh() {
  const { usuario, perfil, logout } = useAuth();
  const inicial = useMemo(ventanaInicial, []);

  // El filtro que se EDITA y el que se APLICO son dos cosas distintas: sin
  // separarlos, cada tecla en el campo de fecha dispara una peticion y a
  // mitad de escribir "2026-07-01" se piden rangos absurdos.
  const [borrador, setBorrador] = useState({ ...inicial, idTerapeuta: '' });
  const [aplicado, setAplicado] = useState({ ...inicial, idTerapeuta: '' });

  const reporte = usePeticion(
    () => obtenerReporteSesiones(aplicado),
    [aplicado.desde, aplicado.hasta, aplicado.idTerapeuta]
  );

  const sesiones = reporte.datos?.sesiones ?? [];
  const resumen = reporte.datos?.resumen;

  // Los terapeutas del filtro salen del reporte SIN filtrar. Si salieran del
  // reporte ya filtrado, al elegir uno la lista se quedaria con ese solo y no
  // habria como volver a los demas.
  //
  // VA EN useEffect Y NO EN useMemo. La primera version usaba useMemo, que
  // corre DURANTE el render: llamar a setState ahi hace que React descarte y
  // rehaga el render, y en esa pasada se perdia el cambio del Select. El
  // sintoma era que elegir un terapeuta no disparaba ninguna peticion — se
  // vio en el log del backend, que no registraba la consulta filtrada.
  const [terapeutas, setTerapeutas] = useState([]);
  useEffect(() => {
    if (!aplicado.idTerapeuta && reporte.datos) {
      setTerapeutas(terapeutasDelReporte(reporte.datos.sesiones));
    }
  }, [reporte.datos, aplicado.idTerapeuta]);

  const columnas = [
    {
      clave: 'fecha',
      etiqueta: 'Fecha',
      ancho: 130,
      render: (s) => formatearFecha(s.fecha),
    },
    {
      clave: 'hora_inicio',
      etiqueta: 'Hora',
      ancho: 72,
      render: (s) => s.hora_inicio ?? '—',
    },
    {
      clave: 'terapeuta',
      etiqueta: 'Terapeuta',
      // El id viaja en la respuesta y se muestra como META, chico y debajo
      // del nombre: identifica a dos homonimos sin ocupar la pantalla. El
      // nombre es para leer; el id, para distinguir.
      render: (s) => <PersonCell nombre={s.terapeuta} meta={`id ${s.id_terapeuta}`} />,
    },
    {
      clave: 'paciente',
      etiqueta: 'Paciente',
      render: (s) => <PersonCell nombre={s.paciente} meta={s.nro_historia} />,
    },
    {
      clave: 'estado',
      etiqueta: 'Estado',
      ancho: 128,
      render: (s) => <SesionEstadoChip estado={s.estado} />,
    },
    {
      clave: 'ausencia_de',
      etiqueta: 'Quién faltó',
      ancho: 140,
      render: (s) => {
        if (s.estado !== 'ausencia') return <Box component="span" sx={{ color: 'text.disabled' }}>—</Box>;
        const origen = ORIGENES_AUSENCIA.find((o) => o.clave === (s.ausencia_de ?? 'sin_declarar'));
        return (
          <Box component="span" sx={{ fontSize: 13 }}>
            {origen?.etiqueta ?? s.ausencia_de}
          </Box>
        );
      },
    },
    {
      clave: 'superposiciones',
      etiqueta: 'Superpuestas',
      ancho: 116,
      alinear: 'right',
      // Ya venia en el endpoint desde el primer lote: cuenta cuantas otras
      // sesiones del MISMO terapeuta pisan ese horario, sobre toda su agenda
      // y no solo sobre el periodo filtrado. Sirve para detectar cargas mal
      // hechas, que es trabajo administrativo, no clinico.
      render: (s) => (
        s.superposiciones > 0
          ? <Box component="span" sx={{ fontWeight: 600, color: 'warning.main' }}>{s.superposiciones}</Box>
          : <Box component="span" sx={{ color: 'text.disabled' }}>0</Box>
      ),
    },
  ];

  const aplicar = (evento) => {
    evento?.preventDefault();
    setAplicado({ ...borrador });
  };

  return (
    <Box sx={{ minHeight: '100vh' }}>
      <AppBar
        position="static"
        elevation={0}
        sx={(theme) => ({ backgroundColor: theme.palette.roles.rrhh.fg })}
      >
        <Toolbar>
          <Typography variant="h6" sx={{ flexGrow: 1 }}>AsisTO</Typography>
          <Stack direction="row" spacing={2} alignItems="center">
            {/* texto-libre: el nombre sale de `usuarios` y lo escribe una
                persona. Sin esto, un apellido largo sin espacios empuja el
                boton de cerrar sesion fuera de la barra. Los nombres de las
                FILAS van por PersonCell, que recorta con textOverflow. */}
            <Typography variant="body2" className="texto-libre" noWrap>
              {usuario?.nombre_completo}
            </Typography>
            <Button color="inherit" variant="outlined" onClick={logout}>
              Cerrar sesión
            </Button>
          </Stack>
        </Toolbar>
      </AppBar>

      <Container maxWidth="lg" sx={{ py: 4 }}>
        <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 0.5 }}>
          <Typography variant="h4">Panel de RRHH</Typography>
          <Chip
            label="rrhh"
            sx={(theme) => ({
              backgroundColor: theme.palette.roles.rrhh.bg,
              color: theme.palette.roles.rrhh.fg,
            })}
          />
        </Stack>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
          Consulta de asistencias{perfil?.nro_legajo ? ` · legajo ${perfil.nro_legajo}` : ''}
        </Typography>

        {/* --- Período y filtro --- */}
        <Box
          component="form"
          onSubmit={aplicar}
          sx={(t) => ({
            display: 'flex', flexWrap: 'wrap', gap: 2, alignItems: 'flex-end',
            p: 2, mb: 3,
            backgroundColor: t.palette.superficie.tarjeta,
            border: `1px solid ${t.palette.superficie.borde}`,
            borderRadius: `${t.formas.md}px`,
          })}
        >
          <TextField
            label="Desde" type="date" size="small"
            InputLabelProps={{ shrink: true }}
            value={borrador.desde}
            onChange={(e) => setBorrador({ ...borrador, desde: e.target.value })}
          />
          <TextField
            label="Hasta" type="date" size="small"
            InputLabelProps={{ shrink: true }}
            value={borrador.hasta}
            onChange={(e) => setBorrador({ ...borrador, hasta: e.target.value })}
          />
          <TextField
            select label="Terapeuta" size="small" sx={{ minWidth: 220 }}
            value={borrador.idTerapeuta}
            onChange={(e) => setBorrador({ ...borrador, idTerapeuta: e.target.value })}
          >
            <MenuItem value="">Todos</MenuItem>
            {terapeutas.map((t) => (
              <MenuItem key={t.id} value={t.id}>{t.nombre}</MenuItem>
            ))}
          </TextField>
          <Button type="submit" variant="contained">Ver período</Button>
        </Box>

        {reporte.cargando && <Cargando texto="Buscando las sesiones del período..." />}
        {reporte.error && <EstadoError error={reporte.error} onReintentar={reporte.recargar} />}

        {resumen && !reporte.cargando && !reporte.error && (
          <>
            {/* --- Recuento del período --- */}
            <Grid container spacing={1.5} sx={{ mb: 2 }}>
              <Grid item xs={12} sm={3}>
                <StatTile etiqueta="Sesiones del período" valor={resumen.total_sesiones} nota="Todas las cargadas" />
              </Grid>
              <Grid item xs={12} sm={3}>
                <StatTile etiqueta="Completas" valor={resumen.por_estado?.completa ?? 0} nota="Recuento, no tasa" />
              </Grid>
              <Grid item xs={12} sm={3}>
                <StatTile etiqueta="Incompletas" valor={resumen.por_estado?.incompleta ?? 0} nota="Recuento, no tasa" />
              </Grid>
              <Grid item xs={12} sm={3}>
                <StatTile etiqueta="Ausencias" valor={resumen.por_estado?.ausencia ?? 0} nota="Desglose abajo" />
              </Grid>
            </Grid>

            {/* --- LOS TRES BALDES. Separados y etiquetados. --- */}
            <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 0.5 }}>
              Ausencias, por quién faltó
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
              Son tres grupos distintos. Los dos primeros se suman a una persona; el tercero, a nadie.
            </Typography>
            <Grid container spacing={1.5} sx={{ mb: 1.5 }}>
              {ORIGENES_AUSENCIA.map((origen) => (
                <Grid item xs={12} sm={4} key={origen.clave}>
                  <StatTile
                    etiqueta={origen.etiqueta}
                    valor={resumen.ausencias?.[origen.clave] ?? 0}
                    nota={origen.descripcion}
                  />
                </Grid>
              ))}
            </Grid>

            {resumen.periodo_anterior_a_ausencia_declarable && (
              <Aviso severidad="info" titulo="Parte del período es anterior al registro de quién faltó">
                Hasta el {formatearFecha(resumen.ausencia_declarable_desde)} el sistema no
                pedía declarar quién faltaba, así que esas ausencias quedan en
                <strong> sin declarar</strong>. No se reparten entre paciente y terapeuta:
                ese dato no existe y no se puede reponer.
              </Aviso>
            )}

            {/* --- Listado --- */}
            <Typography variant="subtitle1" sx={{ fontWeight: 600, mt: 3, mb: 1.5 }}>
              Sesiones del período
            </Typography>
            {sesiones.length === 0 ? (
              <EstadoVacio
                titulo="No hubo sesiones en este período"
                descripcion="Probá con un rango más amplio o sacá el filtro por terapeuta."
              />
            ) : (
              <>
                <DataTable
                  columnas={columnas}
                  filas={sesiones.slice(0, MAXIMO_FILAS_VISIBLES)}
                  claveFila={(s) => s.id_sesion}
                />
                {sesiones.length > MAXIMO_FILAS_VISIBLES && (
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                    Se muestran las primeras {MAXIMO_FILAS_VISIBLES} de {sesiones.length} sesiones
                    del período. Los recuentos de arriba son sobre las {sesiones.length}, no sobre
                    las que se ven. Acotá el período o filtrá por terapeuta para recorrerlas todas.
                  </Typography>
                )}
              </>
            )}
          </>
        )}
      </Container>
    </Box>
  );
}

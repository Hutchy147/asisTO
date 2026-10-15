// frontend/src/pages/PanelRrhh.jsx
// Panel de RRHH — consulta de asistencias.
//
// Contrato: docs/api-rrhh.md.
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
//   * SE ESCRIBE UNA SOLA COSA, y desde el 2026-09-14: la observacion
//     TECNICA sobre una sesion (ModalObservacionesRrhh). Es el unico camino
//     de escritura del rol en todo el sistema. NO toca la sesion: es una
//     fila aparte en `observaciones_rrhh` que la referencia.
//
//     La columna del listado se llama `obs_rrhh` y NO `observaciones`, que
//     seria lo natural. El motivo: en este proyecto `observaciones` ya
//     significa `evoluciones.observaciones`, que es CLINICO, y un test de
//     auditoria bloquea ese nombre en el reporte de RRHH. El test tenia
//     razon — el nombre era ambiguo — asi que se renombro la columna, no se
//     tocó el test.

import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
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
import ModalObservacionesRrhh from '../components/rrhh/ModalObservacionesRrhh.jsx';
import { hayCapacidad } from '../config/entregas.js';
import { useAuth } from '../context/AuthContext.jsx';
import { usePeticion } from '../hooks/usePeticion.js';
import { ESTADO_AUSENCIA } from '../services/sesionesService.js';
import {
  ORIGENES_AUSENCIA, obtenerReporteSesiones, terapeutasDelReporte,
} from '../services/rrhhService.js';
import { armarCsv, descargarCsv } from '../utils/csv.js';
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
  const navigate = useNavigate();
  const inicial = useMemo(ventanaInicial, []);

  // El filtro que se EDITA y el que se APLICO son dos cosas distintas: sin
  // separarlos, cada tecla en el campo de fecha dispara una peticion y a
  // mitad de escribir "2026-07-01" se piden rangos absurdos.
  const [borrador, setBorrador] = useState({ ...inicial, idTerapeuta: '' });
  const [aplicado, setAplicado] = useState({ ...inicial, idTerapeuta: '' });

  // La sesión cuyas observaciones se están mirando. null = modal cerrado.
  const [sesionObservada, setSesionObservada] = useState(null);

  // Conteo de observaciones corregido a mano, por sesión, después de guardar.
  //
  // POR QUÉ NO SE VUELVE A PEDIR EL REPORTE. La primera versión hacía
  // `reporte.recargar()` al guardar, y **dejaba la pantalla en blanco**: con
  // 630 sesiones, refetchear y volver a dibujar la grilla entera con el modal
  // abierto deja al navegador sin responder. Se vio en Chrome real, no se
  // dedujo. El dato que cambió es UNO —cuántas observaciones tiene ESA
  // sesión— y pedir de nuevo 630 filas para enterarse es lo que lo rompía.
  const [conteoObservaciones, setConteoObservaciones] = useState({});

  const reporte = usePeticion(
    () => obtenerReporteSesiones(aplicado),
    [aplicado.desde, aplicado.hasta, aplicado.idTerapeuta]
  );

  // El conteo corregido pisa al que vino del servidor, cuando hay uno.
  const sesiones = (reporte.datos?.sesiones ?? []).map((s) => (
    conteoObservaciones[s.id_sesion] === undefined
      ? s
      : { ...s, obs_rrhh: conteoObservaciones[s.id_sesion] }
  ));
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

  // LAS COLUMNAS DEL CSV. Lista cerrada, igual que la de la pantalla.
  //
  // Van SEPARADAS de `columnas` a proposito, aunque digan casi lo mismo: las
  // de la pantalla devuelven JSX (chips, PersonCell) y un archivo necesita
  // texto. Derivar una de la otra obligaria a que cada `render` supiera
  // ademas dibujarse en plano, que es peor que escribir las dos listas.
  //
  // NO SALE NADA CLINICO, y aca es donde hay que sostenerlo: el endpoint ya
  // no devuelve notas ni evoluciones ni diagnostico, asi que no hay de donde
  // sacarlo — pero si manana alguien agrega una columna al endpoint, esta
  // lista la sigue dejando afuera hasta que alguien la escriba. El limite no
  // se relaja por ser un archivo en vez de una pantalla.
  //
  // El id del terapeuta va en COLUMNA PROPIA y no pegado al nombre: en la
  // pantalla es un meta chico debajo, pero en una planilla se filtra y se
  // ordena por columna, y "Fernandez, Laura (id 1)" no se puede ordenar por
  // id. Mismo criterio con nro_historia.
  const columnasCsv = [
    { clave: 'fecha', etiqueta: 'Fecha' },
    { clave: 'hora_inicio', etiqueta: 'Hora inicio' },
    { clave: 'hora_fin', etiqueta: 'Hora fin' },
    { clave: 'id_terapeuta', etiqueta: 'Id terapeuta' },
    { clave: 'terapeuta', etiqueta: 'Terapeuta' },
    { clave: 'nro_historia', etiqueta: 'N de historia' },
    { clave: 'paciente', etiqueta: 'Paciente' },
    { clave: 'estado', etiqueta: 'Estado' },
    {
      clave: 'ausencia_de',
      etiqueta: 'Quien falto',
      // Mismo texto que la pantalla, y el mismo balde de tres: una ausencia
      // sin declarar dice "Sin declarar", NO queda vacia. Una celda vacia en
      // una planilla se lee como "no hubo ausencia", que es justo lo que no
      // es.
      valor: (s) => {
        if (s.estado !== ESTADO_AUSENCIA) return '';
        const origen = ORIGENES_AUSENCIA.find((o) => o.clave === (s.ausencia_de ?? 'sin_declarar'));
        return origen?.etiqueta ?? s.ausencia_de ?? '';
      },
    },
    { clave: 'superposiciones', etiqueta: 'Superpuestas' },
    // El CONTEO, no el texto. Que el archivo diga cuáles tienen observación
    // sirve para revisarlas; volcar el texto de todas convertiría el CSV en
    // un export de comentarios, que no es lo que es.
    { clave: 'obs_rrhh', etiqueta: 'Observaciones RRHH' },
  ];

  const exportar = () => {
    // Sale `sesiones` ENTERO, no `sesiones.slice(...)`: el tope de 100 es
    // para que el navegador no se pegue dibujando, y un archivo no dibuja
    // nada. Exportar lo que se ve seria exportar un recorte de pantalla.
    const contenido = armarCsv(sesiones, columnasCsv);
    descargarCsv(`asistencias_${aplicado.desde}_${aplicado.hasta}.csv`, contenido);
  };

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
    {
      clave: 'obs_rrhh',
      etiqueta: 'Observ.',
      ancho: 96,
      alinear: 'right',
      // Lo que distingue a una sesión con observación de una sin ella. Se
      // dibuja como texto y no sólo como número: "2 obs." se entiende sin
      // leer el encabezado, y un "0" gris no compite visualmente con el
      // resto de la fila.
      render: (s) => (
        s.obs_rrhh > 0
          ? (
            <Box component="span" sx={{ fontWeight: 600, color: 'primary.main' }}>
              {s.obs_rrhh} obs.
            </Box>
          )
          : <Box component="span" sx={{ color: 'text.disabled' }}>—</Box>
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
            {hayCapacidad('auditoria.accesos') && (
              <Button color="inherit" variant="outlined" onClick={() => navigate('/rrhh/auditoria')}>
                Auditoría de accesos
              </Button>
            )}
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

          {/* El boton DICE CUANTAS va a exportar, y son todas las del
              periodo, no las 100 que dibuja la tabla. Sin el numero, quien
              lo aprieta despues de ver "se muestran las primeras 100"
              razonablemente espera un archivo de 100 filas.

              Deshabilitado mientras carga y cuando no hay nada: un boton que
              descarga un archivo con solo el encabezado es peor que uno
              apagado, porque hay que abrirlo para darse cuenta. */}
          <Button
            type="button"
            variant="outlined"
            onClick={exportar}
            disabled={reporte.cargando || sesiones.length === 0}
          >
            {sesiones.length > 0
              ? `Exportar ${sesiones.length} ${sesiones.length === 1 ? 'sesión' : 'sesiones'}`
              : 'Exportar'}
          </Button>
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
                  onAbrirFila={(s) => setSesionObservada(s)}
                  etiquetaFila={(s) => `Observaciones de la sesión de ${s.paciente} del ${s.fecha}`}
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

        <ModalObservacionesRrhh
          abierto={Boolean(sesionObservada)}
          sesion={sesionObservada}
          onCerrar={() => setSesionObservada(null)}
          // El modal ya sabe cuántas quedaron —acaba de releer su lista—, así
          // que pasa el total y acá se corrige esa fila y nada más. Sin esto
          // la sesión seguiría diciendo "—" y parecería que no se guardó.
          onGuardado={(total) => setConteoObservaciones((previo) => ({
            ...previo,
            [sesionObservada.id_sesion]: total,
          }))}
        />
      </Container>
    </Box>
  );
}

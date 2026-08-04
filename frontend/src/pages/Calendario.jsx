// frontend/src/pages/Calendario.jsx
// Semana de trabajo del terapeuta: lunes a viernes, de 8 a 19.

import { useMemo, useState } from 'react';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Snackbar from '@mui/material/Snackbar';
import Alert from '@mui/material/Alert';
import Typography from '@mui/material/Typography';

import ModalCargarEvolucion from '../components/evoluciones/ModalCargarEvolucion.jsx';
import AppLayout from '../components/layout/AppLayout.jsx';
import ModalRegistrarSesion from '../components/sesiones/ModalRegistrarSesion.jsx';
import { Cargando, EstadoError } from '../components/estado/index.js';
import { usePeticion } from '../hooks/usePeticion.js';
import { listarPacientes } from '../services/pacientesService.js';
import { ETIQUETA_ESTADO, faltaEvolucion, listarSesiones } from '../services/sesionesService.js';
import { formatearFecha } from '../utils/fechas.js';

const DIAS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes'];
const HORA_INICIO = 8;
const HORA_FIN = 19;
const ALTO_HORA = 56;
const ANCHO_GUTTER = 62;
const HORAS = Array.from({ length: HORA_FIN - HORA_INICIO }, (_, i) => HORA_INICIO + i);

/** Lunes de la semana de `fecha`. */
function inicioDeSemana(fecha) {
  const dia = new Date(fecha);
  dia.setDate(dia.getDate() - ((dia.getDay() + 6) % 7)); // domingo = 0 -> 6
  dia.setHours(0, 0, 0, 0);
  return dia;
}

/** Local, no UTC: toISOString() puede correr un día según la zona. */
function aIso(fecha) {
  const mes = String(fecha.getMonth() + 1).padStart(2, '0');
  const dia = String(fecha.getDate()).padStart(2, '0');
  return `${fecha.getFullYear()}-${mes}-${dia}`;
}

/** "09:30:00" -> 9.5 */
function aDecimal(hora) {
  if (!hora) return null;
  const [h, m] = hora.split(':').map(Number);
  return h + m / 60;
}

function BloqueSesion({ sesion, onAbrir }) {
  const inicio = aDecimal(sesion.hora_inicio) ?? HORA_INICIO;
  const fin = aDecimal(sesion.hora_fin) ?? inicio + 1;
  const duracion = Math.max(0.5, fin - inicio);
  // La definición vive en sesionesService para que el panel y el
  // calendario no la calculen cada uno por su lado.
  const falta = faltaEvolucion(sesion);

  return (
    <Box
      component="button"
      type="button"
      onClick={() => onAbrir(sesion)}
      title={`${sesion.paciente.nombre_completo} · ${sesion.estado}${falta ? ' · falta cargar la evolución' : ''}`}
      sx={(t) => {
        const colores = t.palette.sesionEstado[sesion.estado];
        return {
          position: 'absolute',
          left: 5,
          right: 5,
          top: (inicio - HORA_INICIO) * ALTO_HORA + 3,
          height: duracion * ALTO_HORA - 6,
          backgroundColor: colores.bg,
          border: '1px solid transparent',
          borderLeft: `3px solid ${colores.fg}`,
          borderRadius: '6px',
          padding: '5px 8px',
          textAlign: 'left',
          cursor: 'pointer',
          font: 'inherit',
          color: t.palette.text.primary,
          display: 'flex',
          flexDirection: 'column',
          gap: '1px',
          overflow: 'hidden',
          // Marca del pendiente: contorno punteado. No es un estado más de
          // la sesión, es una señal de trabajo por hacer.
          outline: falta ? `1.5px dashed ${t.palette.text.primary}80` : 'none',
          outlineOffset: -2,
          '&:focus-visible': { outline: 'none', boxShadow: t.foco.anillo },
        };
      }}
    >
      <Box
        component="span"
        sx={{ display: 'flex', alignItems: 'center', gap: 0.75, fontSize: 12.5, fontWeight: 600, lineHeight: 1.2, minWidth: 0 }}
      >
        <Box component="span" className="tabular" sx={{ flex: 'none' }}>
          {sesion.hora_inicio?.slice(0, 5)}
        </Box>
        <Box component="span" sx={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {sesion.paciente.nombre_completo}
        </Box>
      </Box>
      <Box
        component="span"
        sx={(t) => ({
          fontSize: 11,
          fontWeight: falta ? 500 : 400,
          color: falta ? t.palette.text.primary : t.palette.sesionEstado[sesion.estado].fg,
        })}
      >
        {/* El color y la regla izquierda ya dicen el estado; el texto se
            usa para lo accionable cuando hay algo que hacer. */}
        {falta ? 'Falta la evolución' : ETIQUETA_ESTADO[sesion.estado]}
      </Box>
    </Box>
  );
}

function Leyenda() {
  const items = [
    { clave: 'completa', etiqueta: 'Completa' },
    { clave: 'incompleta', etiqueta: 'Incompleta' },
    { clave: 'ausencia', etiqueta: 'Ausencia' },
  ];
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
      {items.map(({ clave, etiqueta }) => (
        <Box key={clave} sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.9, fontSize: 12, color: 'text.secondary' }}>
          <Box
            component="i"
            sx={(t) => ({
              width: 11,
              height: 11,
              borderRadius: '2px',
              backgroundColor: t.palette.sesionEstado[clave].bg,
              boxShadow: `inset 3px 0 0 ${t.palette.sesionEstado[clave].fg}`,
            })}
          />
          {etiqueta}
        </Box>
      ))}
      <Box sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.9, fontSize: 12, fontWeight: 500, color: 'text.primary' }}>
        <Box
          component="i"
          sx={(t) => ({
            width: 11,
            height: 11,
            borderRadius: '2px',
            outline: `1.5px dashed ${t.palette.text.primary}80`,
            outlineOffset: '-1.5px',
          })}
        />
        Falta la evolución
      </Box>
    </Box>
  );
}

export default function Calendario() {
  const [lunes, setLunes] = useState(() => inicioDeSemana(new Date()));
  const [modalSesion, setModalSesion] = useState(null); // null | {fecha, hora}
  const [idEvolucion, setIdEvolucion] = useState(null);
  const [aviso, setAviso] = useState('');

  const { desde, hasta, dias } = useMemo(() => {
    const lista = Array.from({ length: 5 }, (_, i) => {
      const dia = new Date(lunes);
      dia.setDate(lunes.getDate() + i);
      return dia;
    });
    return { desde: aIso(lista[0]), hasta: aIso(lista[4]), dias: lista };
  }, [lunes]);

  const sesiones = usePeticion(() => listarSesiones({ desde, hasta }), [desde, hasta]);
  const pacientes = usePeticion(listarPacientes, []);

  const porFecha = useMemo(() => {
    const mapa = {};
    (sesiones.datos?.sesiones ?? []).forEach((s) => {
      (mapa[s.fecha] ??= []).push(s);
    });
    return mapa;
  }, [sesiones.datos]);

  const pendientes = useMemo(
    () => (sesiones.datos?.sesiones ?? []).filter(faltaEvolucion),
    [sesiones.datos]
  );

  const hoyIso = aIso(new Date());
  const enSemanaActual = dias.some((d) => aIso(d) === hoyIso);
  const ahora = new Date();
  const ahoraDecimal = ahora.getHours() + ahora.getMinutes() / 60;
  const mostrarLineaAhora =
    enSemanaActual && ahoraDecimal >= HORA_INICIO && ahoraDecimal <= HORA_FIN;

  const mover = (semanas) => {
    const nuevo = new Date(lunes);
    nuevo.setDate(lunes.getDate() + semanas * 7);
    setLunes(nuevo);
  };

  const abrirAlta = (fecha, hora) =>
    setModalSesion({ fecha: fecha ?? '', hora: hora ?? '' });

  const recargar = () => {
    sesiones.recargar();
  };

  return (
    <AppLayout
      titulo="Calendario"
      subtitulo={`${formatearFecha(desde)} al ${formatearFecha(hasta)}${sesiones.datos ? ` · ${sesiones.datos.total} sesiones` : ''}`}
      acciones={
        <Button variant="contained" onClick={() => abrirAlta()}>
          Registrar sesión
        </Button>
      }
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2, flexWrap: 'wrap' }}>
        <Button size="small" variant="outlined" onClick={() => mover(-1)}>
          Semana anterior
        </Button>
        <Button size="small" variant="outlined" onClick={() => setLunes(inicioDeSemana(new Date()))}>
          Esta semana
        </Button>
        <Button size="small" variant="outlined" onClick={() => mover(1)}>
          Semana siguiente
        </Button>
        <Box sx={{ flex: 1 }} />
        <Leyenda />
      </Box>

      {/* Barra de trabajo pendiente: lo que hay que resolver antes de
          cerrar el día, visible de un vistazo y sin abrir nada. */}
      {pendientes.length > 0 && (
        <Box
          sx={(t) => ({
            display: 'flex',
            alignItems: 'center',
            gap: 1.5,
            px: 2,
            py: 1.25,
            mb: 2,
            borderRadius: `${t.formas.sm}px`,
            backgroundColor: t.palette.feedback.info.bg,
            border: `1px solid ${t.palette.superficie.borde}`,
            fontSize: 13,
          })}
        >
          <Box component="span" sx={{ flex: 1 }}>
            {pendientes.length === 1
              ? 'Una sesión de esta semana quedó sin evolución cargada.'
              : `${pendientes.length} sesiones de esta semana quedaron sin evolución cargada.`}
          </Box>
          <Button size="small" onClick={() => setIdEvolucion(pendientes[0].id)}>
            Cargar la primera
          </Button>
        </Box>
      )}

      {sesiones.cargando && <Cargando texto="Cargando la semana..." />}
      {sesiones.error && <EstadoError error={sesiones.error} onReintentar={sesiones.recargar} />}

      {sesiones.datos && !sesiones.cargando && !sesiones.error && (
        <>
          {sesiones.datos.total === 0 && (
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              No hay sesiones registradas en esta semana. Podés registrar una o
              mirar otra semana con los botones de arriba.
            </Typography>
          )}

          {/* La grilla se dibuja SIEMPRE, aunque la semana esté vacía: es
              la estructura de la pantalla, no su contenido. Sin ella el
              terapeuta pierde la referencia de los días y el lugar donde
              hacer clic para registrar. */}
          <Box
            sx={(t) => ({
              position: 'relative',
              backgroundColor: t.palette.superficie.tarjeta,
              border: `1px solid ${t.palette.superficie.borde}`,
              borderRadius: `${t.formas.md}px`,
              overflow: 'hidden',
              minWidth: 820,
            })}
          >
            {/* Encabezado de días */}
            <Box
              sx={(t) => ({
                display: 'grid',
                gridTemplateColumns: `${ANCHO_GUTTER}px repeat(5, 1fr)`,
                borderBottom: `1px solid ${t.palette.superficie.borde}`,
                backgroundColor: '#FAF9F6',
              })}
            >
              <Box />
              {dias.map((dia, indice) => {
                const iso = aIso(dia);
                const esHoy = iso === hoyIso;
                return (
                  <Box
                    key={iso}
                    sx={(t) => ({
                      px: 1.25,
                      py: 1.1,
                      borderLeft: `1px solid ${t.palette.superficie.hundida}`,
                      display: 'flex',
                      alignItems: 'baseline',
                      gap: 0.75,
                    })}
                  >
                    <Typography variant="subtitle2" component="span">
                      {DIAS[indice]}
                    </Typography>
                    <Box component="span" className="tabular" sx={{ fontSize: 12, color: 'text.secondary' }}>
                      {iso.slice(8)}/{iso.slice(5, 7)}
                    </Box>
                    {esHoy && (
                      <Box
                        component="span"
                        sx={(t) => ({
                          fontSize: 10,
                          fontWeight: 600,
                          letterSpacing: '.06em',
                          textTransform: 'uppercase',
                          color: '#FFFFFF',
                          backgroundColor: t.palette.primary.main,
                          borderRadius: '999px',
                          px: 0.9,
                          py: '1px',
                        })}
                      >
                        hoy
                      </Box>
                    )}
                  </Box>
                );
              })}
            </Box>

            {/* Grilla */}
            <Box
              sx={{ display: 'grid', gridTemplateColumns: `${ANCHO_GUTTER}px repeat(5, 1fr)`, position: 'relative' }}
            >
              <Box>
                {HORAS.map((hora) => (
                  <Box
                    key={hora}
                    className="tabular"
                    sx={(t) => ({
                      height: ALTO_HORA,
                      borderBottom: `1px solid ${t.palette.superficie.hundida}`,
                      px: 1.1,
                      pt: '3px',
                      textAlign: 'right',
                      fontSize: 11,
                      color: t.palette.text.disabled,
                    })}
                  >
                    {String(hora).padStart(2, '0')}:00
                  </Box>
                ))}
              </Box>

              {dias.map((dia) => {
                const iso = aIso(dia);
                return (
                  <Box
                    key={iso}
                    sx={(t) => ({ position: 'relative', borderLeft: `1px solid ${t.palette.superficie.hundida}` })}
                  >
                    {HORAS.map((hora) => (
                      <Box
                        key={hora}
                        component="button"
                        type="button"
                        aria-label={`Registrar sesión el ${formatearFecha(iso)} a las ${String(hora).padStart(2, '0')}:00`}
                        onClick={() => abrirAlta(iso, `${String(hora).padStart(2, '0')}:00`)}
                        sx={(t) => ({
                          display: 'block',
                          width: '100%',
                          height: ALTO_HORA,
                          border: 0,
                          borderBottom: `1px solid ${t.palette.superficie.hundida}`,
                          background: 'transparent',
                          padding: 0,
                          cursor: 'pointer',
                          '&:hover': { backgroundColor: t.palette.superficie.acentoSuave },
                          '&:focus-visible': { outline: 'none', boxShadow: `inset ${t.foco.anillo}` },
                        })}
                      />
                    ))}
                    {(porFecha[iso] ?? []).map((sesion) => (
                      <BloqueSesion key={sesion.id} sesion={sesion} onAbrir={(s) => setIdEvolucion(s.id)} />
                    ))}
                  </Box>
                );
              })}

              {mostrarLineaAhora && (
                <Box
                  aria-hidden="true"
                  sx={(t) => ({
                    position: 'absolute',
                    left: ANCHO_GUTTER,
                    right: 0,
                    top: (ahoraDecimal - HORA_INICIO) * ALTO_HORA,
                    height: 0,
                    borderTop: `1.5px solid ${t.palette.primary.main}`,
                    pointerEvents: 'none',
                    zIndex: 3,
                  })}
                >
                  <Box
                    component="span"
                    sx={(t) => ({
                      position: 'absolute',
                      left: -4,
                      top: -4,
                      width: 8,
                      height: 8,
                      borderRadius: '999px',
                      backgroundColor: t.palette.primary.main,
                    })}
                  />
                </Box>
              )}
            </Box>
          </Box>
        </>
      )}

      <ModalRegistrarSesion
        key={`${modalSesion?.fecha ?? ''}-${modalSesion?.hora ?? ''}`}
        abierto={Boolean(modalSesion)}
        pacientes={pacientes.datos?.pacientes ?? []}
        fechaInicial={modalSesion?.fecha ?? ''}
        horaInicial={modalSesion?.hora ?? ''}
        onCerrar={() => setModalSesion(null)}
        onRegistrada={(respuesta) => {
          recargar();
          setAviso(respuesta?.mensaje ?? 'Sesión registrada correctamente');
        }}
      />

      <ModalCargarEvolucion
        key={idEvolucion ?? 'sin-sesion'}
        abierto={Boolean(idEvolucion)}
        idSesion={idEvolucion}
        onCerrar={() => setIdEvolucion(null)}
        onCargada={(respuesta) => {
          recargar();
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

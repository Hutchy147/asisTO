// frontend/src/pages/Calendario.jsx
// Semana de trabajo del terapeuta: lunes a viernes, de 8 a 19.
//
// ENTREGA 3 (capacidad `calendario.agenda`): el calendario es para AGENDAR y
// planificar. Agendar abre un modal corto (sin estado ni "quién faltó"), una
// sesión del calendario se abre en lectura y se puede reprogramar, y cargar
// la evolución se hace desde el Panel o la ficha del paciente, no acá. Antes
// de la entrega 3 se conserva el comportamiento anterior.

import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Snackbar from '@mui/material/Snackbar';
import Alert from '@mui/material/Alert';
import Typography from '@mui/material/Typography';

import ModalCargarEvolucion from '../components/evoluciones/ModalCargarEvolucion.jsx';
import AppLayout from '../components/layout/AppLayout.jsx';
import ModalAgendarSesion from '../components/sesiones/ModalAgendarSesion.jsx';
import ModalAgendaSemanal from '../components/sesiones/ModalAgendaSemanal.jsx';
import ModalDetalleSesion from '../components/sesiones/ModalDetalleSesion.jsx';
import ModalEditarSesion from '../components/sesiones/ModalEditarSesion.jsx';
import ModalRegistrarSesion from '../components/sesiones/ModalRegistrarSesion.jsx';
import { Cargando, EstadoError } from '../components/estado/index.js';
import CalendarioSemanal from './CalendarioSemanal.jsx';
import { usePeticion } from '../hooks/usePeticion.js';
import { hayCapacidad } from '../config/entregas.js';
import { listarPacientes } from '../services/pacientesService.js';
import { ETIQUETA_ESTADO, faltaEvolucion, listarSesiones } from '../services/sesionesService.js';
import { formatearFecha, formatearFechaCorta } from '../utils/fechas.js';

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

function CalendarioPorDia() {
  const [lunes, setLunes] = useState(() => inicioDeSemana(new Date()));
  const [modalSesion, setModalSesion] = useState(null); // null | {fecha, hora}
  const [agendaSemanal, setAgendaSemanal] = useState(false);
  const [idEvolucion, setIdEvolucion] = useState(null);
  const [idDetalle, setIdDetalle] = useState(null);
  const [sesionAEditar, setSesionAEditar] = useState(null);
  const [aviso, setAviso] = useState('');
  const navigate = useNavigate();
  const soloAgenda = hayCapacidad('calendario.agenda');
  // Un clic en una sesión: en agenda se LEE (y se reprograma); antes de la
  // entrega 3 se abría directo la carga de evolución.
  const abrirSesion = (s) => (soloAgenda ? setIdDetalle(s.id) : setIdEvolucion(s.id));
  const pacientesAsignados = (pacientes_) => (pacientes_ ?? []).filter(
    (p) => !hayCapacidad('asignaciones.gestionar') || p.asignado_a_mi,
  );

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

  // Una sesion agendada para despues todavia no "quedo sin evolucion": en
  // modo agenda el aviso cuenta solo las que ya pasaron o son de hoy.
  const pendientes = useMemo(
    () => (sesiones.datos?.sesiones ?? []).filter(
      (s) => faltaEvolucion(s) && (!soloAgenda || s.fecha <= aIso(new Date())),
    ),
    [sesiones.datos, soloAgenda]
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
        <>
          {hayCapacidad('agenda.recurrente') && (
            <Button variant="outlined" onClick={() => setAgendaSemanal(true)} sx={{ mr: 1 }}>
              Agenda semanal
            </Button>
          )}
          <Button variant="contained" onClick={() => abrirAlta()}>
            {soloAgenda ? 'Agendar sesión' : 'Registrar sesión'}
          </Button>
        </>
      }
    >
      {/* --- Navegación entre semanas ---
          Rehecha el 2026-08-20 por observación directa: una terapeuta
          ocupacional NO ENCONTRÓ estos controles, y sin poder moverse entre
          semanas no llegó a probar ni la planificación ni la consulta de
          días anteriores. Lo que estaba mal, medido en el navegador:

            texto  13 px, #3E8E7E sobre #F6F4F0  -> contraste 3.56:1 (AA pide 4.5)
            borde  el mismo color al 50 % de alfa -> 1.79:1, casi invisible
            alto   30 px contra los 37 del boton de accion de la pantalla

          Y sobre todo: los tres tenían EXACTAMENTE el mismo peso visual que
          la leyenda de colores de al lado, que no es interactiva. Tres
          controles y una leyenda se veían igual.

          Van sobre una barra de superficie propia para separarse del fondo,
          con texto navy —el mismo `text.primary` de la pantalla— y el rango
          de fechas EN EL MEDIO de los dos botones: saber en qué semana estás
          parado es la mitad del problema, y esa información vivía sola en el
          subtítulo del encabezado, lejos y en gris. */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 2, flexWrap: 'wrap' }}>
        <Box
          sx={(t) => ({
            display: 'flex',
            alignItems: 'stretch',
            backgroundColor: t.palette.superficie.tarjeta,
            border: `1px solid ${t.palette.superficie.borde}`,
            borderRadius: `${t.formas.sm}px`,
            overflow: 'hidden',
          })}
        >
          <Button
            onClick={() => mover(-1)}
            sx={{ px: 2, borderRadius: 0, color: 'text.primary', fontWeight: 600, whiteSpace: 'nowrap' }}
          >
            ‹ Semana anterior
          </Button>

          <Box
            sx={(t) => ({
              display: 'flex',
              alignItems: 'center',
              gap: 1,
              px: 2,
              borderLeft: `1px solid ${t.palette.superficie.borde}`,
              borderRight: `1px solid ${t.palette.superficie.borde}`,
              backgroundColor: t.palette.superficie.hundida,
            })}
          >
            {/* Sin año: lo dice el subtítulo del encabezado dos líneas más
                arriba, y con el año la barra pedía 844 px de ancho cuando el
                área de contenido da 820 en el mínimo declarado del
                calendario. Medido, no estimado.

                nowrap: un rango partido en dos renglones deja de leerse como
                un rango, y estiraba la barra entera a 65 px. */}
            <Box
              component="span"
              className="tabular"
              sx={{ fontSize: 13, fontWeight: 600, whiteSpace: 'nowrap' }}
            >
              {formatearFechaCorta(desde)} al {formatearFechaCorta(hasta)}
            </Box>
            {enSemanaActual && (
              <Box
                component="span"
                sx={(t) => ({
                  flex: 'none',
                  fontSize: 11,
                  fontWeight: 700,
                  letterSpacing: 0.4,
                  textTransform: 'uppercase',
                  color: t.palette.primary.contrastText,
                  // primary.dark y no primary.main: a 11 px el blanco sobre
                  // el eucalipto claro da 3.91:1 y AA pide 4.5. Medido en el
                  // navegador, no elegido de memoria.
                  backgroundColor: t.palette.primary.dark,
                  borderRadius: `${t.formas.pill}px`,
                  px: 0.9,
                  py: '1px',
                  whiteSpace: 'nowrap',
                })}
              >
                Esta semana
              </Box>
            )}
          </Box>

          <Button
            onClick={() => mover(1)}
            sx={{ px: 2, borderRadius: 0, color: 'text.primary', fontWeight: 600, whiteSpace: 'nowrap' }}
          >
            Semana siguiente ›
          </Button>
        </Box>

        {/* Aparece SOLO cuando estás fuera de la semana actual. Su ausencia
            es en sí misma la señal de que ya estás parado en ella, y evita
            un botón que no hace nada. */}
        {!enSemanaActual && (
          <Button variant="outlined" onClick={() => setLunes(inicioDeSemana(new Date()))}>
            Volver a esta semana
          </Button>
        )}

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
            {soloAgenda && ' Se cargan desde el Panel.'}
          </Box>
          {soloAgenda ? (
            <Button size="small" onClick={() => navigate('/panel')}>
              Ir al Panel
            </Button>
          ) : (
            <Button size="small" onClick={() => setIdEvolucion(pendientes[0].id)}>
              Cargar la primera
            </Button>
          )}
        </Box>
      )}

      {sesiones.cargando && <Cargando texto="Cargando la semana..." />}
      {sesiones.error && <EstadoError error={sesiones.error} onReintentar={sesiones.recargar} />}

      {sesiones.datos && !sesiones.cargando && !sesiones.error && (
        <>
          {sesiones.datos.total === 0 && (
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              {soloAgenda
                ? 'No hay sesiones agendadas en esta semana. Puede agendar una o consultar otra semana con los botones superiores.'
                : 'No hay sesiones registradas en esta semana. Puede registrar una o consultar otra semana con los botones superiores.'}
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
                        aria-label={`${soloAgenda ? 'Agendar' : 'Registrar'} sesión el ${formatearFecha(iso)} a las ${String(hora).padStart(2, '0')}:00`}
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
                      <BloqueSesion key={sesion.id} sesion={sesion} onAbrir={abrirSesion} />
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

      {soloAgenda ? (
        <ModalAgendarSesion
          key={`agenda-${modalSesion?.fecha ?? ''}-${modalSesion?.hora ?? ''}`}
          abierto={Boolean(modalSesion)}
          // HDU 11: solo se agenda a pacientes asignados al terapeuta; el
          // servidor igual lo valida (regla 8).
          pacientes={pacientesAsignados(pacientes.datos?.pacientes)}
          fechaInicial={modalSesion?.fecha ?? ''}
          horaInicial={modalSesion?.hora ?? ''}
          onCerrar={() => setModalSesion(null)}
          onAgendada={(respuesta) => {
            recargar();
            setAviso(respuesta?.mensaje ?? 'Sesión agendada correctamente');
          }}
        />
      ) : (
        <ModalRegistrarSesion
          key={`${modalSesion?.fecha ?? ''}-${modalSesion?.hora ?? ''}`}
          abierto={Boolean(modalSesion)}
          pacientes={pacientesAsignados(pacientes.datos?.pacientes)}
          fechaInicial={modalSesion?.fecha ?? ''}
          horaInicial={modalSesion?.hora ?? ''}
          onCerrar={() => setModalSesion(null)}
          onRegistrada={(respuesta) => {
            recargar();
            setAviso(respuesta?.mensaje ?? 'Sesión registrada correctamente');
          }}
        />
      )}

      {hayCapacidad('agenda.recurrente') && agendaSemanal && (
        <ModalAgendaSemanal
          abierto
          pacientes={pacientesAsignados(pacientes.datos?.pacientes)}
          onCerrar={() => setAgendaSemanal(false)}
          onGenerada={recargar}
        />
      )}

      {soloAgenda && (
        <>
          <ModalDetalleSesion
            key={`detalle-${idDetalle ?? 'sin-sesion'}`}
            abierto={Boolean(idDetalle)}
            idSesion={idDetalle}
            onCerrar={() => setIdDetalle(null)}
            onEditar={(sesion, paciente) => {
              setIdDetalle(null);
              setSesionAEditar({ sesion, paciente });
            }}
          />
          <ModalEditarSesion
            key={`editar-${sesionAEditar?.sesion?.id ?? 'sin-sesion'}`}
            abierto={Boolean(sesionAEditar)}
            sesion={sesionAEditar?.sesion}
            paciente={sesionAEditar?.paciente}
            onCerrar={() => setSesionAEditar(null)}
            onGuardado={(respuesta) => {
              recargar();
              setAviso(respuesta?.mensaje ?? 'Sesión actualizada.');
            }}
          />
        </>
      )}

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


// Desde la Entrega 3 el calendario es la semana tipo (turnos que se repiten);
// antes de esa entrega se conserva el calendario por día.
export default function Calendario() {
  return hayCapacidad('agenda.recurrente') ? <CalendarioSemanal /> : <CalendarioPorDia />;
}

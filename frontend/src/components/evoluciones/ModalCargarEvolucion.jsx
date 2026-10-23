// frontend/src/components/evoluciones/ModalCargarEvolucion.jsx
//
// El modal más importante del sistema: acá ocurre el seguimiento
// terapéutico. Tiene tres caminos y solo uno muestra el formulario.

import { useMemo } from 'react';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import FormControlLabel from '@mui/material/FormControlLabel';
import Radio from '@mui/material/Radio';
import RadioGroup from '@mui/material/RadioGroup';
import Typography from '@mui/material/Typography';
import { useNavigate } from 'react-router-dom';

import EscalaLogro from './EscalaLogro.jsx';
import AvisoSesionDeOtroTerapeuta from '../avisos/AvisoSesionDeOtroTerapeuta.jsx';
import AvisoSesionSinEvolucion from '../avisos/AvisoSesionSinEvolucion.jsx';
import AvisoSinObjetivosActivos from '../avisos/AvisoSinObjetivosActivos.jsx';
import CampoTexto from '../forms/CampoTexto.jsx';
import ModalFormulario from '../modal/ModalFormulario.jsx';
import Aviso from '../estado/Aviso.jsx';
import { Cargando, EstadoError } from '../estado/index.js';
import { useFormularioModal } from '../../hooks/useFormularioModal.js';
import { usePeticion } from '../../hooks/usePeticion.js';
import { etiquetaDeValor, registrarEvolucion } from '../../services/evolucionesService.js';
import { obtenerSesion } from '../../services/sesionesService.js';
import { formatearFecha } from '../../utils/fechas.js';

/** Última calificación del objetivo, en palabras. */
function textoUltima(seguimiento) {
  const etiqueta = etiquetaDeValor(seguimiento?.ultimo_valor);
  if (!etiqueta) return 'Sin calificaciones todavía';
  const fecha = formatearFecha(seguimiento.fecha_ultima_evolucion);
  return fecha ? `Última: ${etiqueta} · ${fecha}` : `Última: ${etiqueta}`;
}

export default function ModalCargarEvolucion({ abierto, idSesion, onCerrar, onCargada }) {
  const navigate = useNavigate();
  const detalle = usePeticion(() => obtenerSesion(idSesion), [idSesion], {
    inmediata: Boolean(idSesion),
  });

  const datos = detalle.datos;
  const sesion = datos?.sesion;
  const objetivos = datos?.objetivos_activos ?? [];

  // Qué objetivos ya se calificaron EN ESTA SESIÓN. El dato viene embebido
  // en el detalle, no hace falta pedirlo aparte.
  //
  // Sin esto el modal ofrecía elegir un objetivo ya calificado y el
  // servidor lo rechazaba con "Ya existe una evolucion para ese objetivo
  // en esa sesion". Un camino que siempre falla, visible en la interfaz:
  // exactamente lo que este proyecto viene evitando.
  const yaCalificados = useMemo(() => {
    const mapa = new Map();
    (datos?.evoluciones ?? []).forEach((e) => mapa.set(e.id_objetivo, e));
    return mapa;
  }, [datos]);

  const disponibles = objetivos.filter((o) => !yaCalificados.has(o.id));

  const formulario = useFormularioModal({
    inicial: { id_objetivo: '', valor: '', observaciones: '' },
    obligatorios: ['id_objetivo', 'valor'],
    onEnviar: (valores) =>
      registrarEvolucion({
        id_sesion: idSesion,
        id_objetivo: Number(valores.id_objetivo),
        valor: Number(valores.valor),
        observaciones: valores.observaciones.trim() || null,
      }),
    onExito: (respuesta) => {
      onCerrar?.();
      onCargada?.(respuesta);
    },
    onCerrar,
  });

  const { valores, setValor, setCampo, errorDe, guardando, validado } = formulario;

  // --- Qué camino toma el modal ---
  const esDeOtro = sesion?.es_propia === false;
  const noAdmite = sesion && !sesion.admite_evolucion;
  const sinObjetivos = sesion && !esDeOtro && !noAdmite && objetivos.length === 0;
  // Todos los objetivos activos ya tienen su evolución en esta sesión: no
  // queda nada para elegir, y no es un error sino trabajo terminado.
  const todosCalificados =
    sesion && !esDeOtro && !noAdmite && objetivos.length > 0 && disponibles.length === 0;
  // Ninguno de los cuatro se resuelve desde este modal
  const soloCerrar = Boolean(esDeOtro || noAdmite || sinObjetivos || todosCalificados);

  const subtitulo = datos
    ? `${datos.paciente.nombre_completo} · ${formatearFecha(sesion.fecha)} · ${sesion.hora_inicio?.slice(0, 5)}`
    : undefined;

  /**
   * La escala y las observaciones van al panel lateral: son el único campo
   * OBLIGATORIO que no es la lista, y con objetivos en formato real la lista
   * puede medir cualquier cosa. Si comparten el scroll con ella, se van con
   * ella — medido: 807 px de contenido contra 423 visibles en 1366x768, con la
   * escala 16 px abajo del pliegue.
   *
   * En una sola columna ModalFormulario los apila acá abajo, en este mismo
   * orden, que es el que tenía el modal antes de los dos paneles.
   */
  const panelLateral = !soloCerrar && datos ? (
    <>
      <EscalaLogro
        valor={valores.valor}
        onChange={(valor) => setValor('valor', valor)}
        deshabilitado={guardando}
        error={validado && !valores.valor ? 'Elija cómo evolucionó el objetivo.' : undefined}
      />

      <CampoTexto
        id="evolucion-observaciones"
        etiqueta="Observaciones"
        multilinea
        filas={3}
        ayuda="Opcional. Lo que convenga que lea quien retome el tratamiento."
        valor={valores.observaciones}
        onChange={setCampo('observaciones')}
        error={errorDe('observaciones')}
        deshabilitado={guardando}
      />
    </>
  ) : undefined;

  return (
    <ModalFormulario
      abierto={abierto}
      // 640 es el ancho de UNA columna. Con dos paneles ModalFormulario usa
      // ANCHO_DOS_PANELES y este valor no se aplica.
      ancho={640}
      panelLateral={panelLateral}
      titulo="Cargar evolución"
      subtitulo={subtitulo}
      guardando={guardando}
      errorServidor={formulario.errorServidor}
      tituloRechazo="No se pudo guardar la evolución"
      confirmandoDescarte={formulario.confirmandoDescarte}
      onPedirCierre={formulario.pedirCierre}
      onSeguirEditando={formulario.seguirEditando}
      onDescartar={formulario.descartar}
      onEnviar={formulario.enviar}
      etiquetaEnviar="Guardar evolución"
      etiquetaGuardando="Guardando…"
      soloCerrar={soloCerrar}
    >
      {detalle.cargando && <Cargando texto="Abriendo la sesión..." minHeight={140} />}
      {detalle.error && <EstadoError error={detalle.error} onReintentar={detalle.recargar} />}

      {datos && (
        <>
          {/* Los tres caminos sin formulario, cada uno con su motivo escrito */}
          {esDeOtro && (
            <AvisoSesionDeOtroTerapeuta sesion={sesion} terapeuta={datos.terapeuta} />
          )}
          {noAdmite && <AvisoSesionSinEvolucion sesion={sesion} />}
          {sinObjetivos && <AvisoSinObjetivosActivos objetivosActivos={objetivos} />}
          {todosCalificados && (
            <Aviso severidad="success" titulo="Esta sesión ya está completa">
              {objetivos.length === 1
                ? `El único objetivo activo de ${datos.paciente.nombre} ya tiene su evolución cargada en esta sesión.`
                : `Los ${objetivos.length} objetivos activos de ${datos.paciente.nombre} ya tienen su evolución cargada en esta sesión.`}{' '}
              No queda nada por calificar.
            </Aviso>
          )}

          {sinObjetivos && (
            <Box sx={{ display: 'flex', justifyContent: 'center', pb: 1 }}>
              <Button
                variant="contained"
                onClick={() => {
                  onCerrar?.();
                  navigate(`/pacientes/${datos.paciente.id}`);
                }}
              >
                Ir a los objetivos de {datos.paciente.nombre}
              </Button>
            </Box>
          )}

          {!soloCerrar && (
            <>
              {/* data-campo-invalido: igual que EscalaLogro, el grupo dibuja
                  su propio error y MUI no lo marca. Ver ModalFormulario. */}
              <Box {...(validado && !valores.id_objetivo ? { 'data-campo-invalido': '' } : {})}>
                <Typography variant="body2" sx={{ fontWeight: 500, mb: 0.5 }}>
                  Objetivo trabajado <Box component="span" sx={{ color: 'error.main' }}>*</Box>
                </Typography>
                <RadioGroup
                  value={valores.id_objetivo}
                  onChange={(evento) => setValor('id_objetivo', evento.target.value)}
                >
                  {objetivos.map((objetivo) => {
                    const yaCargada = yaCalificados.get(objetivo.id);
                    const esElegido = valores.id_objetivo === String(objetivo.id);
                    return (
                      <FormControlLabel
                        key={objetivo.id}
                        value={String(objetivo.id)}
                        // Un objetivo ya calificado en esta sesión no se
                        // puede volver a calificar: la UNIQUE lo rechaza.
                        // Se deja visible, para que se vea qué se trabajó.
                        disabled={guardando || Boolean(yaCargada)}
                        control={<Radio size="small" />}
                        sx={{ alignItems: 'flex-start', mb: 0.5 }}
                        label={
                          <Box sx={{ py: 0.25, minWidth: 0 }}>
                            <Box
                              component="span"
                              className="texto-libre"
                              sx={{
                                display: 'block',
                                fontSize: 14,
                                lineHeight: 1.4,
                                // El objetivo ELEGIDO se muestra completo; los
                                // demás en dos líneas.
                                //
                                // No es por espacio: es que las dos tareas
                                // necesitan cantidades distintas de texto.
                                // Para ELEGIR alcanzan dos líneas —los cuatro
                                // objetivos comparten solo 16 caracteres de
                                // arranque, así que se distinguen enseguida—.
                                // Para CALIFICAR hace falta el criterio de
                                // medición, que en formato real arranca en la
                                // línea 3 y es la rúbrica de la calificación.
                                // Colapsar el elegido escondería justo eso.
                                ...(esElegido
                                  ? {}
                                  : {
                                      display: '-webkit-box',
                                      WebkitLineClamp: 2,
                                      WebkitBoxOrient: 'vertical',
                                      overflow: 'hidden',
                                    }),
                              }}
                            >
                              {objetivo.descripcion}
                            </Box>
                            <Typography variant="caption" sx={{ display: 'block' }}>
                              {yaCargada
                                ? `Ya calificado en esta sesión: ${etiquetaDeValor(yaCargada.valor)}`
                                : textoUltima(objetivo.seguimiento)}
                            </Typography>
                          </Box>
                        }
                      />
                    );
                  })}
                </RadioGroup>
                {validado && !valores.id_objetivo && (
                  <Typography variant="caption" color="error">
                    Elija el objetivo que se trabajó en esta sesión.
                  </Typography>
                )}
              </Box>
            </>
          )}
        </>
      )}
    </ModalFormulario>
  );
}

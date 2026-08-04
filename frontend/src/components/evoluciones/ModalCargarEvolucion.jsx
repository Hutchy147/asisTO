// frontend/src/components/evoluciones/ModalCargarEvolucion.jsx
//
// El modal más importante del sistema: acá ocurre el seguimiento
// terapéutico. Tiene tres caminos y solo uno muestra el formulario.

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
  // Ninguno de los tres se resuelve desde este modal
  const soloCerrar = Boolean(esDeOtro || noAdmite || sinObjetivos);

  const subtitulo = datos
    ? `${datos.paciente.nombre_completo} · ${formatearFecha(sesion.fecha)} · ${sesion.hora_inicio?.slice(0, 5)}`
    : undefined;

  return (
    <ModalFormulario
      abierto={abierto}
      ancho={640}
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
              <Box>
                <Typography variant="body2" sx={{ fontWeight: 500, mb: 0.5 }}>
                  Objetivo trabajado <Box component="span" sx={{ color: 'error.main' }}>*</Box>
                </Typography>
                <RadioGroup
                  value={valores.id_objetivo}
                  onChange={(evento) => setValor('id_objetivo', evento.target.value)}
                >
                  {objetivos.map((objetivo) => (
                    <FormControlLabel
                      key={objetivo.id}
                      value={String(objetivo.id)}
                      disabled={guardando}
                      control={<Radio size="small" />}
                      sx={{ alignItems: 'flex-start', mb: 0.5 }}
                      label={
                        <Box sx={{ py: 0.25 }}>
                          <Box component="span" sx={{ fontSize: 14, lineHeight: 1.4 }}>
                            {objetivo.descripcion}
                          </Box>
                          <Typography variant="caption" sx={{ display: 'block' }}>
                            {textoUltima(objetivo.seguimiento)}
                          </Typography>
                        </Box>
                      }
                    />
                  ))}
                </RadioGroup>
                {validado && !valores.id_objetivo && (
                  <Typography variant="caption" color="error">
                    Elegí el objetivo que se trabajó en esta sesión.
                  </Typography>
                )}
              </Box>

              <EscalaLogro
                valor={valores.valor}
                onChange={(valor) => setValor('valor', valor)}
                deshabilitado={guardando}
                error={
                  validado && !valores.valor ? 'Elegí cómo evolucionó el objetivo.' : undefined
                }
              />

              <CampoTexto
                id="evolucion-observaciones"
                etiqueta="Observaciones"
                multilinea
                filas={3}
                ayuda="Opcional. Lo que quieras que lea quien retome el tratamiento."
                valor={valores.observaciones}
                onChange={setCampo('observaciones')}
                error={errorDe('observaciones')}
                deshabilitado={guardando}
              />
            </>
          )}
        </>
      )}
    </ModalFormulario>
  );
}

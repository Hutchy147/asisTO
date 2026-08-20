// frontend/src/components/sesiones/ModalDetalleSesion.jsx
//
// LEER lo que se registró en una sesión. Es la contraparte de
// ModalCargarEvolucion, que solo escribe.
//
// POR QUÉ EXISTE. Hasta el 2026-08-20 `sesiones.notas` y
// `evoluciones.observaciones` se guardaban desde la Entrega 1 y NO SE
// MOSTRABAN EN NINGUNA PANTALLA. El dato viajaba al navegador —el detalle
// de la sesión ya traía las evoluciones embebidas— y se descartaba: lo
// único que se pintaba de una evolución cargada era su valor, y solo
// dentro del formulario de carga. Una terapeuta ocupacional cargó un
// evolutivo completo y después no encontró dónde leerlo. Traer el dato y
// mostrarlo son dos cosas distintas.
//
// El caso peor era el suyo: con TODOS los objetivos activos calificados,
// ModalCargarEvolucion toma el camino `todosCalificados` y solo dice "Esta
// sesión ya está completa". Ni una calificación, ni una observación.
//
// ES SOLO LECTURA, Y ESO ES UNA DECISIÓN. Leer la sesión de otro terapeuta
// está permitido; cargarle evolución no. El pie se reduce a "Cerrar" y la
// acción de cargar aparece únicamente cuando el servidor la va a aceptar:
// sesión propia, que admita evolución, y con algún objetivo sin calificar.
// Ofrecer un botón que termina en 403 es peor que no ofrecerlo.
//
// FORMA DEL CONTENIDO. Medido con una TO usando el sistema: escribe en
// fragmentos de tres a ocho palabras con abreviaturas, no en párrafos. La
// lectura está armada para muchas líneas cortas —una fila por objetivo, la
// palabra clínica y su observación al lado— y no para prosa larga.

import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Typography from '@mui/material/Typography';

import SesionEstadoChip from '../data/SesionEstadoChip.jsx';
import ModalFormulario from '../modal/ModalFormulario.jsx';
import { Cargando, EstadoError, EstadoVacio } from '../estado/index.js';
import { usePeticion } from '../../hooks/usePeticion.js';
import { etiquetaDeValor } from '../../services/evolucionesService.js';
import { obtenerSesion } from '../../services/sesionesService.js';
import { formatearFecha } from '../../utils/fechas.js';

/** Encabezado de bloque con su contador a la derecha. */
function Bloque({ titulo, contador, children }) {
  return (
    <Box sx={{ mb: 2.5 }}>
      <Box
        sx={{
          display: 'flex',
          alignItems: 'baseline',
          justifyContent: 'space-between',
          gap: 1,
          mb: 1,
        }}
      >
        <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
          {titulo}
        </Typography>
        {contador && (
          <Typography variant="caption" color="text.secondary" className="tabular">
            {contador}
          </Typography>
        )}
      </Box>
      {children}
    </Box>
  );
}

/** Texto que escribió una persona, o el hueco explícito si no hay. */
function TextoDeLaTerapeuta({ children, vacio }) {
  if (!children) {
    return (
      <Typography variant="body2" sx={{ color: 'text.disabled', fontStyle: 'italic' }}>
        {vacio}
      </Typography>
    );
  }
  return (
    // texto-libre: lo escribió una persona y puede traer un token sin
    // espacios. Ver decisión 14 bis.
    <Typography variant="body2" className="texto-libre" sx={{ whiteSpace: 'pre-line' }}>
      {children}
    </Typography>
  );
}

/** Una calificación: el objetivo, la palabra clínica y su observación. */
function FilaCalificada({ evolucion }) {
  const palabra = etiquetaDeValor(evolucion.valor);
  const descripcion = evolucion.objetivo?.descripcion;

  return (
    <Box
      component="li"
      sx={(t) => ({
        listStyle: 'none',
        py: 1.25,
        borderTop: `1px solid ${t.palette.superficie.borde}`,
      })}
    >
      <Box className="texto-libre" sx={{ fontSize: 14, lineHeight: 1.45, mb: 0.5 }}>
        {descripcion ?? 'Objetivo que ya no está en la ficha'}
        {evolucion.objetivo?.activo === false && (
          <Typography component="span" variant="caption" color="text.secondary" sx={{ ml: 0.75 }}>
            (archivado)
          </Typography>
        )}
      </Box>

      <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 1, flexWrap: 'wrap' }}>
        {/* La PALABRA es el dato clínico. El 1-5 de la base no se muestra:
            existe para ordenar y graficar. Decisión 13. */}
        <Box
          component="span"
          sx={(t) => ({
            flex: 'none',
            fontSize: 13,
            fontWeight: 600,
            color: t.palette.primary.dark,
            backgroundColor: t.palette.superficie.acentoSuave,
            borderRadius: `${t.formas.pill}px`,
            px: 1,
            py: '2px',
          })}
        >
          {palabra ?? 'Sin calificar'}
        </Box>
        <Box sx={{ minWidth: 0, flex: 1 }}>
          <TextoDeLaTerapeuta vacio="Sin observaciones">
            {evolucion.observaciones}
          </TextoDeLaTerapeuta>
        </Box>
      </Box>
    </Box>
  );
}

export default function ModalDetalleSesion({ abierto, idSesion, onCerrar, onCargarEvolucion }) {
  const detalle = usePeticion(() => obtenerSesion(idSesion), [idSesion], {
    inmediata: Boolean(idSesion),
  });

  const datos = detalle.datos;
  const sesion = datos?.sesion;
  const evoluciones = datos?.evoluciones ?? [];
  const objetivosActivos = datos?.objetivos_activos ?? [];

  const calificados = new Set(evoluciones.map((e) => e.id_objetivo));
  const sinCalificar = objetivosActivos.filter((o) => !calificados.has(o.id));

  const admite = Boolean(sesion?.admite_evolucion);
  const esPropia = sesion?.es_propia !== false;
  // Solo se ofrece cargar cuando el servidor lo va a aceptar. Las tres
  // condiciones son las mismas que aplica el backend.
  const puedeCargar = Boolean(sesion && esPropia && admite && sinCalificar.length > 0);

  const subtitulo = datos
    ? `${datos.paciente.nombre_completo} · ${formatearFecha(sesion.fecha)} · ${sesion.hora_inicio?.slice(0, 5)}`
    : undefined;

  return (
    <ModalFormulario
      abierto={abierto}
      ancho={640}
      titulo="Registro de la sesión"
      subtitulo={subtitulo}
      soloCerrar
      onPedirCierre={onCerrar}
    >
      {detalle.cargando && <Cargando texto="Abriendo la sesión..." minHeight={140} />}
      {detalle.error && <EstadoError error={detalle.error} onReintentar={detalle.recargar} />}

      {datos && (
        <>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, flexWrap: 'wrap', mb: 2.5 }}>
            <SesionEstadoChip estado={sesion.estado} />
            <Typography variant="body2" color="text.secondary">
              Atendió {datos.terapeuta?.nombre_completo ?? 'un terapeuta del centro'}
              {esPropia ? '' : ' · otro terapeuta'}
            </Typography>
          </Box>

          <Bloque titulo="Notas del día">
            <TextoDeLaTerapeuta vacio="No se cargaron notas en esta sesión.">
              {sesion.notas}
            </TextoDeLaTerapeuta>
          </Bloque>

          <Bloque
            titulo="Objetivos trabajados"
            // En una ausencia no corresponde calificar: va "—" y no "0 de 3",
            // que se leería como trabajo pendiente. Mismo criterio que la
            // columna del historial y que el backend.
            contador={admite ? `${evoluciones.length} de ${sesion.objetivos?.total ?? 0}` : '—'}
          >
            {!admite ? (
              <Typography variant="body2" color="text.secondary">
                La sesión está marcada como ausencia: no corresponde calificar
                objetivos, y por eso no hay nada que leer acá.
              </Typography>
            ) : evoluciones.length === 0 ? (
              <EstadoVacio
                plano
                titulo="Todavía no se calificó ningún objetivo"
                descripcion="La sesión está registrada pero no tiene evolución cargada."
              />
            ) : (
              <Box component="ul" sx={{ m: 0, p: 0 }}>
                {evoluciones.map((evolucion) => (
                  <FilaCalificada key={evolucion.id} evolucion={evolucion} />
                ))}
              </Box>
            )}
          </Bloque>

          {/* Los que quedaron afuera. Solo tiene sentido en una sesión que
              admite evolución: en una ausencia no hay "pendiente". */}
          {admite && sinCalificar.length > 0 && (
            <Bloque titulo="Sin calificar en esta sesión" contador={`${sinCalificar.length}`}>
              <Box component="ul" sx={{ m: 0, p: 0 }}>
                {sinCalificar.map((objetivo) => (
                  <Box
                    component="li"
                    key={objetivo.id}
                    className="texto-libre"
                    sx={(t) => ({
                      listStyle: 'none',
                      py: 1,
                      fontSize: 14,
                      lineHeight: 1.45,
                      color: t.palette.text.secondary,
                      borderTop: `1px solid ${t.palette.superficie.borde}`,
                    })}
                  >
                    {objetivo.descripcion}
                  </Box>
                ))}
              </Box>
            </Bloque>
          )}

          {puedeCargar && (
            <Box sx={{ display: 'flex', justifyContent: 'flex-start', pt: 0.5 }}>
              <Button variant="contained" onClick={() => onCargarEvolucion?.(sesion.id)}>
                Cargar evolución
              </Button>
            </Box>
          )}
        </>
      )}
    </ModalFormulario>
  );
}

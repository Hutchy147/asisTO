// frontend/src/components/data/GraficoEvolucion.jsx
//
// Gráfico de evolución de UN objetivo en el tiempo. SVG propio, sin
// librería, y es una decisión: el eje Y de este proyecto no es numérico
// sino las cinco palabras de la escala, y toda librería de gráficos empuja
// hacia ejes numéricos —ticks intermedios, decimales, interpolación— que
// acá son exactamente lo que no puede aparecer. Con cinco posiciones fijas
// y una serie, el SVG es más corto que la configuración que haría falta
// para domar una librería.
//
// El componente dibuja UNA serie. Varias objetivos = varios gráficos, que
// es la decisión de producto: promediar "No logrado" con "Logrado" entre
// objetivos que miden cosas distintas da un número sin significado clínico.

import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import { useTheme } from '@mui/material/styles';

import { ESCALA_VALORES, etiquetaDeValor } from '../../services/evolucionesService.js';
import { formatearFecha } from '../../utils/fechas.js';

// Sistema de coordenadas interno del SVG. El viewBox lo escala solo, así
// que estos números son proporciones, no píxeles en pantalla.
const ANCHO = 720;
const MARGEN = { arriba: 14, derecha: 18, abajo: 38, izquierda: 104 };
const PASO_Y = 42; // separación entre los cinco escalones
const ALTO = MARGEN.arriba + PASO_Y * (ESCALA_VALORES.length - 1) + MARGEN.abajo;

const RADIO_PUNTO = 4.5;

/** Y del escalón. El 5 arriba y el 1 abajo, como se lee una escala. */
function yDeValor(valor) {
  const maximo = ESCALA_VALORES.length;
  return MARGEN.arriba + (maximo - valor) * PASO_Y;
}

/** Fecha ISO a milisegundos, para posicionar en el eje. */
function tiempo(iso) {
  return new Date(`${iso}T00:00:00`).getTime();
}

export default function GraficoEvolucion({ serie, titulo }) {
  const tema = useTheme();
  const puntos = serie?.puntos ?? [];

  if (puntos.length === 0) return null;

  const archivado = !serie.activo;
  const colorLinea = archivado
    ? tema.palette.text.secondary
    : tema.palette.primary.main;
  // Los archivados van atenuados, no en otro color: siguen siendo el mismo
  // dato clínico, solo que cerrado. Un color distinto se leería como otra
  // categoría de medición.
  const opacidadSerie = archivado ? 0.55 : 1;

  const tiempos = puntos.map((p) => tiempo(p.fecha));
  const desde = Math.min(...tiempos);
  const hasta = Math.max(...tiempos);
  const anchoUtil = ANCHO - MARGEN.izquierda - MARGEN.derecha;

  // Eje X de TIEMPO REAL, no de posición en la lista. Es lo que hace que
  // dos calificaciones separadas por una semana y por seis meses no se
  // vean igual. Con un solo punto (o todos el mismo día) no hay rango: se
  // centra en vez de dividir por cero.
  const xDeFecha = (iso) => {
    if (hasta === desde) return MARGEN.izquierda + anchoUtil / 2;
    return MARGEN.izquierda + ((tiempo(iso) - desde) / (hasta - desde)) * anchoUtil;
  };

  // La línea une mediciones CONSECUTIVAS en la secuencia de sesiones. Si
  // entre dos calificaciones hubo una sesión sin calificar este objetivo,
  // la línea se corta: unirlas afirmaría una trayectoria que nadie midió.
  const tramos = [];
  let tramo = [];
  puntos.forEach((punto) => {
    if (punto.valor === null || punto.valor === undefined) {
      if (tramo.length > 0) tramos.push(tramo);
      tramo = [];
      return;
    }
    tramo.push(punto);
  });
  if (tramo.length > 0) tramos.push(tramo);

  const sinCalificar = puntos.filter((p) => p.valor === null || p.valor === undefined);
  const calificados = puntos.length - sinCalificar.length;

  // La línea de un objetivo archivado TERMINA donde se archivó. Sin esto
  // quedaría abierta, como si siguiera vigente.
  const xArchivado = serie.fecha_archivado
    ? xDeFecha(serie.fecha_archivado.slice(0, 10))
    : null;
  const archivadoEnRango =
    xArchivado !== null
    && xArchivado >= MARGEN.izquierda
    && xArchivado <= ANCHO - MARGEN.derecha;

  // El resumen accesible describe LOS DATOS, no repite el texto del
  // objetivo: ese ya está como encabezado al lado del gráfico y meterlo
  // acá haría que un lector de pantalla lo anuncie dos veces. Por eso
  // este componente no renderiza `descripcion` en ningún lado — el que la
  // muestra es el llamador, con su `texto-libre` puesto.
  const resumen = calificados === 0
    ? 'Sin calificaciones en el período.'
    : `${calificados} calificación(es) en el período, de "${
      etiquetaDeValor(tramos[0]?.[0]?.valor)}" a "${
      etiquetaDeValor(tramos[tramos.length - 1]?.slice(-1)[0]?.valor)}".`;

  return (
    <Box sx={{ mb: 1 }}>
      {titulo}
      <Box
        component="svg"
        viewBox={`0 0 ${ANCHO} ${ALTO}`}
        role="img"
        aria-label={resumen}
        sx={{ width: '100%', height: 'auto', display: 'block', overflow: 'visible' }}
      >
        <title>{resumen}</title>

        {/* Los cinco escalones, con su palabra. El número 1..5 NO aparece
            en ningún lado: es representación interna. Ver decisión 13. */}
        {ESCALA_VALORES.map((paso) => (
          <g key={paso.valor}>
            <line
              x1={MARGEN.izquierda}
              y1={yDeValor(paso.valor)}
              x2={ANCHO - MARGEN.derecha}
              y2={yDeValor(paso.valor)}
              stroke={tema.palette.superficie.borde}
              strokeWidth="1"
            />
            <text
              x={MARGEN.izquierda - 10}
              y={yDeValor(paso.valor) + 4}
              textAnchor="end"
              fontSize="12"
              fill={tema.palette.text.secondary}
            >
              {paso.etiqueta}
            </text>
          </g>
        ))}

        {/* Marca de cierre del objetivo archivado */}
        {archivadoEnRango && (
          <line
            x1={xArchivado}
            y1={MARGEN.arriba - 6}
            x2={xArchivado}
            y2={ALTO - MARGEN.abajo + 6}
            stroke={tema.palette.text.secondary}
            strokeWidth="1.5"
            strokeDasharray="4 3"
          />
        )}

        {/* Sesiones donde este objetivo NO se calificó. Van como marca en
            el eje y no como punto en la trama: no hay valor que ubicar.
            Distinguir la ausencia del resto importa — en una ausencia no
            se podía calificar, en una sesión trabajada sí y no se hizo. */}
        {sinCalificar.map((punto) => (
          <line
            key={`sc-${punto.id_sesion}`}
            x1={xDeFecha(punto.fecha)}
            y1={ALTO - MARGEN.abajo}
            x2={xDeFecha(punto.fecha)}
            y2={ALTO - MARGEN.abajo + 7}
            stroke={
              punto.estado_sesion === 'ausencia'
                ? tema.palette.sesionEstado.ausencia.fg
                : tema.palette.sesionEstado.incompleta.fg
            }
            strokeWidth="2"
          >
            <title>
              {`${formatearFecha(punto.fecha)} — ${
                punto.estado_sesion === 'ausencia'
                  ? 'ausencia: no correspondía calificar'
                  : 'sesión sin calificar este objetivo'}`}
            </title>
          </line>
        ))}

        {/* Los tramos de línea, uno por racha de mediciones consecutivas */}
        <g opacity={opacidadSerie}>
          {tramos.map((segmento) => (
            <polyline
              key={`t-${segmento[0].id_sesion}`}
              fill="none"
              stroke={colorLinea}
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              points={segmento
                .map((p) => `${xDeFecha(p.fecha)},${yDeValor(p.valor)}`)
                .join(' ')}
            />
          ))}

          {puntos
            .filter((p) => p.valor !== null && p.valor !== undefined)
            .map((punto) => (
              <circle
                key={`p-${punto.id_sesion}`}
                cx={xDeFecha(punto.fecha)}
                cy={yDeValor(punto.valor)}
                r={RADIO_PUNTO}
                fill={colorLinea}
                stroke={tema.palette.superficie.tarjeta}
                strokeWidth="1.5"
              >
                <title>
                  {`${formatearFecha(punto.fecha)} — ${etiquetaDeValor(punto.valor)}`}
                  {punto.terapeuta ? ` — ${punto.terapeuta}` : ''}
                </title>
              </circle>
            ))}
        </g>

        {/* Eje X: primera y última fecha. Poner una etiqueta por sesión las
            amontona y no agrega nada; la fecha exacta de cada punto está en
            su tooltip. */}
        <line
          x1={MARGEN.izquierda}
          y1={ALTO - MARGEN.abajo}
          x2={ANCHO - MARGEN.derecha}
          y2={ALTO - MARGEN.abajo}
          stroke={tema.palette.superficie.bordeFuerte}
          strokeWidth="1"
        />
        <text
          x={MARGEN.izquierda}
          y={ALTO - 10}
          fontSize="12"
          fill={tema.palette.text.secondary}
        >
          {formatearFecha(puntos[0].fecha)}
        </text>
        {hasta !== desde && (
          <text
            x={ANCHO - MARGEN.derecha}
            y={ALTO - 10}
            textAnchor="end"
            fontSize="12"
            fill={tema.palette.text.secondary}
          >
            {formatearFecha(puntos[puntos.length - 1].fecha)}
          </text>
        )}
      </Box>

      {calificados === 0 && (
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
          Hubo {puntos.length} sesión(es) en el período y este objetivo no se
          calificó en ninguna.
        </Typography>
      )}
    </Box>
  );
}

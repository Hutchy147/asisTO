// frontend/src/components/data/GraficoEvolucion.jsx
//
// Gráfico de evolución de UN objetivo en el tiempo. SVG propio, sin
// librería, y es una decisión: el eje Y de este proyecto no es numérico
// sino las cinco palabras de la escala, y toda librería de gráficos empuja
// hacia ejes numéricos —ticks intermedios, decimales, interpolación— que
// acá son exactamente lo que no puede aparecer.
//
// El componente dibuja UNA serie. Varios objetivos = varios gráficos, que
// es la decisión de producto: promediar "No logrado" con "Logrado" entre
// objetivos que miden cosas distintas da un número sin significado clínico.
//
// FORMA (simplificada el 2026-10-25). Una sola vista: una curva suave, con
// área debajo, que pasa por CADA calificación. Se allana cuando entre dos
// calificaciones no hay cambio y sube o baja cuando lo hay. Se sacaron la
// vista de "nivel alcanzado", el selector, la franja de marcas de sesiones
// sin calificar / ausencias y su leyenda: el gráfico tiene que leerse de un
// vistazo. Las sesiones sin calificar siguen consultables en la pestaña
// Sesiones.

import { useId } from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import useMediaQuery from '@mui/material/useMediaQuery';
import { useTheme } from '@mui/material/styles';

import { ESCALA_VALORES, etiquetaDeValor } from '../../services/evolucionesService.js';
import { formatearFecha } from '../../utils/fechas.js';

// Sistema de coordenadas interno del SVG. El viewBox lo escala solo, así
// que estos números son proporciones, no píxeles en pantalla.
const ANCHO = 720;
const ANCHO_CELULAR = 360;
const IZQUIERDA_CELULAR = 80;
const MARGEN = { arriba: 14, derecha: 18, izquierda: 104 };
const PASO_Y = 42; // separación entre los cinco escalones

// Y de la fila más baja de la escala ("No logrado").
const PISO_ESCALA = MARGEN.arriba + PASO_Y * (ESCALA_VALORES.length - 1);

// Las fechas van justo debajo de la escala, sin eje ni franja de por medio.
const Y_FECHAS = PISO_ESCALA + 26;
const ALTO = Y_FECHAS + 8;

const RADIO_PUNTO = 4;

/** Y del escalón. El 5 arriba y el 1 abajo, como se lee una escala. */
function yDeValor(valor) {
  return MARGEN.arriba + (ESCALA_VALORES.length - valor) * PASO_Y;
}

/** Fecha ISO a milisegundos, para posicionar en el eje. */
function tiempo(iso) {
  return new Date(`${iso}T00:00:00`).getTime();
}

/**
 * Curva suave por los puntos {x, y}. Cada tramo es una S con tangente
 * horizontal en los dos extremos: la curva se allana al pasar por cada punto
 * y sube o baja entre uno y otro, sin picos ni excesos (nunca pasa de los
 * valores que unen, a diferencia de un spline común).
 */
function curvaSuave(pts) {
  if (pts.length === 0) return '';
  let d = `M ${pts[0].x} ${pts[0].y}`;
  for (let i = 1; i < pts.length; i += 1) {
    const a = pts[i - 1];
    const b = pts[i];
    const medio = (a.x + b.x) / 2;
    d += ` C ${medio} ${a.y}, ${medio} ${b.y}, ${b.x} ${b.y}`;
  }
  return d;
}

export default function GraficoEvolucion({ serie, titulo }) {
  const tema = useTheme();
  const idDegradado = `degradado-${useId().replace(/:/g, '')}`;
  const puntos = serie?.puntos ?? [];
  // En el celular el SVG de 720 se achicaba a la mitad y los rótulos quedaban
  // de 5 px (usabilidad, madre): con un lienzo angosto se ven a tamaño real.
  const celular = useMediaQuery(tema.breakpoints.down('sm'));
  const ancho = celular ? ANCHO_CELULAR : ANCHO;
  const izquierda = celular ? IZQUIERDA_CELULAR : MARGEN.izquierda;
  const derecha = MARGEN.derecha;

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
  const fechaArchivado = serie.fecha_archivado
    ? serie.fecha_archivado.slice(0, 10)
    : null;

  const desde = Math.min(...tiempos);
  // El dominio del eje incluye `fecha_archivado`. Sin esto la marca de
  // cierre quedaba SIEMPRE afuera y no se dibujaba nunca: un objetivo se
  // archiva después de su última sesión calificada, por definición. El
  // gráfico mostraba una línea que "terminaba" por falta de puntos, que no
  // es lo mismo que terminar porque el objetivo se cerró. Encontrado
  // mirando la ficha de un paciente dado de baja con datos reales.
  const hasta = Math.max(
    ...tiempos,
    fechaArchivado ? tiempo(fechaArchivado) : -Infinity,
  );
  const anchoUtil = ancho - izquierda - derecha;

  // Eje X de TIEMPO REAL, no de posición en la lista. Es lo que hace que
  // dos calificaciones separadas por una semana y por seis meses no se
  // vean igual. Con un solo punto no hay rango: se centra.
  const xDeFecha = (iso) => {
    if (hasta === desde) return izquierda + anchoUtil / 2;
    return izquierda + ((tiempo(iso) - desde) / (hasta - desde)) * anchoUtil;
  };

  const calificados = puntos.filter((p) => p.valor !== null && p.valor !== undefined);

  const puntosCurva = calificados.map((p) => ({ x: xDeFecha(p.fecha), y: yDeValor(p.valor) }));
  const trazoCurva = curvaSuave(puntosCurva);
  const areaCurva = puntosCurva.length > 1
    ? `${trazoCurva} L ${puntosCurva[puntosCurva.length - 1].x} ${PISO_ESCALA} L ${puntosCurva[0].x} ${PISO_ESCALA} Z`
    : '';

  // Marcador de la última calificación: es "dónde está hoy" el objetivo.
  const ultimo = calificados.length > 1 ? calificados[calificados.length - 1] : null;
  const xUltimo = ultimo ? xDeFecha(ultimo.fecha) : 0;
  const yUltimo = ultimo ? yDeValor(ultimo.valor) : 0;
  // Si no hay lugar a la derecha para el rótulo, va arriba y a la izquierda.
  const cercaDelBorde = xUltimo > ancho - derecha - 96;

  // La línea de un objetivo archivado TERMINA donde se archivó. Sin esto
  // quedaría abierta, como si siguiera vigente.
  const xArchivado = fechaArchivado ? xDeFecha(fechaArchivado) : null;
  const archivadoEnRango =
    xArchivado !== null
    && xArchivado >= izquierda
    && xArchivado <= ancho - derecha;

  // El resumen accesible describe LOS DATOS, no repite el texto del
  // objetivo: ese ya está como encabezado al lado del gráfico y meterlo
  // acá haría que un lector de pantalla lo anuncie dos veces.
  const resumen = calificados.length === 0
    ? 'Sin calificaciones en el período.'
    : `${calificados.length} ${calificados.length === 1 ? 'calificación' : 'calificaciones'} en el período, de "${
      etiquetaDeValor(calificados[0].valor)}" a "${
      etiquetaDeValor(calificados[calificados.length - 1].valor)}".`;

  return (
    <Box sx={{ mb: 1 }}>
      {titulo}
      <Box
        component="svg"
        viewBox={`0 0 ${ancho} ${ALTO}`}
        role="img"
        aria-label={resumen}
        sx={{ width: '100%', height: 'auto', display: 'block', overflow: 'visible' }}
      >
        <title>{resumen}</title>

        {/* Bandas alternadas entre escalones: dan la sensación de "subir de
            nivel" (referencia: gráficos de progreso hacia una meta). */}
        {ESCALA_VALORES.filter((paso) => paso.valor < ESCALA_VALORES.length).map((paso) => (
          paso.valor % 2 === 1 && (
            <rect
              key={`banda-${paso.valor}`}
              x={izquierda}
              y={yDeValor(paso.valor + 1)}
              width={anchoUtil}
              height={PASO_Y}
              fill={colorLinea}
              fillOpacity="0.05"
            />
          )
        ))}

        {/* Los cinco escalones, con su palabra. El número 1..5 NO aparece
            en ningún lado: es representación interna. Ver decisión 13.
            El más alto ("Logrado") es la meta y va resaltado. */}
        {ESCALA_VALORES.map((paso) => {
          const meta = paso.valor === ESCALA_VALORES.length;
          return (
            <g key={paso.valor}>
              <line
                x1={izquierda}
                y1={yDeValor(paso.valor)}
                x2={ancho - derecha}
                y2={yDeValor(paso.valor)}
                stroke={meta ? colorLinea : tema.palette.superficie.borde}
                strokeOpacity={meta ? 0.55 : 1}
                strokeWidth={meta ? 1.75 : 1}
              />
              <text
                x={izquierda - 10}
                y={yDeValor(paso.valor) + 4}
                textAnchor="end"
                fontSize="12"
                fontWeight={meta ? 600 : 400}
                fill={meta ? colorLinea : tema.palette.text.secondary}
              >
                {paso.etiqueta}
              </text>
            </g>
          );
        })}

        {/* Marca de cierre del objetivo archivado */}
        {archivadoEnRango && (
          <line
            x1={xArchivado}
            y1={MARGEN.arriba - 6}
            x2={xArchivado}
            y2={PISO_ESCALA + 6}
            stroke={tema.palette.text.secondary}
            strokeWidth="1.5"
            strokeDasharray="4 3"
          />
        )}

        <defs>
          <linearGradient id={idDegradado} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={colorLinea} stopOpacity="0.30" />
            <stop offset="100%" stopColor={colorLinea} stopOpacity="0.02" />
          </linearGradient>
        </defs>

        {/* La curva: suave, con área debajo, por cada calificación. */}
        <g opacity={opacidadSerie}>
          {areaCurva && <path d={areaCurva} fill={`url(#${idDegradado})`} stroke="none" />}
          {trazoCurva && puntosCurva.length > 1 && (
            <path
              d={trazoCurva}
              fill="none"
              stroke={colorLinea}
              strokeWidth="2.75"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          )}

          {calificados.map((punto) => (
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

          {ultimo && (
            <g>
              <circle cx={xUltimo} cy={yUltimo} r={RADIO_PUNTO + 5} fill={colorLinea} fillOpacity="0.22" />
              <circle
                cx={xUltimo} cy={yUltimo} r={RADIO_PUNTO + 1}
                fill={colorLinea} stroke={tema.palette.superficie.tarjeta} strokeWidth="1.5"
              />
              <text
                x={cercaDelBorde ? xUltimo - 12 : xUltimo + 14}
                y={cercaDelBorde ? yUltimo - 12 : yUltimo + 4}
                textAnchor={cercaDelBorde ? 'end' : 'start'}
                fontSize="12"
                fontWeight="600"
                fill={colorLinea}
                // Halo del color del fondo: la curva puede pasar por debajo
                // del rótulo y no tiene que tapar las letras.
                stroke={tema.palette.superficie.tarjeta}
                strokeWidth="4"
                strokeLinejoin="round"
                paintOrder="stroke"
              >
                {etiquetaDeValor(ultimo.valor)}
              </text>
            </g>
          )}
        </g>

        {/* Fechas: primera y última. Una etiqueta por sesión las amontona y
            no agrega nada; la fecha exacta de cada punto está en su
            tooltip. */}
        <text
          x={izquierda}
          y={Y_FECHAS}
          fontSize="12"
          fill={tema.palette.text.secondary}
        >
          {formatearFecha(puntos[0].fecha)}
        </text>
        {hasta !== desde && (
          <text
            x={ancho - derecha}
            y={Y_FECHAS}
            textAnchor="end"
            fontSize="12"
            fill={tema.palette.text.secondary}
          >
            {/* El extremo derecho es la fecha de archivado cuando la hay:
                es la que fija el dominio del eje. Poner la última sesión
                mentiría sobre dónde termina el gráfico. */}
            {formatearFecha(fechaArchivado ?? puntos[puntos.length - 1].fecha)}
          </text>
        )}
      </Box>

      {calificados.length === 0 && (
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
          {puntos.length === 1
            ? 'Hubo una sesión en el período y este objetivo no se calificó.'
            : `Hubo ${puntos.length} sesiones en el período y este objetivo no se calificó en ninguna.`}
        </Typography>
      )}
    </Box>
  );
}

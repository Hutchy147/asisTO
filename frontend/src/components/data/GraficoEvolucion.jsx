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
// FORMA DE LA CURVA (rehecha el 2026-10-24). Antes se unían las calificaciones
// con rectas, sólidas o punteadas: con objetivos que suben y bajan seguido
// quedaba un zigzag que no se leía como evolución. Ahora la curva es suave y
// con área debajo, y por defecto muestra el NIVEL ALCANZADO: sube cuando el
// paciente avanza y se allana cuando no. Cada calificación real sigue
// dibujada como punto; los que quedan por debajo del nivel alcanzado (una
// sesión peor que la mejor hasta ahora) van huecos, así una baja no se
// esconde. Un selector permite ver la curva por cada calificación.

import { useId, useState } from 'react';
import Box from '@mui/material/Box';
import ToggleButton from '@mui/material/ToggleButton';
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup';
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

// SEPARACIÓN ENTRE LA ESCALA Y EL EJE, y es una corrección de un defecto
// real: antes el eje X se dibujaba justo en la Y de "No logrado", así que
// las marcas de sesión sin calificar arrancaban sobre esa fila y se leían
// como calificaciones de "No logrado" — la lectura más dañina posible.
// Ninguna marca puede quedar alineada con una fila de palabra.
const SEPARACION_EJE = 26;
const Y_EJE = PISO_ESCALA + SEPARACION_EJE;

// Banda propia de las marcas, debajo del eje. No se superpone con nada.
const BANDA_ARRIBA = Y_EJE + 6;

// Las marcas del MISMO DIA se APILAN, no se superponen. Un paciente puede
// tener dos sesiones el mismo dia —medido en datos reales: cinco fechas asi
// en el paciente 1— y dos marcas en la misma x se dibujaban una sobre la
// otra. El conteo visible quedaba corto y, peor, si una era ausencia y la
// otra no, un color TAPABA al otro y la ausencia desaparecia. Eso es
// informacion clinica oculta, no un problema de densidad.
const ALTURA_MARCA = 7;
const SEPARACION_MARCA = 3;

const RADIO_PUNTO = 4;

/** Alto total del SVG, que depende de cuantas marcas haya que apilar. */
function altoTotal(maxApilado) {
  const banda = Math.max(1, maxApilado) * ALTURA_MARCA
    + Math.max(0, maxApilado - 1) * SEPARACION_MARCA;
  return BANDA_ARRIBA + banda + 22;
}

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

/** Una entrada del conteo al pie, con el color de su marca al lado. */
function Conteo({ color, cantidad, texto, singular }) {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
      <Box
        sx={(t) => ({
          width: 9,
          height: 9,
          borderRadius: '2px',
          backgroundColor: typeof color === 'function' ? color(t) : color,
          flex: 'none',
        })}
      />
      <Typography variant="body2" color="text.secondary">
        <strong>{cantidad}</strong> {cantidad === 1 && singular ? singular : texto}
      </Typography>
    </Box>
  );
}

export default function GraficoEvolucion({ serie, titulo }) {
  const tema = useTheme();
  const idDegradado = `degradado-${useId().replace(/:/g, '')}`;
  const [modo, setModo] = useState('progreso'); // 'progreso' | 'calificaciones'
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
  const sinCalificar = puntos.filter((p) => p.valor === null || p.valor === undefined);

  // Mejor nivel alcanzado hasta cada calificación (nunca baja).
  let techo = 0;
  const alcanzado = calificados.map((p) => {
    techo = Math.max(techo, p.valor);
    return techo;
  });
  const hayBajas = calificados.some((p, i) => p.valor < alcanzado[i]);
  const verProgreso = modo === 'progreso' || !hayBajas;
  const puntosCurva = calificados.map((p, i) => ({
    x: xDeFecha(p.fecha),
    y: yDeValor(verProgreso ? alcanzado[i] : p.valor),
  }));
  const trazoCurva = curvaSuave(puntosCurva);
  // Marcador de la última calificación: es "dónde está hoy" el objetivo.
  const ultimo = calificados.length > 1 ? calificados[calificados.length - 1] : null;
  const xUltimo = ultimo ? xDeFecha(ultimo.fecha) : 0;
  const yUltimo = ultimo ? yDeValor(ultimo.valor) : 0;
  // Si no hay lugar a la derecha para el rótulo, va arriba y a la izquierda.
  const cercaDelBorde = xUltimo > ancho - derecha - 96;
  const areaCurva = puntosCurva.length > 1
    ? `${trazoCurva} L ${puntosCurva[puntosCurva.length - 1].x} ${PISO_ESCALA} L ${puntosCurva[0].x} ${PISO_ESCALA} Z`
    : '';

  const ausencias = sinCalificar.filter((p) => p.estado_sesion === 'ausencia');
  const trabajadasSinCalificar = sinCalificar.length - ausencias.length;

  // Se agrupa por FECHA y no por x: son la misma cosa —la x sale de la
  // fecha— pero comparar fechas es exacto y comparar floats no.
  const nivelPorPunto = new Map();
  const ocupadosPorFecha = new Map();
  sinCalificar.forEach((punto) => {
    const nivel = ocupadosPorFecha.get(punto.fecha) ?? 0;
    nivelPorPunto.set(punto.id_sesion, nivel);
    ocupadosPorFecha.set(punto.fecha, nivel + 1);
  });
  const maxApilado = Math.max(1, ...ocupadosPorFecha.values());
  const ALTO = altoTotal(maxApilado);

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
      etiquetaDeValor(calificados[calificados.length - 1].valor)}"${
      verProgreso ? `; mejor nivel alcanzado: "${etiquetaDeValor(alcanzado[alcanzado.length - 1])}"` : ''}.`;

  return (
    <Box sx={{ mb: 1 }}>
      {titulo}
      {hayBajas && (
        <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 0.5 }}>
          <ToggleButtonGroup
            exclusive size="small" value={modo} aria-label="Qué mostrar la curva"
            onChange={(_, valor) => { if (valor) setModo(valor); }}
          >
            <ToggleButton value="progreso" sx={{ px: 1.25, py: 0.25, textTransform: 'none', fontSize: 12 }}>
              Nivel alcanzado
            </ToggleButton>
            <ToggleButton value="calificaciones" sx={{ px: 1.25, py: 0.25, textTransform: 'none', fontSize: 12 }}>
              Cada calificación
            </ToggleButton>
          </ToggleButtonGroup>
        </Box>
      )}
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

        {/* La curva: suave, con área debajo. Se allana cuando no hay avance. */}
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

          {calificados.map((punto, i) => {
            // Hueco = calificación por debajo del mejor nivel ya alcanzado.
            const porDebajo = verProgreso && punto.valor < alcanzado[i];
            return (
              <circle
                key={`p-${punto.id_sesion}`}
                cx={xDeFecha(punto.fecha)}
                cy={yDeValor(punto.valor)}
                r={RADIO_PUNTO}
                fill={porDebajo ? tema.palette.superficie.tarjeta : colorLinea}
                stroke={porDebajo ? colorLinea : tema.palette.superficie.tarjeta}
                strokeWidth={porDebajo ? 2 : 1.5}
              >
                <title>
                  {`${formatearFecha(punto.fecha)} — ${etiquetaDeValor(punto.valor)}`}
                  {porDebajo ? ` (nivel alcanzado: ${etiquetaDeValor(alcanzado[i])})` : ''}
                  {punto.terapeuta ? ` — ${punto.terapeuta}` : ''}
                </title>
              </circle>
            );
          })}

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
              >
                {etiquetaDeValor(ultimo.valor)}
              </text>
            </g>
          )}
        </g>

        {/* Eje X, SEPARADO de la fila más baja de la escala */}
        <line
          x1={izquierda}
          y1={Y_EJE}
          x2={ancho - derecha}
          y2={Y_EJE}
          stroke={tema.palette.superficie.bordeFuerte}
          strokeWidth="1"
        />

        {/* Banda de sesiones sin calificar, DEBAJO del eje y en su propia
            franja. Poco peso visual a propósito: son muchas —la mayoría de
            las sesiones no califican un objetivo dado— y si pesaran como
            los puntos taparían la serie, que es lo que hay que leer. */}
        {sinCalificar.map((punto) => (
          <line
            key={`sc-${punto.id_sesion}`}
            x1={xDeFecha(punto.fecha)}
            y1={BANDA_ARRIBA
              + nivelPorPunto.get(punto.id_sesion) * (ALTURA_MARCA + SEPARACION_MARCA)}
            x2={xDeFecha(punto.fecha)}
            y2={BANDA_ARRIBA
              + nivelPorPunto.get(punto.id_sesion) * (ALTURA_MARCA + SEPARACION_MARCA)
              + ALTURA_MARCA}
            stroke={
              punto.estado_sesion === 'ausencia'
                ? tema.palette.sesionEstado.ausencia.fg
                : tema.palette.sesionEstado.incompleta.fg
            }
            // La ausencia más gruesa y opaca: con el mismo trazo, ámbar y
            // rojo se confundían (pruebas de usabilidad con familias).
            strokeWidth={punto.estado_sesion === 'ausencia' ? 3 : 1}
            opacity={punto.estado_sesion === 'ausencia' ? 0.9 : 0.6}
          >
            <title>
              {`${formatearFecha(punto.fecha)} — ${
                punto.estado_sesion === 'ausencia'
                  ? 'ausencia: no correspondía calificar'
                  : 'sesión sin calificar este objetivo'}`}
            </title>
          </line>
        ))}

        {/* Fechas: primera y última. Una etiqueta por sesión las amontona y
            no agrega nada; la fecha exacta de cada punto está en su
            tooltip. */}
        <text
          x={izquierda}
          y={ALTO - 4}
          fontSize="12"
          fill={tema.palette.text.secondary}
        >
          {formatearFecha(puntos[0].fecha)}
        </text>
        {hasta !== desde && (
          <text
            x={ancho - derecha}
            y={ALTO - 4}
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

      {/* Conteo explícito de cada categoría. El número no puede depender de
          que alguien cuente marcas de 1 px: apiladas o no, la cantidad se
          lee acá. */}
      <Box
        sx={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: 2,
          mt: 0.5,
          pl: `${(izquierda / ancho) * 100}%`,
        }}
      >
        <Conteo
          color={archivado ? 'text.secondary' : 'primary.main'}
          cantidad={calificados.length}
          texto="calificaciones"
          singular="calificación"
        />
        <Conteo
          color={(t) => t.palette.sesionEstado.incompleta.fg}
          cantidad={trabajadasSinCalificar}
          texto="sesiones sin calificar este objetivo"
          singular="sesión sin calificar este objetivo"
        />
        <Conteo
          color={(t) => t.palette.sesionEstado.ausencia.fg}
          cantidad={ausencias.length}
          texto="ausencias"
          singular="ausencia"
        />
        {calificados.length > 1 && (
          <Typography variant="body2" color="text.secondary">
            {verProgreso
              ? 'curva: mejor nivel alcanzado hasta cada fecha'
              : 'curva: sigue cada calificación'}
          </Typography>
        )}
        {verProgreso && hayBajas && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
            <Box
              component="span"
              sx={(t) => ({
                width: 9, height: 9, borderRadius: '50%', flex: 'none', boxSizing: 'border-box',
                border: `2px solid ${archivado ? t.palette.text.secondary : t.palette.primary.main}`,
              })}
            />
            <Typography variant="body2" color="text.secondary">
              punto hueco: calificación por debajo del mejor nivel
            </Typography>
          </Box>
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

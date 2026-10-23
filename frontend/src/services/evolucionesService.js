// frontend/src/services/evolucionesService.js
// Contrato: docs/api-sesiones-evoluciones.md

import { del, post, put } from './api.js';

/**
 * Escala de logro del centro. ÚNICO lugar donde el número de la base se
 * traduce a la palabra que usa el terapeuta.
 *
 * En la base la calificación es un TINYINT de 1 a 5 porque hay que poder
 * ordenarla, promediarla y graficarla. En pantalla eso no se muestra: un
 * objetivo está "En proceso", no "3 de 5". El número es representación
 * interna; la palabra es el dato clínico.
 *
 * Si esta tabla se duplica en algún componente, las dos versiones se
 * separan y la interfaz empieza a decir cosas distintas en cada pantalla.
 * Importar `etiquetaDeValor` desde acá, siempre.
 */
export const ESCALA_VALORES = [
  { valor: 1, etiqueta: 'No logrado' },
  { valor: 2, etiqueta: 'Inicial' },
  { valor: 3, etiqueta: 'En proceso' },
  { valor: 4, etiqueta: 'Avanzado' },
  { valor: 5, etiqueta: 'Logrado' },
];

/**
 * Qué significa cada palabra, dicho para la familia (pruebas de usabilidad:
 * «¿Inicial es bueno o malo?»). Mismo orden que ESCALA_VALORES.
 */
export const SIGNIFICADO_NIVEL = {
  1: 'Todavía no lo consigue, aun con ayuda.',
  2: 'Empieza a hacerlo, con mucha ayuda.',
  3: 'Lo hace a veces o con algo de ayuda.',
  4: 'Lo hace casi siempre, con poca ayuda.',
  5: 'Lo hace solo y de manera sostenida.',
};

/** Palabra de la escala. `null` cuando todavía no se calificó. */
export function etiquetaDeValor(valor) {
  if (valor === null || valor === undefined) return null;
  return ESCALA_VALORES.find((paso) => paso.valor === Number(valor))?.etiqueta ?? null;
}

/**
 * Resumen EN PALABRAS SIMPLES de cómo viene un objetivo, para la familia y el
 * paciente. Compara el promedio de las primeras calificaciones del período con
 * el de las últimas, y NUNCA contradice el último tramo del gráfico (pruebas de
 * usabilidad: decía «le costó más» cuando la última calificación había subido,
 * y «estable» con saltos de Inicial a Logrado). Siempre termina con el nivel
 * de la primera y de la última calificación, que es lo que se ve en el gráfico.
 * Con menos de 3 calificaciones no opina.
 * -> { texto, tono: 'bien' | 'igual' | 'atencion' | 'pocos' }
 */
export function resumenEnPalabras(puntos) {
  const valores = (puntos ?? []).map((p) => p.valor).filter((v) => v !== null && v !== undefined).map(Number);
  if (valores.length < 3) {
    return { texto: 'Todavía hay pocas calificaciones para saber hacia dónde va.', tono: 'pocos' };
  }
  const tramo = Math.max(1, Math.floor(valores.length / 3));
  const promedio = (lista) => lista.reduce((a, b) => a + b, 0) / lista.length;
  const diferencia = promedio(valores.slice(-tramo)) - promedio(valores.slice(0, tramo));
  const ultimo = valores[valores.length - 1];
  const previo = valores[valores.length - 2];
  const cayoAlFinal = previo - ultimo >= 2;
  const subioAlFinal = ultimo > previo;
  const variacion = Math.max(...valores) - Math.min(...valores);
  const detalle = ` Empezó el período en «${etiquetaDeValor(valores[0])}» y la última calificación fue «${etiquetaDeValor(ultimo)}».`;
  const calma = ' Es habitual que haya altibajos; el equipo lo sigue trabajando.';

  let texto;
  let tono;
  if (diferencia >= 0.5) {
    tono = 'bien';
    texto = cayoAlFinal ? 'Viene mejorando, aunque en la última sesión le costó más.' : 'Viene mejorando.';
  } else if (diferencia <= -0.5) {
    tono = 'atencion';
    texto = subioAlFinal
      ? `Está por debajo del comienzo del período, aunque en la última sesión mejoró.${calma}`
      : `En las últimas sesiones le costó más que al comienzo del período.${calma}`;
  } else if (cayoAlFinal) {
    tono = 'atencion';
    texto = `En la última sesión le costó más que en las anteriores.${calma}`;
  } else if (variacion >= 3) {
    tono = 'igual';
    texto = 'Varía bastante de una sesión a otra, sin una tendencia clara.';
  } else {
    tono = 'igual';
    texto = 'Se mantiene estable.';
  }
  return { texto: texto + detalle, tono };
}

/**
 * Registra una evolucion.
 *
 * Errores esperables, todos con el mensaje ya redactado por el servidor —
 * los tres primeros salen de los triggers y se muestran tal cual:
 * - 400 sesion en ausencia (regla 2)
 * - 400 objetivo de otro paciente (regla 3)
 * - 400 objetivo archivado (regla 4)
 * - 400 ya existe una evolucion para ese objetivo en esa sesion
 * - 409 el paciente no tiene objetivos activos
 * - 403 la sesion es de otro terapeuta
 */
export function registrarEvolucion({
  id_sesion: idSesion,
  id_objetivo: idObjetivo,
  valor,
  observaciones = null,
}) {
  return post('/evoluciones', {
    id_sesion: idSesion,
    id_objetivo: idObjetivo,
    valor,
    observaciones,
  });
}

/**
 * Corrige una calificación ya guardada. Solo quien atendió la sesión y con el
 * registro abierto (una sesión terminada se reabre primero).
 */
export function corregirEvolucion(idEvolucion, { valor, observaciones = null }) {
  return put(`/evoluciones/${idEvolucion}`, { valor, observaciones });
}

/** Quita una calificación: el objetivo vuelve a quedar sin calificar. */
export function quitarEvolucion(idEvolucion) {
  return del(`/evoluciones/${idEvolucion}`);
}

// Se borraron de aca:
//
//   listarEvolucionesDeSesion(idSesion)
//     Envolvia GET /api/evoluciones/sesion/<id>, que existe y funciona.
//     Pero obtenerSesion() ya trae las evoluciones embebidas, asi que el
//     cliente tenia dos formas de pedir lo mismo. El endpoint sigue
//     documentado en docs/ para quien lo necesite desde afuera.
//
//   valorEsValido(valor), VALOR_MINIMO, VALOR_MAXIMO
//     Validaban que la calificacion estuviera entre 1 y 5. La escala es de
//     botones: no puede producir un valor fuera de rango. Y el rango real
//     lo aplican el CHECK de la base y el procedimiento, que son la
//     autoridad. Mantener una tercera copia del limite era pedir que se
//     desincronizara.

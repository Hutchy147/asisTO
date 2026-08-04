// frontend/src/services/evolucionesService.js
// Contrato: docs/api-sesiones-evoluciones.md

import { post } from './api.js';

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

/** Palabra de la escala. `null` cuando todavía no se calificó. */
export function etiquetaDeValor(valor) {
  if (valor === null || valor === undefined) return null;
  return ESCALA_VALORES.find((paso) => paso.valor === Number(valor))?.etiqueta ?? null;
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

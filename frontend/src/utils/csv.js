// frontend/src/utils/csv.js
// Armado y descarga de un CSV, en el cliente. Sin dependencias.
//
// LAS DOS DECISIONES DE FORMATO, que no son gusto:
//
//   PUNTO Y COMA como separador. Excel en español lee el CSV con el
//   separador de lista del sistema, que en configuración regional es `;`.
//   Con coma, Excel mete la fila entera en la primera columna y el archivo
//   se ve roto aunque esté bien formado.
//
//   BOM UTF-8 al principio. Sin el BOM, Excel abre el archivo como ANSI y
//   los acentos salen mojibake: "Faltó" se lee "FaltÃ³". No alcanza con
//   guardar en UTF-8, hay que decírselo, y el BOM es la forma de decírselo
//   que Excel entiende sin preguntar nada.
//
// Las dos están VERIFICADAS abriendo el archivo, no deducidas.

const SEPARADOR = ';';
const BOM = '﻿';

// Fin de línea CRLF: es lo que dice el RFC 4180 y lo que Excel espera. Con
// LF solo, Excel igual lo abre, pero el Bloc de notas viejo de Windows
// muestra todo en un renglón.
const FIN_DE_LINEA = '\r\n';

/**
 * Un valor, listo para meter en una celda.
 *
 * SE EXPORTA AUNQUE HOY SOLO LA USE `armarCsv`, en este mismo archivo. Es la
 * pieza con más riesgo de las dos —el escapado— y la única que se puede
 * probar sola, sin DOM ni descarga. Exportarla es lo que permite que
 * auditoría le escriba un test sin tener que refactorizar nada primero. Si
 * se decide que no vale, se saca el `export` y no cambia ningún llamador.
 *
 * Se entrecomilla si trae el separador, comillas o un salto de línea, y las
 * comillas de adentro se duplican (que es como se escapan en CSV, no con
 * barra invertida).
 *
 * POR QUE IMPORTA: un apellido con coma —"Rivas, Ignacio (h)"— o un nombre
 * con comillas parte la fila en dos y corre todas las columnas siguientes.
 * No rompe una celda: rompe el archivo desde ahí para abajo.
 *
 * `null` y `undefined` van como celda vacía, no como el texto "null".
 *
 * LA COMA TAMBIEN DISPARA EL ENTRECOMILLADO, aunque con `;` de separador no
 * haga falta: una coma adentro de una celda no parte nada. Se entrecomilla
 * igual por dos motivos. Uno, "Apellido, Nombre" es la forma en que este
 * reporte escribe TODOS los nombres, así que es el caso normal y no el raro.
 * Dos, si alguna vez se cambia el separador a coma —o alguien abre el
 * archivo con un parser que asume coma— el archivo sigue siendo correcto en
 * vez de partirse en silencio. Cuesta dos comillas por celda.
 */
export function celda(valor) {
  if (valor === null || valor === undefined) return '';
  const texto = String(valor);
  if (/[;,"\r\n]/.test(texto)) {
    return `"${texto.replace(/"/g, '""')}"`;
  }
  return texto;
}

/**
 * Filas + columnas -> texto CSV con encabezados.
 *
 * `columnas` es [{ clave, etiqueta, valor? }]. `valor(fila)` permite derivar
 * una celda; sin él se usa `fila[clave]`.
 *
 * La lista de columnas es CERRADA y se pasa desde afuera: lo que no esté
 * nombrado ahí no sale al archivo, aunque venga en la fila. Es la misma
 * forma que COLUMNAS_REPORTE del backend y por el mismo motivo — el límite
 * de RRHH no se sostiene solo.
 */
export function armarCsv(filas, columnas) {
  const encabezado = columnas.map((c) => celda(c.etiqueta)).join(SEPARADOR);
  const cuerpo = filas.map((fila) => (
    columnas
      .map((c) => celda(c.valor ? c.valor(fila) : fila[c.clave]))
      .join(SEPARADOR)
  ));
  return [encabezado, ...cuerpo].join(FIN_DE_LINEA) + FIN_DE_LINEA;
}

/**
 * Dispara la descarga de un texto como archivo.
 *
 * El `revokeObjectURL` no es cosmético: sin él cada export deja el Blob
 * retenido en memoria hasta que se recarga la página.
 */
export function descargarCsv(nombreArchivo, contenido) {
  const blob = new Blob([BOM + contenido], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const enlace = document.createElement('a');
  enlace.href = url;
  enlace.download = nombreArchivo;
  document.body.appendChild(enlace);
  enlace.click();
  document.body.removeChild(enlace);
  URL.revokeObjectURL(url);
}

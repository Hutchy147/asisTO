// frontend/src/components/data/DataTable.jsx
// Tabla densa de la app.
//
// Las columnas se declaran como datos ({ clave, etiqueta, ancho, alinear,
// render }) en vez de escribir el <table> en cada pantalla: asi el alto de
// fila, el encabezado pegajoso y las cifras tabulares quedan iguales en
// todos lados sin depender de que alguien se acuerde.

import Box from '@mui/material/Box';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';

export default function DataTable({
  columnas,
  filas,
  claveFila = (fila) => fila.id,
  onAbrirFila,
  etiquetaFila,
  densidad = 'densa',
}) {
  const clickeable = Boolean(onAbrirFila);

  return (
    <Box
      sx={(t) => ({
        width: '100%',
        overflow: 'auto',
        backgroundColor: t.palette.superficie.tarjeta,
        border: `1px solid ${t.palette.superficie.borde}`,
        borderRadius: `${t.formas.md}px`,
      })}
    >
      <Table className="tabular" stickyHeader>
        <TableHead>
          <TableRow>
            {columnas.map((columna) => (
              <TableCell
                key={columna.clave}
                align={columna.alinear ?? 'left'}
                sx={{ width: columna.ancho, whiteSpace: 'nowrap' }}
              >
                {columna.etiqueta}
              </TableCell>
            ))}
          </TableRow>
        </TableHead>

        <TableBody>
          {filas.map((fila) => (
            <TableRow
              key={claveFila(fila)}
              hover={clickeable}
              onClick={clickeable ? () => onAbrirFila(fila) : undefined}
              // Una fila clickeable tiene que poder abrirse con el teclado,
              // no solo con el mouse.
              tabIndex={clickeable ? 0 : undefined}
              role={clickeable ? 'button' : undefined}
              aria-label={clickeable && etiquetaFila ? etiquetaFila(fila) : undefined}
              onKeyDown={
                clickeable
                  ? (evento) => {
                      if (evento.key === 'Enter' || evento.key === ' ') {
                        evento.preventDefault();
                        onAbrirFila(fila);
                      }
                    }
                  : undefined
              }
              sx={(t) => ({
                cursor: clickeable ? 'pointer' : 'default',
                '&:last-child td': { borderBottom: 0 },
                '&:focus-visible': { outline: 'none', boxShadow: `inset ${t.foco.anillo}` },
              })}
            >
              {columnas.map((columna) => {
                const contenido = columna.render ? columna.render(fila) : fila[columna.clave];
                return (
                  <TableCell
                    key={columna.clave}
                    align={columna.alinear ?? 'left'}
                    sx={{
                      height: densidad === 'comoda' ? 46 : 38,
                      borderBottom: (t) => `1px solid ${t.palette.superficie.borde}`,
                      // Un texto largo sin tope rompe el alto de fila densa
                      // y con el la lectura en columna de toda la tabla.
                      // Con `truncar` la celda se corta con puntos
                      // suspensivos y el texto completo queda en el title.
                      ...(columna.truncar
                        ? { maxWidth: columna.ancho ?? 280, overflow: 'hidden' }
                        : {}),
                    }}
                  >
                    {columna.truncar ? (
                      <Box
                        title={typeof contenido === 'string' ? contenido : undefined}
                        sx={{
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {contenido}
                      </Box>
                    ) : (
                      contenido
                    )}
                  </TableCell>
                );
              })}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Box>
  );
}

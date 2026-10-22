// frontend/src/components/informes/TextoInforme.jsx
// Lectura de un informe. El texto usa una convención mínima: "## Título" abre
// una sección, "- " un ítem de lista y una línea en blanco separa párrafos.
// Las marcas [COMPLETAR ...] se resaltan: son lo que falta resolver antes de
// poder publicar.

import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';

function ConMarcas({ texto }) {
  const partes = texto.split(/(\[COMPLETAR[^\]]*\])/gi);
  return partes.map((parte, i) => (/^\[COMPLETAR/i.test(parte) ? (
    <Box
      key={i}
      component="mark"
      sx={(t) => ({ backgroundColor: t.palette.warning.light, color: t.palette.warning.dark, px: 0.5, borderRadius: '3px' })}
    >
      {parte}
    </Box>
  ) : (
    <span key={i}>{parte}</span>
  )));
}

export default function TextoInforme({ contenido }) {
  const bloques = [];
  let parrafo = [];
  let items = [];
  const cerrarParrafo = () => {
    if (parrafo.length) bloques.push({ tipo: 'p', texto: parrafo.join('\n') });
    parrafo = [];
  };
  const cerrarLista = () => {
    if (items.length) bloques.push({ tipo: 'ul', items });
    items = [];
  };
  (contenido ?? '').replace(/\r\n/g, '\n').split('\n').forEach((linea) => {
    const l = linea.trim();
    if (l.startsWith('## ')) { cerrarParrafo(); cerrarLista(); bloques.push({ tipo: 'h', texto: l.slice(3).trim() }); }
    else if (/^[-*]\s+/.test(l)) { cerrarParrafo(); items.push(l.replace(/^[-*]\s+/, '')); }
    else if (l === '') { cerrarParrafo(); cerrarLista(); }
    else { cerrarLista(); parrafo.push(l); }
  });
  cerrarParrafo(); cerrarLista();

  return (
    <Box className="texto-libre">
      {bloques.map((b, i) => {
        if (b.tipo === 'h') {
          return <Typography key={i} variant="h5" sx={{ mt: i === 0 ? 0 : 2.5, mb: 0.75 }}>{b.texto}</Typography>;
        }
        if (b.tipo === 'ul') {
          return (
            <Box key={i} component="ul" sx={{ m: 0, mb: 1, pl: 3 }}>
              {b.items.map((it, j) => (
                <Typography key={j} component="li" variant="body1" sx={{ lineHeight: 1.6 }}><ConMarcas texto={it} /></Typography>
              ))}
            </Box>
          );
        }
        return (
          <Typography key={i} variant="body1" sx={{ lineHeight: 1.6, mb: 1, whiteSpace: 'pre-line' }}>
            <ConMarcas texto={b.texto} />
          </Typography>
        );
      })}
    </Box>
  );
}

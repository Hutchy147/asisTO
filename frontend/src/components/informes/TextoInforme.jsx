// frontend/src/components/informes/TextoInforme.jsx
// Lectura de un informe. El texto usa una convención mínima: "## Título" abre
// una sección, "- " un ítem de lista y una línea en blanco separa párrafos.
// Las marcas [COMPLETAR ...] se resaltan: son lo que falta resolver antes de
// poder publicar.
//
// El texto sigue siendo texto (es lo que se edita y lo que viaja al PDF), pero
// acá se lee con presentación: ficha del paciente arriba, asistencia en
// tarjetas, cada objetivo con su nivel en una etiqueta y las observaciones con
// su fecha. Si una sección no tiene la forma esperada (alguien la reescribió
// a mano), se muestra como texto común: nunca se pierde contenido.
//
// Las cinco palabras de la escala llevan TODAS el mismo color: no es una nota
// y "No logrado" no puede verse peor que "Logrado".

import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';

const NIVELES = 'No logrado|Inicial|En proceso|Avanzado|Logrado';
const RE_OBJETIVO = new RegExp(`^(.*?): (${NIVELES}) \\(calificado en (una sesión|\\d+ sesi(?:ón|ones))\\)(?:; (.*?))?\\.?$`);
const RE_SIN_CALIFICAR = /^(.*?): no se calificó en el período\.?$/;
const RE_OBSERVACION = /^(\d{2}\/\d{2}): (.*)$/;

function normalizar(texto) {
  return texto.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();
}

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

/** Parte el texto en secciones [{ titulo, bloques: [{tipo:'p'|'ul', ...}] }]. */
function leerSecciones(contenido) {
  const secciones = [];
  let actual = null;
  let parrafo = [];
  let items = [];
  const abrir = (titulo) => {
    actual = { titulo, bloques: [] };
    secciones.push(actual);
  };
  const cerrarParrafo = () => {
    if (parrafo.length) { if (!actual) abrir(null); actual.bloques.push({ tipo: 'p', texto: parrafo.join('\n') }); }
    parrafo = [];
  };
  const cerrarLista = () => {
    if (items.length) { if (!actual) abrir(null); actual.bloques.push({ tipo: 'ul', items }); }
    items = [];
  };
  (contenido ?? '').replace(/\r\n/g, '\n').split('\n').forEach((linea) => {
    const l = linea.trim();
    if (l.startsWith('## ')) { cerrarParrafo(); cerrarLista(); abrir(l.slice(3).trim()); }
    else if (/^[-*]\s+/.test(l)) { cerrarParrafo(); items.push(l.replace(/^[-*]\s+/, '')); }
    else if (l === '') { cerrarParrafo(); cerrarLista(); }
    else { cerrarLista(); parrafo.push(l); }
  });
  cerrarParrafo(); cerrarLista();
  return secciones;
}

const estiloParrafo = { lineHeight: 1.7, mb: 1.25, whiteSpace: 'pre-line', maxWidth: '72ch' };

function Parrafo({ texto }) {
  return (
    <Typography variant="body1" sx={estiloParrafo}><ConMarcas texto={texto} /></Typography>
  );
}

function Lista({ items }) {
  return (
    <Box component="ul" sx={{ m: 0, mb: 1.5, pl: 3, maxWidth: '72ch' }}>
      {items.map((it, j) => (
        <Typography key={j} component="li" variant="body1" sx={{ lineHeight: 1.7, mb: 0.5 }}><ConMarcas texto={it} /></Typography>
      ))}
    </Box>
  );
}

function Bloques({ bloques }) {
  return bloques.map((b, i) => (b.tipo === 'p' ? <Parrafo key={i} texto={b.texto} /> : <Lista key={i} items={b.items} />));
}

function TituloSeccion({ texto, primero }) {
  return (
    <Box
      sx={(t) => ({
        display: 'flex', alignItems: 'center', gap: 1.25,
        mt: primero ? 0 : 3.5, mb: 1.5, pt: primero ? 0 : 2.5,
        borderTop: primero ? 0 : `1px solid ${t.palette.superficie.borde}`,
      })}
    >
      <Box component="span" aria-hidden sx={{ width: 4, height: 20, borderRadius: 2, backgroundColor: 'primary.main', flex: 'none' }} />
      <Typography variant="h5" component="h3" sx={{ lineHeight: 1.3 }}>{texto}</Typography>
    </Box>
  );
}

/** Paciente y período, juntos arriba, como una ficha. */
function Ficha({ datos }) {
  return (
    <Box
      sx={(t) => ({
        display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1.4fr 1fr' }, gap: 2,
        p: 2, mb: 3, backgroundColor: t.palette.superficie.hundida,
        border: `1px solid ${t.palette.superficie.borde}`, borderRadius: `${t.formas.md}px`,
      })}
    >
      {datos.map((d) => (
        <Box key={d.etiqueta} sx={{ minWidth: 0 }}>
          <Typography variant="overline" color="text.secondary" sx={{ display: 'block', lineHeight: 1.6 }}>{d.etiqueta}</Typography>
          <Typography variant="body1" className="texto-libre" sx={{ fontWeight: 500, lineHeight: 1.5 }}>{d.valor}</Typography>
        </Box>
      ))}
    </Box>
  );
}

function Tarjetas({ sesiones, ausencias, frase }) {
  const tarjetas = [{ etiqueta: sesiones === 1 ? 'Sesión a la que asistió' : 'Sesiones a las que asistió', valor: sesiones }];
  if (ausencias !== null) tarjetas.push({ etiqueta: ausencias === 1 ? 'Ausencia' : 'Ausencias', valor: ausencias });
  return (
    <Box role="group" aria-label={frase} sx={{ display: 'flex', gap: 1.5, flexWrap: 'wrap', mb: 1.5 }}>
      {tarjetas.map((c) => (
        <Box
          key={c.etiqueta}
          sx={(t) => ({
            minWidth: 150, px: 2, py: 1.25, backgroundColor: t.palette.superficie.tarjeta,
            border: `1px solid ${t.palette.superficie.borde}`, borderRadius: `${t.formas.md}px`,
          })}
        >
          <Typography className="tabular" sx={{ fontSize: 26, fontWeight: 600, lineHeight: 1.1, color: 'primary.dark' }}>{c.valor}</Typography>
          <Typography variant="body2" color="text.secondary">{c.etiqueta}</Typography>
        </Box>
      ))}
    </Box>
  );
}

function Asistencia({ bloques }) {
  const [primero, ...resto] = bloques;
  const frase = primero?.tipo === 'p' ? primero.texto : '';
  // Dos redacciones: la del generador («asistió a 4 sesiones y faltó a 1») y la
  // de los informes ya cargados («4 sesiones realizadas y 1 ausencia»).
  const cuenta = (...patrones) => {
    for (const patron of patrones) {
      const m = patron.exec(frase);
      if (m) return Number(m[1]);
    }
    return null;
  };
  const asistio = cuenta(/asisti[óo] a (\d+) sesi/, /(\d+) sesi[óo]n(?:es)? realizad/);
  const falto = cuenta(/falt[óo] a (\d+)/, /(\d+) ausencias?/);
  if (asistio === null && falto === null) return <Bloques bloques={bloques} />;
  return (
    <>
      <Tarjetas sesiones={asistio ?? 0} ausencias={falto} frase={frase} />
      <Bloques bloques={resto} />
    </>
  );
}

function EtiquetaNivel({ texto }) {
  return (
    <Box
      component="span"
      sx={(t) => ({
        display: 'inline-block', px: 1.25, py: 0.25, borderRadius: `${t.formas.pill}px`, fontSize: 13, fontWeight: 600,
        whiteSpace: 'nowrap', backgroundColor: t.palette.superficie.acentoSuave, color: 'primary.dark',
        border: `1px solid ${t.palette.primary.light}`,
      })}
    >
      {texto}
    </Box>
  );
}

function FilaObjetivo({ objetivo, nivel, detalle }) {
  return (
    <Box
      sx={(t) => ({
        display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 2,
        py: 1.25, borderBottom: `1px solid ${t.palette.superficie.borde}`, '&:last-of-type': { borderBottom: 0 },
      })}
    >
      <Box sx={{ minWidth: 0 }}>
        <Typography variant="body1" className="texto-libre" sx={{ fontWeight: 500, lineHeight: 1.45 }}>{objetivo}</Typography>
        {detalle && <Typography variant="body2" color="text.secondary" sx={{ mt: 0.25 }}>{detalle}</Typography>}
      </Box>
      <EtiquetaNivel texto={nivel} />
    </Box>
  );
}

function Objetivos({ bloques }) {
  return bloques.map((b, i) => {
    if (b.tipo === 'p') {
      return <Typography key={i} variant="body2" color="text.secondary" sx={{ mb: 1.25, whiteSpace: 'pre-line', maxWidth: '72ch' }}><ConMarcas texto={b.texto} /></Typography>;
    }
    const filas = b.items.map((it) => {
      const o = RE_OBJETIVO.exec(it);
      if (o) {
        const extras = [`Calificado en ${o[3]}`, o[4]].filter(Boolean).join(' · ');
        return { objetivo: o[1], nivel: o[2], detalle: extras.charAt(0).toUpperCase() + extras.slice(1) };
      }
      const s = RE_SIN_CALIFICAR.exec(it);
      if (s) return { objetivo: s[1], nivel: 'Sin calificar', detalle: 'No se calificó en el período' };
      return null;
    });
    if (filas.some((f) => f === null)) return <Lista key={i} items={b.items} />;
    return (
      <Box
        key={i}
        sx={(t) => ({
          px: 2, mb: 1.5, backgroundColor: t.palette.superficie.tarjeta,
          border: `1px solid ${t.palette.superficie.borde}`, borderRadius: `${t.formas.md}px`,
        })}
      >
        {filas.map((f, j) => <FilaObjetivo key={j} {...f} />)}
      </Box>
    );
  });
}

function Observaciones({ bloques }) {
  return bloques.map((b, i) => {
    if (b.tipo === 'p') return <Parrafo key={i} texto={b.texto} />;
    const filas = b.items.map((it) => RE_OBSERVACION.exec(it));
    if (filas.some((f) => f === null)) return <Lista key={i} items={b.items} />;
    return (
      <Box key={i} sx={{ mb: 1.5, maxWidth: '72ch' }}>
        {filas.map((f, j) => (
          <Box key={j} sx={{ display: 'flex', gap: 1.5, py: 0.75 }}>
            <Typography className="tabular" variant="body2" sx={{ flex: 'none', width: 48, fontWeight: 600, color: 'primary.dark', pt: '2px' }}>{f[1]}</Typography>
            <Typography variant="body1" sx={{ lineHeight: 1.6 }}><ConMarcas texto={f[2]} /></Typography>
          </Box>
        ))}
      </Box>
    );
  });
}

export default function TextoInforme({ contenido }) {
  const secciones = leerSecciones(contenido);
  const ficha = [];
  const cuerpo = [];
  secciones.forEach((s) => {
    const clave = s.titulo ? normalizar(s.titulo) : '';
    const unico = s.bloques.length === 1 && s.bloques[0].tipo === 'p' ? s.bloques[0].texto : null;
    if (clave === 'datos del paciente' && unico) ficha.push({ etiqueta: 'Paciente', valor: unico });
    else if (clave === 'periodo' && unico) ficha.push({ etiqueta: 'Período', valor: unico });
    else cuerpo.push(s);
  });

  return (
    <Box className="texto-libre">
      {ficha.length > 0 && <Ficha datos={ficha} />}
      {cuerpo.map((s, i) => {
        const clave = s.titulo ? normalizar(s.titulo) : '';
        let interior;
        if (clave === 'asistencia') interior = <Asistencia bloques={s.bloques} />;
        else if (clave.startsWith('objetivos')) interior = <Objetivos bloques={s.bloques} />;
        else if (clave.startsWith('observaciones')) interior = <Observaciones bloques={s.bloques} />;
        else interior = <Bloques bloques={s.bloques} />;
        return (
          <Box key={i} component="section">
            {s.titulo && <TituloSeccion texto={s.titulo} primero={i === 0} />}
            {interior}
          </Box>
        );
      })}
    </Box>
  );
}

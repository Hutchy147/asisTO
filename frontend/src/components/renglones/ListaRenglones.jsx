// frontend/src/components/renglones/ListaRenglones.jsx
// Lista de renglones cortos (notas de campo). Cada renglón es una fila con su
// marca de destacado; el plan además se cierra como hecho o descartado.
// Escritura telegráfica: el campo de alta es de una línea, no un textarea.

import { useState } from 'react';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';

import { MAXIMO_CARACTERES_RENGLON } from '../../services/renglonesService.js';

/** Estrella de destacado: botón con estado, no un color libre. */
function Marca({ activa, onClick, deshabilitada }) {
  return (
    <Box
      component="button"
      type="button"
      aria-pressed={activa}
      aria-label={activa ? 'Quitar destacado' : 'Destacar renglón'}
      title={activa ? 'Quitar destacado' : 'Destacar'}
      disabled={deshabilitada}
      onClick={onClick}
      sx={(t) => ({
        flex: 'none', width: 28, height: 28, border: 0, borderRadius: '6px',
        background: activa ? t.palette.feedback.advertencia.bg : 'transparent',
        color: activa ? t.palette.text.primary : t.palette.text.disabled,
        fontSize: 16, lineHeight: 1, cursor: deshabilitada ? 'default' : 'pointer',
        '&:hover:not(:disabled)': { backgroundColor: t.palette.superficie.hundida },
        '&:focus-visible': { outline: 'none', boxShadow: t.foco.anillo },
      })}
    >
      {activa ? '★' : '☆'}
    </Box>
  );
}

function BotonChico({ children, onClick, deshabilitado, etiqueta }) {
  return (
    <Button
      size="small" variant="text" disabled={deshabilitado} onClick={onClick} aria-label={etiqueta}
      sx={{ minWidth: 0, px: 0.75, py: 0, fontSize: 12, fontWeight: 600, whiteSpace: 'nowrap' }}
    >
      {children}
    </Button>
  );
}

export default function ListaRenglones({
  renglones = [],
  editable = false,
  conCierre = false,        // el plan se cierra (hecho / descartado)
  etiquetaVacio = 'Todavía no hay renglones.',
  ocupado = false,
  onDestacar,               // (renglon) => Promise
  onBorrar,                 // (renglon) => Promise
  onCerrar,                 // (renglon, cierre) => Promise
  onEditar,                 // (renglon, texto) => Promise (T4.1)
  alPie,                    // nodo opcional (el campo de alta)
}) {
  // Edición en el lugar: un renglón por vez. Enter guarda, Escape cancela.
  const [editando, setEditando] = useState(null); // null | { id, texto, error }
  const [guardando, setGuardando] = useState(false);

  async function guardarEdicion(r) {
    const limpio = (editando?.texto ?? '').trim();
    if (!limpio) { setEditando((e) => ({ ...e, error: 'El renglón no puede quedar vacío.' })); return; }
    if (limpio === r.texto) { setEditando(null); return; }
    setGuardando(true);
    try {
      await onEditar(r, limpio);
      setEditando(null);
    } catch (fallo) {
      setEditando((e) => ({ ...e, error: fallo?.message || 'No se pudo guardar el cambio.' }));
    } finally {
      setGuardando(false);
    }
  }

  return (
    <Box>
      {renglones.length === 0 ? (
        <Typography variant="body2" color="text.secondary" sx={{ fontStyle: 'italic', py: 0.5 }}>
          {etiquetaVacio}
        </Typography>
      ) : (
        <Box component="ul" sx={{ listStyle: 'none', m: 0, p: 0 }}>
          {renglones.map((r) => {
            const resuelto = Boolean(r.cierre);
            return (
              <Box
                component="li"
                key={r.id}
                sx={(t) => ({
                  display: 'flex', alignItems: 'center', gap: 0.75, py: 0.4,
                  borderBottom: `1px solid ${t.palette.superficie.hundida}`,
                })}
              >
                <Marca
                  activa={r.destacado}
                  deshabilitada={!editable || ocupado}
                  onClick={() => onDestacar?.(r)}
                />
                {editando?.id === r.id ? (
                  <Box sx={{ flex: 1, minWidth: 0, display: 'flex', alignItems: 'flex-start', gap: 0.75 }}>
                    <TextField
                      size="small" fullWidth autoFocus value={editando.texto}
                      disabled={guardando}
                      onChange={(e) => setEditando({ id: r.id, texto: e.target.value, error: '' })}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') { e.preventDefault(); guardarEdicion(r); }
                        if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); setEditando(null); }
                      }}
                      inputProps={{ maxLength: MAXIMO_CARACTERES_RENGLON, 'aria-label': `Editar el renglón ${r.texto}` }}
                      error={Boolean(editando.error)}
                      helperText={editando.error || 'Enter guarda; Escape cancela.'}
                    />
                    <BotonChico deshabilitado={guardando} onClick={() => guardarEdicion(r)} etiqueta="Guardar el cambio">
                      Guardar
                    </BotonChico>
                    <BotonChico deshabilitado={guardando} onClick={() => setEditando(null)} etiqueta="Cancelar la edición">
                      Cancelar
                    </BotonChico>
                  </Box>
                ) : (
                <Box
                  className="texto-libre"
                  sx={(t) => ({
                    flex: 1, minWidth: 0, fontSize: 14, lineHeight: 1.35,
                    fontWeight: r.destacado ? 600 : 400,
                    color: resuelto ? t.palette.text.disabled : t.palette.text.primary,
                    textDecoration: r.cierre === 'hecho' ? 'line-through' : 'none',
                    fontStyle: r.cierre === 'descartado' ? 'italic' : 'normal',
                  })}
                >
                  {r.texto}
                  {r.fecha_sesion && (
                    <Box component="span" className="tabular" sx={{ ml: 1, fontSize: 11, color: 'text.secondary', fontWeight: 400 }}>
                      del {r.fecha_sesion.slice(8)}/{r.fecha_sesion.slice(5, 7)}
                    </Box>
                  )}
                  {r.cierre === 'descartado' && (
                    <Box component="span" sx={{ ml: 1, fontSize: 11 }}>descartado</Box>
                  )}
                </Box>
                )}
                {editable && onEditar && !resuelto && editando?.id !== r.id && (
                  <BotonChico deshabilitado={ocupado} onClick={() => setEditando({ id: r.id, texto: r.texto, error: '' })} etiqueta={`Editar el renglón ${r.texto}`}>
                    Editar
                  </BotonChico>
                )}
                {editable && conCierre && editando?.id !== r.id && (
                  resuelto ? (
                    <BotonChico deshabilitado={ocupado} onClick={() => onCerrar?.(r, null)} etiqueta="Reabrir renglón">
                      Reabrir
                    </BotonChico>
                  ) : (
                    <>
                      <BotonChico deshabilitado={ocupado} onClick={() => onCerrar?.(r, 'hecho')} etiqueta="Marcar como hecho">
                        Hecho
                      </BotonChico>
                      <BotonChico deshabilitado={ocupado} onClick={() => onCerrar?.(r, 'descartado')} etiqueta="Descartar renglón">
                        Descartar
                      </BotonChico>
                    </>
                  )
                )}
                {editable && onBorrar && editando?.id !== r.id && (
                  <BotonChico deshabilitado={ocupado} onClick={() => onBorrar(r)} etiqueta={`Borrar el renglón ${r.texto}`}>
                    Borrar
                  </BotonChico>
                )}
              </Box>
            );
          })}
        </Box>
      )}
      {alPie}
    </Box>
  );
}

/**
 * Campo de alta de un renglón: una línea, Enter agrega. El tope de 160 se
 * dice con un contador, y el servidor lo vuelve a validar.
 */
export function CampoRenglon({ placeholder, onAgregar, deshabilitado = false }) {
  const [texto, setTexto] = useState('');
  const [destacado, setDestacado] = useState(false);
  const [error, setError] = useState('');
  const [enviando, setEnviando] = useState(false);

  async function agregar() {
    const limpio = texto.trim();
    if (!limpio || enviando) return;
    setError('');
    setEnviando(true);
    try {
      await onAgregar(limpio, destacado);
      setTexto('');
      setDestacado(false);
    } catch (fallo) {
      setError(fallo.message || 'No se pudo guardar el renglón.');
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Box sx={{ pt: 1 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
        <Marca activa={destacado} onClick={() => setDestacado((d) => !d)} deshabilitada={deshabilitado || enviando} />
        <TextField
          size="small" fullWidth value={texto} placeholder={placeholder}
          disabled={deshabilitado || enviando}
          onChange={(e) => setTexto(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); agregar(); } }}
          inputProps={{ maxLength: MAXIMO_CARACTERES_RENGLON, 'aria-label': placeholder }}
          error={Boolean(error)}
        />
        <Button variant="outlined" size="small" onClick={agregar} disabled={deshabilitado || enviando || !texto.trim()}>
          Agregar
        </Button>
      </Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 0.25, pl: 4.5 }}>
        <Typography variant="caption" color={error ? 'error' : 'text.secondary'}>
          {error || 'Frases cortas. Enter agrega; la estrella lo destaca.'}
        </Typography>
        {texto.length > 120 && (
          <Typography variant="caption" className="tabular" color="text.secondary">
            {texto.length}/{MAXIMO_CARACTERES_RENGLON}
          </Typography>
        )}
      </Box>
    </Box>
  );
}

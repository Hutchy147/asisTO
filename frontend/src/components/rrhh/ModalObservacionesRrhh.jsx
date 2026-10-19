// frontend/src/components/rrhh/ModalObservacionesRrhh.jsx
//
// Observaciones TECNICAS de RRHH sobre una sesión. Leer y agregar.
//
// EL PUNTO DELICADO DE ESTA PANTALLA NO ES EL FORMULARIO, ES QUE NO SE
// CONFUNDA CON UNA NOTA CLINICA. Una observación administrativa y una nota
// del terapeuta hablan del mismo hecho y se parecen mucho escritas: "llegó
// tarde" lo puede haber escrito cualquiera de los dos. Si aparecen juntas y
// sin distinguirse, un terapeuta va a leer la de RRHH como propia.
//
// Por eso, y en este orden de importancia:
//
//   1. Cada observación va FIRMADA con nombre y legajo de quien la escribió,
//      no sólo con la fecha.
//   2. El encabezado dice qué son y qué NO son, con todas las letras.
//   3. No se muestran junto a `sesiones.notas`: esta pantalla es de RRHH y
//      las notas del terapeuta no llegan acá — el endpoint no las devuelve.
//
// NO HAY EDITAR NI BORRAR, y es una decisión: una observación es la
// constancia de algo que pasó. Corregirla después es reescribir el registro.
// Si hace falta rectificar, se agrega otra.

import { useState } from 'react';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';

import { Aviso, Cargando, EstadoError, EstadoVacio } from '../estado/index.js';
import { usePeticion } from '../../hooks/usePeticion.js';
import { listarObservaciones, registrarObservacion } from '../../services/rrhhService.js';
import { formatearFecha } from '../../utils/fechas.js';

// Mismo tope que el backend (`MAXIMO_CARACTERES_TEXTO` en el modelo). Está
// acá para poder mostrar el contador antes de mandar; el que manda es el del
// servidor, que rechaza igual si este se queda viejo.
const MAXIMO_CARACTERES = 1000;

function fechaYHora(iso) {
  if (!iso) return '';
  const [fecha, hora] = iso.split('T');
  return `${formatearFecha(fecha)} · ${(hora ?? '').slice(0, 5)}`;
}

export default function ModalObservacionesRrhh({ sesion, abierto, onCerrar, onGuardado }) {
  const [texto, setTexto] = useState('');
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState(null);

  const idSesion = sesion?.id_sesion;
  const datos = usePeticion(
    () => (idSesion ? listarObservaciones(idSesion) : Promise.resolve(null)),
    [idSesion]
  );

  const observaciones = datos.datos?.observaciones ?? [];
  const limpio = texto.trim();

  async function guardar() {
    setGuardando(true);
    setError(null);
    try {
      await registrarObservacion(idSesion, limpio);
      setTexto('');
      const recargado = await datos.recargar();
      // Se le pasa el TOTAL a la pantalla de atrás para que corrija el
      // conteo de esa fila. No se le pide que recargue el período entero:
      // con 630 sesiones eso deja la pantalla en blanco, medido en Chrome.
      onGuardado?.(recargado?.total ?? 0);
    } catch (fallo) {
      setError(fallo);
    } finally {
      setGuardando(false);
    }
  }

  return (
    <Dialog open={Boolean(abierto)} onClose={onCerrar} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ pb: 0.5 }}>
        Observaciones técnicas
        {sesion && (
          <Typography variant="body2" color="text.secondary" className="texto-libre">
            {`${sesion.paciente} · ${formatearFecha(sesion.fecha)} · ${sesion.hora_inicio ?? ''}`}
            {` · atendió ${sesion.terapeuta}`}
          </Typography>
        )}
      </DialogTitle>

      <DialogContent>
        {/* El aviso va ARRIBA de todo y no al pie: tiene que leerse antes
            que las observaciones, no después de haberlas confundido. */}
        <Aviso severidad="info" titulo="Esto no es una nota clínica">
          Son observaciones <strong>administrativas</strong> de RRHH sobre cómo
          transcurrió la sesión — llegadas tarde, material faltante, avisos.
          No reemplazan ni modifican las notas del terapeuta, que son otra
          cosa y viven en otro lado.
        </Aviso>

        <Typography variant="subtitle2" sx={{ mt: 2, mb: 1, fontWeight: 600 }}>
          Registradas ({observaciones.length})
        </Typography>

        {datos.cargando && <Cargando texto="Buscando las observaciones..." minHeight={100} />}
        {datos.error && <EstadoError error={datos.error} onReintentar={datos.recargar} />}

        {!datos.cargando && !datos.error && (
          observaciones.length === 0 ? (
            <EstadoVacio
              plano
              titulo="Todavía no hay observaciones"
              descripcion="Si pasó algo que valga dejar asentado, escribilo abajo."
            />
          ) : (
            <Stack spacing={1.5}>
              {observaciones.map((o) => (
                <Box
                  key={o.id}
                  sx={(t) => ({
                    p: 1.5,
                    backgroundColor: t.palette.superficie.tarjeta,
                    border: `1px solid ${t.palette.superficie.borde}`,
                    borderRadius: `${t.formas.md}px`,
                  })}
                >
                  {/* La FIRMA va primero. Una observación sin autor visible es
                      exactamente la que se lee como nota de la casa. */}
                  <Typography variant="caption" sx={{ fontWeight: 600 }} className="texto-libre">
                    {o.autor?.nombre_completo ?? 'RRHH'}
                    {o.autor?.nro_legajo ? ` · ${o.autor.nro_legajo}` : ''}
                  </Typography>
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                    {fechaYHora(o.fecha_registro)}
                  </Typography>
                  <Typography variant="body2" sx={{ mt: 0.5 }} className="texto-libre">
                    {o.texto}
                  </Typography>
                </Box>
              ))}
            </Stack>
          )
        )}

        <Typography variant="subtitle2" sx={{ mt: 2.5, mb: 1, fontWeight: 600 }}>
          Agregar una
        </Typography>
        <TextField
          multiline
          minRows={3}
          fullWidth
          placeholder="Qué pasó, en una o dos líneas."
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          disabled={guardando}
          inputProps={{ maxLength: MAXIMO_CARACTERES }}
          helperText={`${texto.length} / ${MAXIMO_CARACTERES}. Queda firmada con su nombre y no se puede editar después.`}
          error={Boolean(error)}
        />
        {error && (
          <Typography variant="caption" color="error">{error.message}</Typography>
        )}
      </DialogContent>

      <DialogActions>
        <Button onClick={onCerrar} disabled={guardando}>Cerrar</Button>
        <Button
          variant="contained"
          onClick={guardar}
          disabled={guardando || limpio.length === 0}
        >
          {guardando ? 'Guardando…' : 'Registrar observación'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

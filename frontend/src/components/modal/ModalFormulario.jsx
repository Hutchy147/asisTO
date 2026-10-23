// frontend/src/components/modal/ModalFormulario.jsx
//
// Marco de los cuatro modales de formulario del sistema. Lo que define acá
// se aplica a alta de paciente, objetivo, sesión y evolución por igual.
//
// Se usa junto con useFormularioModal, que aporta el estado.

import { useEffect, useRef, useState } from 'react';
import Alert from '@mui/material/Alert';
import AlertTitle from '@mui/material/AlertTitle';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import Typography from '@mui/material/Typography';
import useMediaQuery from '@mui/material/useMediaQuery';

/**
 * DOS PANELES — cuándo, y de dónde salen los números.
 *
 * Un modal con `panelLateral` reparte el contenido en dos columnas: el
 * formulario a la izquierda con su propio scroll, y el panel lateral a la
 * derecha, fijo. Sirve para el caso del modal de evolución, donde la lista de
 * objetivos puede medir cualquier cosa y los controles obligatorios no pueden
 * irse con ella.
 *
 * PISO_PANEL_LATERAL = 470. Medido: la escala de logro son cinco botones con
 * white-space: nowrap, mide 432 px en una fila y NO se comprime. Debajo de
 * 470 px de panel se parte en dos filas. Ese es el piso duro.
 *
 * ANCHO_MINIMO_DOS_PANELES = 948. Con 470 a la derecha, 24 de separación y 48
 * de padding, el panel izquierdo se queda con 418 px si el modal mide 960.
 * Medido a 880 de modal el panel cae a 340 y un objetivo en formato real pasa
 * a NUEVE líneas: una columna de palabras. Así que el corte está en 900 px de
 * modal, y como el paper lleva maxWidth 95vw, eso pide 948 px de viewport.
 *
 * Los dos escenarios reales de la defensa quedan del lado ancho: 1366x768 al
 * 100 % da 1366 de viewport, y con escalado al 125 % da 1093. Los dos entran.
 *
 * ABAJO DE 948: una sola columna, con el orden y el comportamiento de siempre.
 * Ahí la escala puede quedar bajo el pliegue, y lo que la vuelve alcanzable es
 * el scroll al primer campo inválido de más abajo.
 *
 * MEJORA CONOCIDA, no implementada a propósito: en una columna se le podría
 * poner `position: sticky; bottom: 0` al panel lateral para que la escala
 * quede visible siempre. Se descartó porque resuelve un caso que los dos
 * escenarios reales no tienen, agrega un segundo comportamiento de layout, y
 * donde el ancho es escaso el alto también lo es — la escala y las
 * observaciones fijas arriba del pie dejarían muy poca lista scrolleable. Si
 * alguna vez aparece un requisito de pantallas angostas, esta es la mejora, y
 * este párrafo existe para no tener que redescubrirla. Ver ESTADO.md.
 */
export const PISO_PANEL_LATERAL = 470;
export const ANCHO_MINIMO_DOS_PANELES = 948;
export const ANCHO_DOS_PANELES = 960;

/**
 * Qué se considera "lo primero que está mal" dentro del formulario.
 *
 * Dos fuentes, y las dos hacen falta:
 *
 *   .Mui-error            lo pone MUI en el TextField cuando recibe `error`.
 *                         Cubre por completo tres de los cuatro modales, que
 *                         son solo CampoTexto.
 *   [data-campo-invalido] marca explícita para los controles que dibujan su
 *                         propio error y MUI no toca: la escala de logro y el
 *                         grupo de objetivos del modal de evolución.
 *
 * Gana el primero en orden del documento, que es el que está más arriba en el
 * formulario. El Alert del rechazo del servidor también lleva la marca y es
 * el primer hijo del contenido, así que cuando aparece gana él — que es lo
 * correcto: ese error es del envío entero, no de un campo.
 */
const SELECTOR_INVALIDO = '[data-campo-invalido], .Mui-error';

// Aire sobre el campo al que se scrollea, para que no quede pegado al borde.
const MARGEN_SCROLL = 24;

export default function ModalFormulario({
  abierto,
  titulo,
  subtitulo,
  ancho = 560,
  guardando,
  errorServidor,
  tituloRechazo = 'El servidor rechazó los datos',
  confirmandoDescarte,
  onPedirCierre,
  onSeguirEditando,
  onDescartar,
  onEnviar,
  etiquetaEnviar,
  etiquetaGuardando,
  enviarDeshabilitado = false,
  // El modal no puede guardar nada: el pie se reduce a cerrar. Se usa
  // cuando lo que falta no se resuelve desde acá (un paciente sin
  // objetivos activos, una sesión de otro terapeuta). Ofrecer "Guardar"
  // sería ofrecer algo imposible.
  soloCerrar = false,
  // Con soloCerrar: una acción principal al pie, a la izquierda de Cerrar (el
  // registro del día pone ahí «Terminar la sesión»).
  accionPie = null,
  // Contenido que NO se va con el scroll del formulario. Si viene y la
  // pantalla da el ancho, el modal se abre a dos paneles. Si no viene, o la
  // pantalla es angosta, se apila abajo de `children` como hasta ahora.
  panelLateral,
  children,
}) {
  const contenidoRef = useRef(null);
  const panelIzquierdoRef = useRef(null);

  const cabeEnDosPaneles = useMediaQuery(`(min-width:${ANCHO_MINIMO_DOS_PANELES}px)`);
  const dosPaneles = Boolean(panelLateral) && cabeEnDosPaneles;
  const anchoEfectivo = dosPaneles ? ANCHO_DOS_PANELES : ancho;
  // Cuenta de intentos de envío. No interesa el número: interesa que cambie,
  // para que el efecto corra DESPUÉS del render que dibujó los errores.
  const [intentos, setIntentos] = useState(0);

  /**
   * Lleva el formulario al primer campo inválido después de un envío fallido.
   *
   * El motivo está medido y no es cosmético. Con cuatro objetivos en formato
   * real, el modal de evolución necesita 807 px de contenido y en 1366x768
   * hay 423 visibles: la escala de logro —que es obligatoria— y su mensaje de
   * error quedan bajo el pliegue. Sin esto la terapeuta apretaba "Guardar
   * evolución", el formulario se rechazaba, y NO PASABA NADA VISIBLE: el
   * error se dibujaba 83 px más abajo y el modal no se movía.
   *
   * Se mueve `scrollTop` a mano en vez de usar `scrollIntoView`, que scrollea
   * el ancestro scrolleable más cercano y puede arrastrar la página de atrás.
   * Acá el único que se mueve es el contenido del modal.
   */
  useEffect(() => {
    if (intentos === 0) return;

    const contenido = contenidoRef.current;
    if (!contenido) return;

    const objetivo = contenido.querySelector(SELECTOR_INVALIDO);
    if (!objetivo) return; // no hay nada mal: el envío salió bien

    // Cuál es el contenedor que scrollea NO es fijo: con un panel lo hace el
    // DialogContent, con dos paneles lo hace el panel izquierdo. Se busca el
    // primer ancestro que scrollee de verdad en vez de asumir cuál es, así el
    // scroll al error sigue funcionando en los dos layouts.
    let scroller = objetivo.parentElement;
    while (scroller && scroller !== contenido.parentElement) {
      const desborda = scroller.scrollHeight > scroller.clientHeight + 1;
      const overflowY = getComputedStyle(scroller).overflowY;
      if (desborda && (overflowY === 'auto' || overflowY === 'scroll')) break;
      scroller = scroller.parentElement;
    }
    if (!scroller || scroller === contenido.parentElement) return; // nada scrollea

    const cajaContenido = scroller.getBoundingClientRect();
    const cajaObjetivo = objetivo.getBoundingClientRect();

    const recortadoArriba = cajaObjetivo.top < cajaContenido.top;
    const recortadoAbajo = cajaObjetivo.bottom > cajaContenido.bottom;

    // Si ya se ve entero no se toca nada: mover la vista cuando el campo está
    // a la vista es un salto sin motivo.
    if (!recortadoArriba && !recortadoAbajo) return;

    // Se mueve lo MÍNIMO necesario para que entre, en vez de llevarlo siempre
    // al borde de arriba. Con el campo apenas cortado, alinearlo arriba
    // empujaba fuera de la vista todo el contexto anterior.
    let delta;
    if (recortadoArriba) {
      delta = cajaObjetivo.top - cajaContenido.top - MARGEN_SCROLL;
    } else {
      delta = cajaObjetivo.bottom - cajaContenido.bottom + MARGEN_SCROLL;
      // Si el campo es más alto que el área visible, que al menos se vea su
      // arranque: bajar hasta su borde inferior dejaría el rótulo afuera.
      const deltaQueDejaElTopeArriba = cajaObjetivo.top - cajaContenido.top;
      delta = Math.min(delta, deltaQueDejaElTopeArriba);
    }

    // Asignación directa y NO scrollTo({behavior:'smooth'}). Medido el
    // 2026-08-07: el scroll suave programático no hace nada en este entorno
    // —queda en scrollTop 0 y no se mueve nunca— mientras escribir scrollTop
    // funciona siempre. Un scroll animado que a veces no ocurre es peor que
    // un salto: el salto se ve, y para "llevame al error" ver el salto es
    // justamente lo que hace falta. No cambiar a smooth sin volver a medirlo.
    scroller.scrollTop = Math.max(0, scroller.scrollTop + delta);
    // errorServidor entra en las dependencias porque el rechazo del servidor
    // llega DESPUÉS del click: sin él, el Alert aparecía fuera de la vista.
  }, [intentos, errorServidor]);

  const enviarConScroll = () => {
    setIntentos((n) => n + 1);
    onEnviar();
  };

  return (
    <Dialog
      open={abierto}
      // Mientras guarda no se cierra por Escape ni por clic afuera: la
      // request ya salió y cerrar dejaría al usuario sin saber si terminó.
      disableEscapeKeyDown={guardando}
      onClose={onPedirCierre}
      maxWidth={false}
      PaperProps={{ sx: { width: anchoEfectivo, maxWidth: '95vw' } }}
      aria-labelledby="modal-titulo"
    >
      <Box
        sx={(t) => ({
          px: 3,
          pt: 2.5,
          pb: 2,
          borderBottom: `1px solid ${t.palette.superficie.borde}`,
        })}
      >
        <Typography variant="h4" id="modal-titulo">
          {titulo}
        </Typography>
        {subtitulo && (
          // texto-libre: los cuatro modales arman el subtítulo con el nombre
          // del paciente y su n° de historia, los dos de la base.
          <Typography variant="caption" className="texto-libre" sx={{ display: 'block', mt: 0.25 }}>
            {subtitulo}
          </Typography>
        )}
      </Box>

      <DialogContent
        ref={contenidoRef}
        sx={{
          px: 3,
          py: 2.5,
          // Con dos paneles el que scrollea es el panel izquierdo, no esto:
          // si el DialogContent también scrolleara, el panel derecho se iría
          // con él y se perdería justamente lo que el layout viene a resolver.
          ...(dosPaneles ? { overflow: 'hidden', display: 'flex', flexDirection: 'column' } : {}),
        }}
      >
        {errorServidor && (
          <Alert severity="error" data-campo-invalido sx={{ mb: 2.5 }}>
            <AlertTitle>{tituloRechazo}</AlertTitle>
            {/* Mensaje del servidor TAL CUAL. Está redactado en castellano
                y para una persona; varios salen de los triggers de la base.
                Reescribirlo acá solo puede empeorarlo y lo desincroniza
                cuando cambia del otro lado. */}
            {errorServidor.message}
          </Alert>
        )}

        <Box
          component="form"
          noValidate
          onSubmit={(evento) => {
            evento.preventDefault();
            enviarConScroll();
          }}
          sx={{
            display: dosPaneles ? 'grid' : 'flex',
            flexDirection: dosPaneles ? undefined : 'column',
            gap: dosPaneles ? 3 : 2,
            // minmax(0, 1fr): sin el 0, un texto largo en la columna izquierda
            // le gana al 1fr y empuja el panel derecho fuera del modal.
            gridTemplateColumns: dosPaneles
              ? `minmax(0, 1fr) ${PISO_PANEL_LATERAL}px`
              : undefined,
            alignItems: dosPaneles ? 'start' : undefined,
            // minHeight 0 para que el hijo pueda ser más chico que su contenido
            // y por lo tanto pueda scrollear. Sin esto el grid crece y el
            // scroll no aparece nunca.
            minHeight: dosPaneles ? 0 : undefined,
            flex: dosPaneles ? 1 : undefined,
          }}
        >
          {dosPaneles ? (
            <>
              <Box
                ref={panelIzquierdoRef}
                sx={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 2,
                  minHeight: 0,
                  overflowY: 'auto',
                  maxHeight: '100%',
                  // Aire a la derecha para que el texto no toque la barra de
                  // scroll cuando aparece.
                  pr: 1,
                }}
              >
                {children}
              </Box>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                {panelLateral}
              </Box>
            </>
          ) : (
            <>
              {children}
              {panelLateral}
            </>
          )}
          {/* Permite enviar con Enter sin mostrar un segundo botón */}
          <button type="submit" hidden aria-hidden="true" tabIndex={-1} />
        </Box>
      </DialogContent>

      <DialogActions
        sx={(t) => ({
          px: 3,
          py: 2,
          gap: 1,
          borderTop: `1px solid ${t.palette.superficie.borde}`,
        })}
      >
        {soloCerrar ? (
          <>
            {accionPie}
            <Button variant="outlined" onClick={onPedirCierre}>
              Cerrar
            </Button>
          </>
        ) : confirmandoDescarte ? (
          <>
            <Typography
              variant="body2"
              color="text.secondary"
              sx={{ flex: 1, alignSelf: 'center', lineHeight: 1.4 }}
            >
              Hay datos sin guardar. Si cierra ahora, se perderán.
            </Typography>
            <Button variant="outlined" onClick={onSeguirEditando}>
              Seguir editando
            </Button>
            <Button color="error" variant="contained" onClick={onDescartar}>
              Descartar
            </Button>
          </>
        ) : (
          <>
            <Button variant="outlined" disabled={guardando} onClick={onPedirCierre}>
              Cancelar
            </Button>
            <Button
              variant="contained"
              disabled={guardando || enviarDeshabilitado}
              onClick={enviarConScroll}
              startIcon={
                guardando ? <CircularProgress size={14} color="inherit" thickness={5} /> : null
              }
            >
              {guardando ? etiquetaGuardando : etiquetaEnviar}
            </Button>
          </>
        )}
      </DialogActions>
    </Dialog>
  );
}

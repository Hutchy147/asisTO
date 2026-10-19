// frontend/src/components/sesiones/ModalEditarSesion.jsx
//
// Edita estado, notas, fecha, hora de inicio y de fin de una sesión ya
// registrada, vía PUT /api/sesiones/<id>. Se abre desde ModalDetalleSesion
// —la vista de LECTURA del historial de la ficha— y solo cuando la sesión
// es propia: el botón que abre este modal ya filtra por `es_propia` (ver
// ModalDetalleSesion), así que acá no hace falta repetir ese chequeo.
//
// Paciente y terapeuta NO son campos de este formulario: el endpoint los
// ignora (el terapeuta es siempre el logueado) y el paciente es un hecho de
// la sesión, no un dato que se corrija desde acá. El paciente viaja solo
// como contexto en el subtítulo.
//
// `sesion` llega COMO PROP, ya cargada por ModalDetalleSesion: no se vuelve
// a pedir. Mismo criterio que ModalEditarPaciente con `paciente` — el
// formulario arranca con datos reales desde el primer render, no con un
// valor que se completa después de un segundo pedido asíncrono.

import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import FormControlLabel from '@mui/material/FormControlLabel';
import Radio from '@mui/material/Radio';
import RadioGroup from '@mui/material/RadioGroup';
import Typography from '@mui/material/Typography';

import AvisoSesionSinEvolucion from '../avisos/AvisoSesionSinEvolucion.jsx';
import CampoTexto from '../forms/CampoTexto.jsx';
import ModalFormulario from '../modal/ModalFormulario.jsx';
import { useFormularioModal } from '../../hooks/useFormularioModal.js';
import { ErrorApi } from '../../services/api.js';
import {
  editarSesion, ESTADO_AUSENCIA, OPCIONES_AUSENCIA_DE, OPCIONES_ESTADO_SESION,
} from '../../services/sesionesService.js';
import { formatearFecha } from '../../utils/fechas.js';

export default function ModalEditarSesion({ abierto, sesion, paciente, onCerrar, onGuardado }) {
  const formulario = useFormularioModal({
    inicial: {
      estado: sesion?.estado ?? '',
      // Ausencias sembradas antes de que esta columna existiera quedan
      // NULL -- ver schema.sql --, así que acá arranca vacío igual que si
      // fuera una sesión nueva: no hay valor que precargar, y el usuario
      // tiene que elegir antes de poder guardar cualquier otro cambio en
      // esa fila. Es la consecuencia, dicha, no un efecto secundario.
      ausencia_de: sesion?.ausencia_de ?? '',
      notas: sesion?.notas ?? '',
      fecha: sesion?.fecha ?? '',
      hora_inicio: sesion?.hora_inicio?.slice(0, 5) ?? '',
      hora_fin: sesion?.hora_fin?.slice(0, 5) ?? '',
    },
    obligatorios: ['estado', 'fecha', 'hora_inicio'],
    onEnviar: (valores) => {
      const esAusencia = valores.estado === ESTADO_AUSENCIA;
      if (esAusencia && !valores.ausencia_de) {
        throw new ErrorApi('Elija quién faltó a la sesión.', { campo: 'ausencia_de' });
      }
      return editarSesion(sesion.id, {
        estado: valores.estado,
        ausencia_de: esAusencia ? valores.ausencia_de : null,
        notas: valores.notas.trim() || null,
        fecha: valores.fecha,
        hora_inicio: valores.hora_inicio,
        hora_fin: valores.hora_fin || null,
      });
    },
    onExito: (respuesta) => {
      onCerrar?.();
      onGuardado?.(respuesta);
    },
    onCerrar,
  });

  const { valores, setValor, setCampo, errorDe, guardando, validado } = formulario;
  const esAusencia = valores.estado === ESTADO_AUSENCIA;

  // Pasar a ausencia con evoluciones ya cargadas lo rechaza la base (regla
  // 2, al revés — ver trg_sesiones_solape_update). Se deshabilita la
  // opción en vez de dejar que el envío falle siempre: mismo criterio que
  // ModalCargarEvolucion con un objetivo ya calificado. Si la sesión YA
  // está en ausencia no se bloquea: dejarla como está no es la transición
  // que la regla prohíbe.
  const ausenciaBloqueada = Boolean(sesion?.tiene_evolucion) && sesion?.estado !== ESTADO_AUSENCIA;

  // Salir de ausencia limpia "quién faltó", no solo lo esconde. El envío ya
  // fuerza null fuera de ausencia, así que esto no arregla un rechazo que
  // hoy pase: cierra la forma en que ese rechazo nace. Un campo invisible
  // que conserva su valor vuelve a mandarlo en cuanto alguien toque la
  // guarda del envío, y el par (estado, ausencia_de) inconsistente es
  // exactamente lo que trg_sesiones_solape_insert/_update rechaza con 1644.
  //
  // Además se ve: volver a ausencia después de haber salido vuelve a pedir
  // quién faltó en vez de mostrar la respuesta anterior ya marcada. La
  // preselección es justo lo que se decidió no hacer en este campo.
  const cambiarEstado = (valor) => {
    setValor('estado', valor);
    if (valor !== ESTADO_AUSENCIA) setValor('ausencia_de', '');
  };

  return (
    <ModalFormulario
      abierto={abierto}
      ancho={620}
      titulo="Editar sesión"
      subtitulo={
        sesion
          ? (
            <span className="texto-libre">
              {`${paciente?.nombre_completo ?? ''} · ${formatearFecha(sesion.fecha)}`}
            </span>
          )
          : undefined
      }
      guardando={guardando}
      errorServidor={formulario.errorServidor}
      tituloRechazo="No se pudieron guardar los cambios"
      confirmandoDescarte={formulario.confirmandoDescarte}
      onPedirCierre={formulario.pedirCierre}
      onSeguirEditando={formulario.seguirEditando}
      onDescartar={formulario.descartar}
      onEnviar={formulario.enviar}
      etiquetaEnviar="Guardar cambios"
      etiquetaGuardando="Guardando…"
    >
      {sesion?.companero && (
        <Alert severity="info" sx={{ mb: 2 }}>
          Esta sesión integra una dupla con {sesion.companero.nombre_completo}. Si cambia la fecha
          o el horario, también se reprograma la de su compañero.
        </Alert>
      )}
      <Box sx={{ display: 'flex', gap: 2 }}>
        <CampoTexto
          id="editar-sesion-fecha"
          etiqueta="Fecha"
          tipo="date"
          tabular
          obligatorio
          valor={valores.fecha}
          onChange={setCampo('fecha')}
          error={errorDe('fecha')}
          deshabilitado={guardando}
        />
        <CampoTexto
          id="editar-sesion-inicio"
          etiqueta="Hora de inicio"
          tipo="time"
          tabular
          obligatorio
          valor={valores.hora_inicio}
          onChange={setCampo('hora_inicio')}
          error={errorDe('hora_inicio')}
          deshabilitado={guardando}
        />
        <CampoTexto
          id="editar-sesion-fin"
          etiqueta="Hora de fin"
          tipo="time"
          tabular
          ayuda="Opcional. Sin dato se asume una hora."
          valor={valores.hora_fin}
          onChange={setCampo('hora_fin')}
          error={errorDe('hora_fin')}
          deshabilitado={guardando}
        />
      </Box>

      {/* data-campo-invalido: el grupo dibuja su propio error y MUI no lo
          marca. Mismo criterio que ModalRegistrarSesion y que el grupo de
          objetivos de ModalCargarEvolucion. Ver ModalFormulario. */}
      <Box {...(validado && !valores.estado ? { 'data-campo-invalido': '' } : {})}>
        <Typography variant="body2" sx={{ fontWeight: 500, mb: 0.5 }}>
          Estado de la sesión <Box component="span" sx={{ color: 'error.main' }}>*</Box>
        </Typography>
        <RadioGroup
          value={valores.estado}
          onChange={(evento) => cambiarEstado(evento.target.value)}
        >
          {OPCIONES_ESTADO_SESION.map((estado) => {
            const bloqueada = estado.valor === ESTADO_AUSENCIA && ausenciaBloqueada;
            return (
              <FormControlLabel
                key={estado.valor}
                value={estado.valor}
                disabled={guardando || bloqueada}
                control={<Radio size="small" />}
                label={
                  <Box sx={{ py: 0.25 }}>
                    <Box component="span" sx={{ fontSize: 14 }}>
                      {estado.etiqueta}
                    </Box>
                    <Typography variant="caption" sx={{ display: 'block' }}>
                      {bloqueada
                        ? 'Ya tiene evolución cargada: no se puede marcar como ausencia.'
                        : estado.descripcion}
                    </Typography>
                  </Box>
                }
              />
            );
          })}
        </RadioGroup>
        {validado && !valores.estado && (
          <Typography variant="caption" color="error">
            Elija cómo transcurrió la sesión.
          </Typography>
        )}
      </Box>

      {/* Mismo bloque que ModalRegistrarSesion, mismo criterio. */}
      {esAusencia && (
        <Box {...(validado && !valores.ausencia_de ? { 'data-campo-invalido': '' } : {})}>
          <Typography variant="body2" sx={{ fontWeight: 500, mb: 0.5 }}>
            Quién faltó <Box component="span" sx={{ color: 'error.main' }}>*</Box>
          </Typography>
          <RadioGroup
            value={valores.ausencia_de}
            onChange={(evento) => setValor('ausencia_de', evento.target.value)}
          >
            {OPCIONES_AUSENCIA_DE.map((opcion) => (
              <FormControlLabel
                key={opcion.valor}
                value={opcion.valor}
                disabled={guardando}
                control={<Radio size="small" />}
                label={<Box component="span" sx={{ fontSize: 14 }}>{opcion.etiqueta}</Box>}
              />
            ))}
          </RadioGroup>
          {validado && !valores.ausencia_de && (
            <Typography variant="caption" color="error">
              Elija quién faltó a la sesión.
            </Typography>
          )}
        </Box>
      )}

      {/* Mismo criterio que ModalRegistrarSesion: la consecuencia se ve
          antes de confirmar, todavía se puede cambiar de opinión. */}
      {esAusencia && <AvisoSesionSinEvolucion modo="registro" />}

      <CampoTexto
        id="editar-sesion-notas"
        etiqueta={esAusencia ? 'Motivo de la ausencia' : 'Notas de la sesión'}
        multilinea
        filas={3}
        ayuda="Opcional."
        valor={valores.notas}
        onChange={setCampo('notas')}
        deshabilitado={guardando}
      />
    </ModalFormulario>
  );
}

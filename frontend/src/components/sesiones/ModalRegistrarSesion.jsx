// frontend/src/components/sesiones/ModalRegistrarSesion.jsx

import Box from '@mui/material/Box';
import FormControlLabel from '@mui/material/FormControlLabel';
import MenuItem from '@mui/material/MenuItem';
import Radio from '@mui/material/Radio';
import RadioGroup from '@mui/material/RadioGroup';
import Typography from '@mui/material/Typography';

import AvisoSesionSinEvolucion from '../avisos/AvisoSesionSinEvolucion.jsx';
import CampoTexto from '../forms/CampoTexto.jsx';
import ModalFormulario from '../modal/ModalFormulario.jsx';
import { useFormularioModal } from '../../hooks/useFormularioModal.js';
import { ErrorApi } from '../../services/api.js';
import {
  ESTADO_AUSENCIA, OPCIONES_AUSENCIA_DE, OPCIONES_ESTADO_SESION, registrarSesion,
} from '../../services/sesionesService.js';
import { formatearFecha } from '../../utils/fechas.js';

export default function ModalRegistrarSesion({
  abierto,
  pacientes = [],
  // Precarga cuando se abre desde un hueco de la grilla
  fechaInicial = '',
  horaInicial = '',
  onCerrar,
  onRegistrada,
}) {
  const formulario = useFormularioModal({
    inicial: {
      id_paciente: '',
      fecha: fechaInicial,
      hora_inicio: horaInicial,
      hora_fin: '',
      // Arranca VACÍO a propósito: no hay estado por omisión que sea
      // correcto. Ver el aviso más abajo y el hallazgo A de AUDITORIA.md.
      estado: '',
      // Mismo criterio que estado: sin preselección. Es el mismo defecto
      // que se acaba de cerrar dos veces (estado en la interfaz y en la
      // base) y no se reintroduce acá para el campo nuevo.
      ausencia_de: '',
      notas: '',
    },
    obligatorios: ['id_paciente', 'fecha', 'hora_inicio', 'estado'],
    onEnviar: (valores) => {
      const esAusencia = valores.estado === ESTADO_AUSENCIA;
      // No está en `obligatorios` porque solo es obligatorio CONDICIONADO
      // al estado, y ese mecanismo es para campos siempre obligatorios.
      // Se valida acá, antes de gastar un viaje al servidor -- que de
      // todos modos lo iba a rechazar, ver _validar_ausencia_de en
      // sesiones_service.py -- y el throw lo capta el mismo catch que
      // captura un rechazo real, así que se muestra igual.
      if (esAusencia && !valores.ausencia_de) {
        throw new ErrorApi('Elegí quién faltó a la sesión.', { campo: 'ausencia_de' });
      }
      return registrarSesion({
        id_paciente: Number(valores.id_paciente),
        fecha: valores.fecha,
        hora_inicio: valores.hora_inicio,
        hora_fin: valores.hora_fin || null,
        estado: valores.estado,
        // Se fuerza null fuera de ausencia. Desde que `cambiarEstado`
        // limpia el campo al salir de ausencia esto ya no debería tener
        // nada que forzar, y se queda igual a propósito: son dos guardas
        // independientes de la misma regla, y la de acá es la única que
        // sigue valiendo si alguien cambia el estado por otro camino.
        ausencia_de: esAusencia ? valores.ausencia_de : null,
        notas: valores.notas.trim() || null,
      });
    },
    onExito: (respuesta) => {
      onCerrar?.();
      onRegistrada?.(respuesta);
    },
    onCerrar,
  });

  const { valores, setValor, setCampo, errorDe, guardando, validado } = formulario;
  const esAusencia = valores.estado === ESTADO_AUSENCIA;

  // Salir de ausencia limpia "quién faltó", no solo lo esconde. Mismo
  // criterio y mismo porqué que en ModalEditarSesion: el envío ya fuerza
  // null, y esto cierra la forma en que nace el par inconsistente que la
  // base rechaza con 1644. También evita que volver a ausencia muestre la
  // respuesta anterior ya marcada, que es la preselección que este campo
  // decidió no tener.
  const cambiarEstado = (valor) => {
    setValor('estado', valor);
    if (valor !== ESTADO_AUSENCIA) setValor('ausencia_de', '');
  };

  return (
    <ModalFormulario
      abierto={abierto}
      ancho={620}
      titulo="Registrar sesión"
      subtitulo={
        valores.fecha
          ? `${formatearFecha(valores.fecha)}${valores.hora_inicio ? ` · ${valores.hora_inicio.slice(0, 5)}` : ''}`
          : 'Se registra a su nombre'
      }
      guardando={guardando}
      errorServidor={formulario.errorServidor}
      tituloRechazo="No se pudo registrar la sesión"
      confirmandoDescarte={formulario.confirmandoDescarte}
      onPedirCierre={formulario.pedirCierre}
      onSeguirEditando={formulario.seguirEditando}
      onDescartar={formulario.descartar}
      onEnviar={formulario.enviar}
      etiquetaEnviar="Registrar sesión"
      etiquetaGuardando="Registrando…"
    >
      <CampoTexto
        id="sesion-paciente"
        etiqueta="Paciente"
        select
        obligatorio
        ayuda={pacientes.length === 0
          ? 'No tiene pacientes asignados. Solicite la asignación al administrador.'
          : undefined}
        valor={valores.id_paciente}
        onChange={setCampo('id_paciente')}
        error={errorDe('id_paciente')}
        deshabilitado={guardando}
      >
        {pacientes.map((paciente) => (
          // texto-libre: nombre_completo y nro_historia salen de la base.
          // MUI le pone white-space: nowrap a MenuItem de fábrica, así que
          // "no se rompe el layout" venía de un default de terceros, no de una
          // decisión nuestra. La 14 bis no tiene excepción para eso: si MUI
          // cambia ese default, el bug aparece sin que nadie toque este
          // archivo. La clase lo deja explícito acá.
          <MenuItem key={paciente.id} value={paciente.id} className="texto-libre">
            {paciente.nombre_completo} · {paciente.nro_historia}
          </MenuItem>
        ))}
      </CampoTexto>

      <Box sx={{ display: 'flex', gap: 2 }}>
        <CampoTexto
          id="sesion-fecha"
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
          id="sesion-inicio"
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
          id="sesion-fin"
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
          marca. Mismo criterio que el grupo de objetivos de
          ModalCargarEvolucion. Ver ModalFormulario. */}
      <Box {...(validado && !valores.estado ? { 'data-campo-invalido': '' } : {})}>
        <Typography variant="body2" sx={{ fontWeight: 500, mb: 0.5 }}>
          Estado de la sesión <Box component="span" sx={{ color: 'error.main' }}>*</Box>
        </Typography>
        <RadioGroup
          value={valores.estado}
          onChange={(evento) => cambiarEstado(evento.target.value)}
        >
          {OPCIONES_ESTADO_SESION.map((estado) => (
            <FormControlLabel
              key={estado.valor}
              value={estado.valor}
              disabled={guardando}
              control={<Radio size="small" />}
              label={
                <Box sx={{ py: 0.25 }}>
                  <Box component="span" sx={{ fontSize: 14 }}>
                    {estado.etiqueta}
                  </Box>
                  <Typography variant="caption" sx={{ display: 'block' }}>
                    {estado.descripcion}
                  </Typography>
                </Box>
              }
            />
          ))}
        </RadioGroup>
        {validado && !valores.estado && (
          <Typography variant="caption" color="error">
            Elegí cómo transcurrió la sesión.
          </Typography>
        )}
      </Box>

      {/* Solo aparece si esAusencia: es el mismo criterio que el aviso de
          más abajo, la consecuencia se ve al elegir, no al guardar. */}
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
              Elegí quién faltó a la sesión.
            </Typography>
          )}
        </Box>
      )}

      {/* El aviso aparece AL ELEGIR ausencia, no al guardar: para eso está
          el radio ahí arriba, para que la consecuencia se vea antes de
          confirmar y todavía se pueda cambiar de opinión. */}
      {esAusencia && <AvisoSesionSinEvolucion modo="registro" />}

      <CampoTexto
        id="sesion-notas"
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

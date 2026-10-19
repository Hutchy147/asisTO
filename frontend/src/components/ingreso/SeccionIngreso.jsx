// frontend/src/components/ingreso/SeccionIngreso.jsx
// Pestaña "Ingreso" de la ficha (Entrega 4): paciente nuevo. Cuatro etapas
// (carpeta, evaluación inicial, entrevista a la familia y PTI) y, con los
// objetivos fijados, la generación de la historia clínica del centro.
//
// Las reglas (quién escribe, qué falta para cerrar o completar) las aplica la
// base; esta pantalla muestra el estado y traduce los rechazos.

import { useState } from 'react';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Typography from '@mui/material/Typography';

import { Cargando, EstadoError, EstadoVacio } from '../estado/index.js';
import FormularioEtapa from './FormularioEtapa.jsx';
import HistoriaClinica from './HistoriaClinica.jsx';
import { usePeticion } from '../../hooks/usePeticion.js';
import {
  cerrarEtapa, completarIngreso, guardarEtapa, iniciarIngreso, obtenerIngreso, reabrirEtapa,
} from '../../services/ingresoService.js';

const ESTADOS = {
  pendiente: { etiqueta: 'Pendiente', color: 'default' },
  en_curso: { etiqueta: 'En curso', color: 'warning' },
  cerrada: { etiqueta: 'Cerrada', color: 'success' },
};

function Tarjeta({ children }) {
  return (
    <Box
      sx={(t) => ({
        backgroundColor: t.palette.superficie.tarjeta,
        border: `1px solid ${t.palette.superficie.borde}`,
        borderRadius: `${t.formas.md}px`,
        mb: 2,
      })}
    >
      {children}
    </Box>
  );
}

export default function SeccionIngreso({ paciente, puedeEscribir, onAviso, onIrAObjetivos }) {
  const ingreso = usePeticion(() => obtenerIngreso(paciente.id), [paciente.id]);
  const [abierta, setAbierta] = useState(null);
  const [error, setError] = useState('');
  const [trabajando, setTrabajando] = useState(false);

  const datos = ingreso.datos;

  // Cada acción devuelve el estado nuevo del ingreso: se reemplaza sin
  // volver a pedirlo, y el mensaje de la base va tal cual al aviso.
  const aplicar = async (accion) => {
    const respuesta = await accion();
    ingreso.setDatos(respuesta);
    if (respuesta.mensaje) onAviso?.(respuesta.mensaje);
    return respuesta;
  };

  const iniciar = async () => {
    setTrabajando(true);
    setError('');
    try {
      await aplicar(() => iniciarIngreso(paciente.id));
    } catch (fallo) {
      setError(fallo.message);
    } finally {
      setTrabajando(false);
    }
  };

  const completar = async () => {
    setTrabajando(true);
    setError('');
    try {
      await aplicar(() => completarIngreso(paciente.id));
    } catch (fallo) {
      setError(fallo.message);
    } finally {
      setTrabajando(false);
    }
  };

  if (ingreso.cargando && !datos) return <Cargando texto="Cargando el ingreso..." />;
  if (ingreso.error) return <EstadoError error={ingreso.error} onReintentar={ingreso.recargar} />;
  if (!datos) return null;

  // --- Sin ingreso iniciado ---
  if (!datos.ingreso) {
    return (
      <Tarjeta>
        {error && <Alert severity="error" sx={{ m: 2 }}>{error}</Alert>}
        <EstadoVacio
          plano
          titulo="Todavía no tiene un ingreso iniciado"
          descripcion={
            puedeEscribir && paciente.activo
              ? 'El ingreso ordena la llegada de un paciente nuevo: revisión de la carpeta, evaluación inicial, entrevista a la familia y plan terapéutico. Al completarlo se genera su historia clínica.'
              : 'Solo el terapeuta asignado puede iniciar el ingreso de un paciente en tratamiento.'
          }
          acciones={
            puedeEscribir && paciente.activo ? (
              <Button variant="contained" disabled={trabajando} onClick={iniciar}>
                {trabajando ? 'Iniciando…' : 'Iniciar ingreso'}
              </Button>
            ) : null
          }
        />
      </Tarjeta>
    );
  }

  const completado = datos.ingreso.estado === 'completado';
  const cerradas = datos.etapas.filter((e) => e.estado === 'cerrada').length;
  const objetivosOk = datos.objetivos_activos >= datos.minimo_objetivos;
  const listo = cerradas === datos.etapas.length && objetivosOk;
  const editable = puedeEscribir && !completado && paciente.activo;

  return (
    <>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      {completado ? (
        <>
          <Alert severity="success" sx={{ mb: 2 }}>
            El ingreso está completo. La historia clínica del centro quedó generada.
          </Alert>
          <HistoriaClinica idPaciente={paciente.id} />
        </>
      ) : (
        <Tarjeta>
          <Box sx={(t) => ({ px: 2.25, py: 1.75, borderBottom: `1px solid ${t.palette.superficie.borde}` })}>
            <Typography variant="h5">Ingreso del paciente</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.25 }}>
              Iniciado el {new Date(`${datos.ingreso.fecha_inicio}T00:00:00`).toLocaleDateString('es-AR')}
              {datos.ingreso.terapeuta ? ` por ${datos.ingreso.terapeuta}` : ''}.
              Complete las cuatro etapas y fije los objetivos para generar la historia clínica.
            </Typography>
          </Box>

          {datos.etapas.map((etapa, indice) => {
            const estado = ESTADOS[etapa.estado];
            const desplegada = abierta === etapa.etapa;
            return (
              <Box key={etapa.etapa} data-testid={`etapa-${etapa.etapa}`} sx={(t) => ({ borderBottom: `1px solid ${t.palette.superficie.borde}` })}>
                <Box
                  role="button"
                  tabIndex={0}
                  aria-expanded={desplegada}
                  onClick={() => setAbierta(desplegada ? null : etapa.etapa)}
                  onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') setAbierta(desplegada ? null : etapa.etapa); }}
                  sx={{ display: 'flex', alignItems: 'center', gap: 2, px: 2.25, py: 1.5, cursor: 'pointer' }}
                >
                  <Typography variant="h6" sx={{ flex: 1 }}>
                    {indice + 1}. {etapa.nombre}
                    <Typography variant="body2" color="text.secondary" component="span" sx={{ display: 'block', fontWeight: 400 }}>
                      {etapa.descripcion}
                    </Typography>
                  </Typography>
                  {etapa.estado !== 'cerrada' && etapa.obligatorios_faltantes > 0 && (
                    <Typography variant="caption" color="text.secondary">
                      {etapa.obligatorios_faltantes} obligatorio(s) por completar
                    </Typography>
                  )}
                  <Chip size="small" color={estado.color} label={estado.etiqueta} />
                </Box>
                {desplegada && (
                  <FormularioEtapa
                    key={`${etapa.etapa}-${etapa.estado}`}
                    etapa={etapa}
                    editable={editable}
                    onGuardar={(valores) => aplicar(() => guardarEtapa(paciente.id, etapa.etapa, valores))}
                    onCerrar={() => aplicar(() => cerrarEtapa(paciente.id, etapa.etapa))}
                    onReabrir={() => aplicar(() => reabrirEtapa(paciente.id, etapa.etapa))}
                  />
                )}
              </Box>
            );
          })}

          <Box sx={{ p: 2.25, display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
            <Box sx={{ flex: 1, minWidth: 260 }}>
              <Typography variant="h6">Generar la historia clínica</Typography>
              <Typography variant="body2" color="text.secondary" data-testid="requisitos">
                Etapas cerradas: {cerradas} de {datos.etapas.length}. Objetivos activos:{' '}
                {datos.objetivos_activos} de {datos.minimo_objetivos} como mínimo.
                {!objetivosOk && ' Tras observar al paciente, fije sus objetivos en la pestaña Objetivos.'}
              </Typography>
            </Box>
            {!objetivosOk && (
              <Button color="inherit" onClick={onIrAObjetivos}>Ir a Objetivos</Button>
            )}
            {editable && (
              <Button variant="contained" disabled={!listo || trabajando} onClick={completar}>
                {trabajando ? 'Generando…' : 'Completar ingreso'}
              </Button>
            )}
          </Box>
        </Tarjeta>
      )}
    </>
  );
}

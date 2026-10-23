// frontend/src/components/familiares/SeccionFamiliares.jsx
// Pestaña "Familia" de la ficha (Entrega 4): quiénes tienen acceso al portal
// con la evolución de este paciente. Vincular y desvincular lo hace el
// terapeuta asignado o el administrador.

import { useState } from 'react';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Typography from '@mui/material/Typography';

import DataTable from '../data/DataTable.jsx';
import { Cargando, EstadoError, EstadoVacio } from '../estado/index.js';
import DialogoConfirmacion from '../modal/DialogoConfirmacion.jsx';
import DialogoContrasenaTemporal from './DialogoContrasenaTemporal.jsx';
import ModalCrearFamiliar from './ModalCrearFamiliar.jsx';
import ModalVincularExistente from './ModalVincularExistente.jsx';
import { usePeticion } from '../../hooks/usePeticion.js';
import {
  desvincularFamiliar, listarCandidatos, listarFamiliaresDePaciente,
} from '../../services/familiaresService.js';
import { formatearFecha } from '../../utils/fechas.js';

export default function SeccionFamiliares({ paciente, puedeGestionar = true, soloQuitar = false, onAviso }) {
  const lista = usePeticion(() => listarFamiliaresDePaciente(paciente.id), [paciente.id]);
  const candidatos = usePeticion(
    // Con el paciente de baja no se vincula a nadie: no hace falta la lista.
    () => (soloQuitar ? Promise.resolve({ familiares: [] }) : listarCandidatos(paciente.id)),
    [paciente.id, soloQuitar],
  );

  const [modal, setModal] = useState(null); // null | 'existente' | 'nuevo'
  const [aDesvincular, setADesvincular] = useState(null);
  const [procesando, setProcesando] = useState(false);
  const [errorBaja, setErrorBaja] = useState('');
  const [credenciales, setCredenciales] = useState(null);

  const recargar = () => {
    lista.recargar();
    candidatos.recargar();
  };

  const confirmarBaja = async () => {
    setProcesando(true);
    setErrorBaja('');
    try {
      await desvincularFamiliar(paciente.id, aDesvincular.id);
      onAviso?.(`Se quitó el acceso de ${aDesvincular.nombre_completo}.`);
      setADesvincular(null);
      recargar();
    } catch (error) {
      setErrorBaja(error.message);
    } finally {
      setProcesando(false);
    }
  };

  const columnas = [
    {
      clave: 'nombre', etiqueta: 'Familiar', truncar: true,
      render: (f) => <span className="texto-libre">{f.nombre_completo}</span>,
    },
    { clave: 'parentesco', etiqueta: 'Parentesco', ancho: 130, render: (f) => <span className="texto-libre">{f.parentesco ?? '—'}</span> },
    { clave: 'email', etiqueta: 'Correo electrónico', truncar: true, render: (f) => <span className="texto-libre">{f.email}</span> },
    { clave: 'telefono', etiqueta: 'Teléfono', ancho: 130, render: (f) => <span className="tabular">{f.telefono ?? '—'}</span> },
    { clave: 'desde', etiqueta: 'Vinculado', ancho: 120, render: (f) => formatearFecha(f.fecha_vinculo) },
  ];
  if (puedeGestionar) {
    columnas.push({
      clave: 'acciones', etiqueta: '', ancho: 130,
      render: (f) => (
        <Button size="small" color="inherit" onClick={() => { setErrorBaja(''); setADesvincular(f); }}>
          Quitar acceso
        </Button>
      ),
    });
  }

  return (
    <Box
      sx={(t) => ({
        backgroundColor: t.palette.superficie.tarjeta,
        border: `1px solid ${t.palette.superficie.borde}`,
        borderRadius: `${t.formas.md}px`,
        mb: 2,
      })}
    >
      <Box
        sx={(t) => ({
          display: 'flex', alignItems: 'flex-start', gap: 2, px: 2.25, py: 1.75,
          borderBottom: `1px solid ${t.palette.superficie.borde}`,
        })}
      >
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography variant="h5">Familiares con acceso</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.25 }}>
            Cada familiar vinculado puede consultar la evolución del paciente y recibe
            avisos del tratamiento. En el portal no ve el diagnóstico ni las notas de cada
            sesión; sí lee completos los informes que se publiquen.
          </Typography>
        </Box>
        {puedeGestionar && !soloQuitar && (
          <Box sx={{ display: 'flex', gap: 1, flex: 'none' }}>
            <Button variant="outlined" onClick={() => setModal('existente')}>Vincular existente</Button>
            <Button variant="contained" onClick={() => setModal('nuevo')}>Crear cuenta</Button>
          </Box>
        )}
      </Box>

      {lista.cargando && <Cargando texto="Cargando los familiares..." />}
      {lista.error && <EstadoError error={lista.error} onReintentar={lista.recargar} />}
      {lista.datos && !lista.cargando && !lista.error && (
        lista.datos.familiares.length === 0 ? (
          <EstadoVacio
            plano
            titulo="Todavía no tiene familiares vinculados"
            descripcion="Mientras no haya un familiar vinculado, nadie de la familia puede consultar la evolución ni recibe avisos."
          />
        ) : (
          <DataTable columnas={columnas} filas={lista.datos.familiares} />
        )
      )}

      <ModalVincularExistente
        abierto={modal === 'existente'}
        paciente={paciente}
        candidatos={candidatos.datos?.familiares ?? []}
        onCerrar={() => setModal(null)}
        onVinculado={(r) => { onAviso?.(r.mensaje); recargar(); }}
      />
      <ModalCrearFamiliar
        abierto={modal === 'nuevo'}
        paciente={paciente}
        onCerrar={() => setModal(null)}
        onCreado={(r) => {
          setCredenciales({ familiar: r.familiar, contrasena: r.contrasena_temporal });
          recargar();
        }}
      />
      <DialogoContrasenaTemporal datos={credenciales} onCerrar={() => setCredenciales(null)} />
      <DialogoConfirmacion
        abierto={Boolean(aDesvincular)}
        titulo="Quitar el acceso"
        etiquetaConfirmar="Quitar acceso"
        etiquetaProcesando="Quitando…"
        procesando={procesando}
        onConfirmar={confirmarBaja}
        onCancelar={() => setADesvincular(null)}
        extra={errorBaja ? <Typography color="error" variant="body2">{errorBaja}</Typography> : null}
      >
        {aDesvincular && (
          <>
            <strong className="texto-libre">{aDesvincular.nombre_completo}</strong> dejará de ver
            la evolución de {paciente.nombre_completo} y de recibir sus avisos. La cuenta se conserva.
          </>
        )}
      </DialogoConfirmacion>
    </Box>
  );
}

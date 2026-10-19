// frontend/src/pages/AdminFormulariosIngreso.jsx
// Configuración del formulario de ingreso (Entrega 4). El administrador
// ajusta los campos de cada etapa; NO ve las respuestas de ningún paciente
// (contenido clínico). Los campos no se borran, se desactivan: las
// respuestas ya cargadas siguen apuntando a ellos.

import { useState } from 'react';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Container from '@mui/material/Container';
import Snackbar from '@mui/material/Snackbar';
import Switch from '@mui/material/Switch';
import Typography from '@mui/material/Typography';

import BarraAdmin from '../components/admin/BarraAdmin.jsx';
import DataTable from '../components/data/DataTable.jsx';
import { Cargando, EstadoError } from '../components/estado/index.js';
import ModalCampoIngreso from '../components/ingreso/ModalCampoIngreso.jsx';
import { usePeticion } from '../hooks/usePeticion.js';
import { editarCampoDeIngreso, listarCamposDeIngreso } from '../services/ingresoService.js';

const TIPOS = {
  texto: 'Texto corto', texto_largo: 'Texto largo', fecha: 'Fecha', opcion: 'Opción única',
};

export default function AdminFormulariosIngreso() {
  const formulario = usePeticion(() => listarCamposDeIngreso(), []);
  const [modal, setModal] = useState(null); // null | { etapa, campo? }
  const [aviso, setAviso] = useState('');
  const [error, setError] = useState('');

  const cambiar = async (campo, cambios) => {
    setError('');
    try {
      await editarCampoDeIngreso(campo.id, cambios);
      formulario.recargar();
    } catch (fallo) {
      setError(fallo.message);
    }
  };

  const columnas = (etapa) => [
    {
      clave: 'etiqueta', etiqueta: 'Campo', truncar: true,
      render: (c) => (
        <Box sx={{ opacity: c.activo ? 1 : 0.55 }}>
          <span className="texto-libre">{c.etiqueta}</span>
          {c.ayuda && <Typography variant="caption" color="text.secondary" component="div" className="texto-libre">{c.ayuda}</Typography>}
        </Box>
      ),
    },
    { clave: 'tipo', etiqueta: 'Tipo', ancho: 130, render: (c) => TIPOS[c.tipo] },
    {
      clave: 'obligatorio', etiqueta: 'Obligatorio', ancho: 110,
      render: (c) => (
        <Switch size="small" checked={c.obligatorio} onChange={(e) => cambiar(c, { obligatorio: e.target.checked })}
          inputProps={{ 'aria-label': `Obligatorio: ${c.etiqueta}` }} />
      ),
    },
    {
      clave: 'activo', etiqueta: 'Visible', ancho: 90,
      render: (c) => (
        <Switch size="small" checked={c.activo} onChange={(e) => cambiar(c, { activo: e.target.checked })}
          inputProps={{ 'aria-label': `Visible: ${c.etiqueta}` }} />
      ),
    },
    { clave: 'orden', etiqueta: 'Orden', ancho: 80, render: (c) => <span className="tabular">{c.orden}</span> },
    {
      clave: 'acciones', etiqueta: '', ancho: 90,
      render: (c) => <Button size="small" color="inherit" onClick={() => setModal({ etapa, campo: c })}>Editar</Button>,
    },
  ];

  return (
    <Box sx={{ minHeight: '100vh' }}>
      <BarraAdmin activa="formularios" />
      <Container maxWidth="lg" sx={{ py: 4 }}>
        <Typography variant="h4">Formulario de ingreso</Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
          Defina qué se completa en cada etapa del ingreso de un paciente nuevo. Los campos no se
          eliminan: se ocultan, para conservar lo ya cargado. Las historias clínicas ya generadas
          no cambian al modificar el formulario.
        </Typography>

        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        {formulario.cargando && <Cargando texto="Cargando el formulario..." />}
        {formulario.error && <EstadoError error={formulario.error} onReintentar={formulario.recargar} />}

        {formulario.datos?.etapas.map((etapa) => (
          <Box
            key={etapa.etapa}
            data-testid={`config-${etapa.etapa}`}
            sx={(t) => ({
              backgroundColor: t.palette.superficie.tarjeta,
              border: `1px solid ${t.palette.superficie.borde}`,
              borderRadius: `${t.formas.md}px`,
              mb: 3,
            })}
          >
            <Box sx={(t) => ({ display: 'flex', alignItems: 'center', gap: 2, px: 2.25, py: 1.5, borderBottom: `1px solid ${t.palette.superficie.borde}` })}>
              <Typography variant="h5" sx={{ flex: 1 }}>{etapa.nombre}</Typography>
              <Chip size="small" label={`${etapa.campos.filter((c) => c.activo).length} campos visibles`} />
              <Button variant="outlined" onClick={() => setModal({ etapa })}>Agregar campo</Button>
            </Box>
            <DataTable columnas={columnas(etapa)} filas={etapa.campos} />
          </Box>
        ))}
      </Container>

      {modal && (
        <ModalCampoIngreso
          abierto
          etapa={modal.etapa}
          campo={modal.campo}
          onCerrar={() => setModal(null)}
          onGuardado={() => { setAviso('Campo guardado.'); formulario.recargar(); }}
        />
      )}
      <Snackbar open={Boolean(aviso)} autoHideDuration={4000} onClose={() => setAviso('')} message={aviso} />
    </Box>
  );
}

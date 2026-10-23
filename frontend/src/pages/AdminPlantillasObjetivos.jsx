// frontend/src/pages/AdminPlantillasObjetivos.jsx
// Catálogo de plantillas de objetivos por área (Entrega 5). El administrador
// lo cura; las terapeutas lo usan al crear un objetivo. El texto se copia al
// objetivo: editar o quitar una plantilla no cambia objetivos ya creados.

import { useState } from 'react';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Container from '@mui/material/Container';
import Snackbar from '@mui/material/Snackbar';
import Typography from '@mui/material/Typography';

import BarraAdmin from '../components/admin/BarraAdmin.jsx';
import DataTable from '../components/data/DataTable.jsx';
import { Cargando, EstadoError } from '../components/estado/index.js';
import ModalPlantillaObjetivo from '../components/objetivos/ModalPlantillaObjetivo.jsx';
import { usePeticion } from '../hooks/usePeticion.js';
import { listarPlantillas, quitarPlantilla } from '../services/plantillasObjetivosService.js';

export default function AdminPlantillasObjetivos() {
  const catalogo = usePeticion(() => listarPlantillas(), []);
  const [modal, setModal] = useState(null); // null | { plantilla?, area? }
  const [aviso, setAviso] = useState('');
  const [error, setError] = useState('');
  const [confirmar, setConfirmar] = useState(null); // plantilla a quitar

  async function quitar(plantilla) {
    setError('');
    try {
      await quitarPlantilla(plantilla.id);
      setConfirmar(null);
      setAviso('Plantilla quitada.');
      catalogo.recargar();
    } catch (fallo) {
      setError(fallo.message);
      setConfirmar(null);
    }
  }

  // Las plantillas llegan anidadas en su área: la edición tiene que llevarla,
  // o el formulario abría el Área vacía y obligaba a reescribirla (F6.1).
  const columnasDe = (area) => [
    {
      clave: 'descripcion', etiqueta: 'Texto sugerido',
      render: (p) => <span className="texto-libre">{p.descripcion}</span>,
    },
    {
      clave: 'acciones', etiqueta: '', ancho: 200,
      render: (p) => (
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button size="small" color="inherit" onClick={() => setModal({ plantilla: { ...p, area } })}>Editar</Button>
          {confirmar?.id === p.id ? (
            <Button size="small" color="error" variant="contained" onClick={() => quitar(p)}>Confirmar</Button>
          ) : (
            <Button size="small" color="inherit" onClick={() => setConfirmar(p)}>Quitar</Button>
          )}
        </Box>
      ),
    },
  ];

  return (
    <Box sx={{ minHeight: '100vh' }}>
      <BarraAdmin activa="plantillas" />
      <Container maxWidth="lg" sx={{ py: 4 }}>
        <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 2, mb: 3 }}>
          <Box sx={{ flex: 1 }}>
            <Typography variant="h4">Plantillas de objetivos</Typography>
            <Typography variant="body2" color="text.secondary">
              Textos sugeridos, agrupados por área, que las terapeutas pueden elegir al crear un
              objetivo y ajustar. Cambiar o quitar una plantilla no modifica los objetivos ya creados.
            </Typography>
          </Box>
          <Button variant="contained" onClick={() => setModal({})}>Nueva plantilla</Button>
        </Box>

        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        {catalogo.cargando && !catalogo.datos && <Cargando texto="Cargando las plantillas..." />}
        {catalogo.error && <EstadoError error={catalogo.error} onReintentar={catalogo.recargar} />}
        {catalogo.datos?.total === 0 && (
          <Alert severity="info">Todavía no hay plantillas. Use «Nueva plantilla» para cargar la primera.</Alert>
        )}

        {catalogo.datos?.areas.map((a) => (
          <Box
            key={a.area}
            data-testid={`area-${a.area}`}
            sx={(t) => ({
              backgroundColor: t.palette.superficie.tarjeta,
              border: `1px solid ${t.palette.superficie.borde}`,
              borderRadius: `${t.formas.md}px`,
              mb: 3,
            })}
          >
            <Box sx={(t) => ({ display: 'flex', alignItems: 'center', gap: 2, px: 2.25, py: 1.5, borderBottom: `1px solid ${t.palette.superficie.borde}` })}>
              <Typography variant="h5" className="texto-libre" sx={{ flex: 1 }}>{a.area}</Typography>
              <Chip size="small" label={`${a.plantillas.length} ${a.plantillas.length === 1 ? 'plantilla' : 'plantillas'}`} />
              <Button variant="outlined" onClick={() => setModal({ area: a.area })}>Agregar a esta área</Button>
            </Box>
            <DataTable columnas={columnasDe(a.area)} filas={a.plantillas} />
          </Box>
        ))}
      </Container>

      {modal && (
        <ModalPlantillaObjetivo
          abierto
          plantilla={modal.plantilla}
          areaInicial={modal.area ?? ''}
          onCerrar={() => setModal(null)}
          onGuardado={() => { setAviso('Plantilla guardada.'); catalogo.recargar(); }}
        />
      )}
      <Snackbar open={Boolean(aviso)} autoHideDuration={4000} onClose={() => setAviso('')} message={aviso} />
    </Box>
  );
}

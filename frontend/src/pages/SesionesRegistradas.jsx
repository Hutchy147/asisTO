// frontend/src/pages/SesionesRegistradas.jsx
// Consulta de sesiones registradas (Entrega 5): lo que ya ocurrió y quedó
// registrado, con filtros y paginación. Es la pantalla para buscar y revisar,
// no la de trabajo pendiente (esa es el Panel).
//
// Lectura abierta entre terapeutas (igual que la ficha clínica): «Mis sesiones»
// o «Todas». Editar sigue siendo de quien atendió; el detalle lo indica.

import { useMemo, useState } from 'react';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import MenuItem from '@mui/material/MenuItem';
import Snackbar from '@mui/material/Snackbar';
import Typography from '@mui/material/Typography';

import DataTable from '../components/data/DataTable.jsx';
import PersonCell from '../components/data/PersonCell.jsx';
import SesionEstadoChip from '../components/data/SesionEstadoChip.jsx';
import { Cargando, EstadoError, EstadoVacio } from '../components/estado/index.js';
import ModalCargarEvolucion from '../components/evoluciones/ModalCargarEvolucion.jsx';
import CampoTexto from '../components/forms/CampoTexto.jsx';
import AppLayout from '../components/layout/AppLayout.jsx';
import ModalDetalleSesion from '../components/sesiones/ModalDetalleSesion.jsx';
import ModalEditarSesion from '../components/sesiones/ModalEditarSesion.jsx';
import { usePeticion } from '../hooks/usePeticion.js';
import { useFiltrosEnUrl } from '../hooks/useEstadoEnUrl.js';
import { listarPacientes } from '../services/pacientesService.js';
import { estadoVisible, listarSesionesRegistradas } from '../services/sesionesService.js';
import { formatearFecha } from '../utils/fechas.js';

const POR_PAGINA = 15;

const iso = (fecha) => {
  const p = (n) => String(n).padStart(2, '0');
  return `${fecha.getFullYear()}-${p(fecha.getMonth() + 1)}-${p(fecha.getDate())}`;
};

function rangoInicial() {
  const hasta = new Date();
  const desde = new Date();
  desde.setDate(desde.getDate() - 89);
  return { desde: iso(desde), hasta: iso(hasta) };
}

export default function SesionesRegistradas() {
  // Filtros y página en la URL: F5 o Atrás vuelven al mismo listado (H32).
  const [filtros, setFiltros] = useFiltrosEnUrl({
    ...rangoInicial(), id_paciente: '', terapeuta: 'mias', estado: '', pagina: 1,
  });
  const [idDetalle, setIdDetalle] = useState(null);
  const [idEvolucion, setIdEvolucion] = useState(null);
  const [edicion, setEdicion] = useState(null); // null | { sesion, paciente }
  const [aviso, setAviso] = useState('');

  const pacientes = usePeticion(listarPacientes, []);
  const listado = usePeticion(
    () => listarSesionesRegistradas({ ...filtros, por_pagina: POR_PAGINA }),
    [filtros.desde, filtros.hasta, filtros.id_paciente, filtros.terapeuta, filtros.estado, filtros.pagina],
  );

  const cambiar = (clave) => (evento) => {
    const valor = evento?.target?.value ?? evento;
    setFiltros((f) => ({ ...f, [clave]: valor, pagina: 1 }));
  };

  // Con «Mis sesiones» solo se ofrecen los pacientes asignados a quien consulta
  // (los de otra terapeuta siempre darían cero). Se conserva el ya elegido.
  const opcionesPaciente = useMemo(() => (pacientes.datos?.pacientes ?? []).filter(
    (p) => filtros.terapeuta !== 'mias' || p.asignado_a_mi !== false || String(p.id) === String(filtros.id_paciente),
  ), [pacientes.datos, filtros.terapeuta, filtros.id_paciente]);
  const datos = listado.datos;
  const rangoInvalido = filtros.desde && filtros.hasta && filtros.desde > filtros.hasta;

  const columnas = [
    {
      clave: 'fecha', etiqueta: 'Fecha', ancho: 110,
      render: (s) => <Box component="span" sx={{ fontWeight: 600 }}>{formatearFecha(s.fecha)}</Box>,
    },
    { clave: 'hora', etiqueta: 'Hora', ancho: 70, render: (s) => s.hora_inicio?.slice(0, 5) },
    {
      clave: 'paciente', etiqueta: 'Paciente',
      render: (s) => (
        <PersonCell
          nombre={s.paciente.nombre_completo}
          meta={s.companero ? `Dupla con ${s.companero.nombre_completo}` : s.paciente.nro_historia}
        />
      ),
    },
    {
      clave: 'terapeuta', etiqueta: 'Atendió', ancho: 170,
      render: (s) => (
        <span className="texto-libre">
          {s.terapeuta?.nombre_completo ?? '—'}
        </span>
      ),
    },
    {
      clave: 'estado', etiqueta: 'Estado', ancho: 130,
      // La misma etapa que el Panel y el detalle: antes esta lista decía
      // «Realizada» y el Panel «Por registrar» para la misma sesión
      // (usabilidad, terapeuta).
      render: (s) => <SesionEstadoChip {...estadoVisible(s)} />,
    },
  ];

  const recargar = () => { listado.recargar(); };

  return (
    <AppLayout
      titulo="Sesiones registradas"
      subtitulo={datos ? `${datos.total} ${datos.total === 1 ? 'sesión' : 'sesiones'} en el período` : 'Consulta de lo ya ocurrido'}
    >
      <Box
        sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: 1.5, mb: 2.5 }}
      >
        <CampoTexto id="filtro-desde" etiqueta="Desde" tipo="date" tabular valor={filtros.desde} onChange={cambiar('desde')} inputProps={{ max: iso(new Date()) }} />
        <CampoTexto id="filtro-hasta" etiqueta="Hasta" tipo="date" tabular valor={filtros.hasta} onChange={cambiar('hasta')} inputProps={{ max: iso(new Date()) }} />
        <CampoTexto id="filtro-paciente" etiqueta="Paciente" select valor={filtros.id_paciente} onChange={cambiar('id_paciente')}>
          <MenuItem value="">Todos</MenuItem>
          {opcionesPaciente.map((p) => (
            <MenuItem key={p.id} value={String(p.id)} className="texto-libre">{p.nombre_completo} · {p.nro_historia}</MenuItem>
          ))}
        </CampoTexto>
        <CampoTexto id="filtro-terapeuta" etiqueta="Terapeuta" select valor={filtros.terapeuta} onChange={cambiar('terapeuta')}>
          <MenuItem value="mias">Mis sesiones</MenuItem>
          <MenuItem value="todas">Todos los terapeutas</MenuItem>
        </CampoTexto>
        <CampoTexto id="filtro-estado" etiqueta="Estado" select valor={filtros.estado} onChange={cambiar('estado')}>
          <MenuItem value="">Todos</MenuItem>
          {/* El filtro va por cómo se cerró la sesión; una cerrada sin
              calificar figura «Sin registrar» en la columna. */}
          <MenuItem value="completa">Completas</MenuItem>
          <MenuItem value="cortada">Se cortaron</MenuItem>
          <MenuItem value="incompleta">Sin registrar</MenuItem>
          <MenuItem value="ausencia">Ausentes</MenuItem>
        </CampoTexto>
      </Box>

      {rangoInvalido && (
        <Typography variant="body2" color="error" sx={{ mb: 2 }}>
          La fecha inicial es posterior a la final. Corrija el período.
        </Typography>
      )}

      {listado.cargando && !datos && <Cargando texto="Cargando las sesiones..." />}
      {listado.error && <EstadoError error={listado.error} onReintentar={listado.recargar} />}

      {datos && !listado.error && (
        datos.total === 0 ? (
          <EstadoVacio
            titulo="No hay sesiones registradas con estos filtros"
            descripcion="Amplíe el período o quite algún filtro. Las sesiones que todavía no se registraron están en el Panel."
          />
        ) : (
          <>
            <DataTable
              columnas={columnas}
              filas={datos.sesiones}
              onAbrirFila={(s) => setIdDetalle(s.id)}
              etiquetaFila={(s) => `Abrir la sesión de ${s.paciente.nombre_completo}`}
            />
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 1.5, mt: 2 }}>
              <Typography variant="body2" color="text.secondary">
                Página {datos.pagina} de {datos.paginas}
              </Typography>
              <Button variant="outlined" size="small" disabled={datos.pagina <= 1}
                onClick={() => setFiltros((f) => ({ ...f, pagina: f.pagina - 1 }))}>
                Anterior
              </Button>
              <Button variant="outlined" size="small" disabled={datos.pagina >= datos.paginas}
                onClick={() => setFiltros((f) => ({ ...f, pagina: f.pagina + 1 }))}>
                Siguiente
              </Button>
            </Box>
          </>
        )
      )}

      <ModalDetalleSesion
        abierto={Boolean(idDetalle)}
        idSesion={idDetalle}
        onCerrar={() => setIdDetalle(null)}
        onCargarEvolucion={(id) => { setIdDetalle(null); setIdEvolucion(id); }}
        onEditar={(sesion, paciente) => { setIdDetalle(null); setEdicion({ sesion, paciente }); }}
      />
      <ModalCargarEvolucion
        key={idEvolucion ?? 'sin-sesion'}
        abierto={Boolean(idEvolucion)}
        idSesion={idEvolucion}
        onCerrar={() => setIdEvolucion(null)}
        onCargada={(respuesta) => {
          recargar();
          setAviso(respuesta?.mensaje ?? 'Evolución registrada correctamente');
        }}
      />
      {edicion && (
        <ModalEditarSesion
          abierto
          sesion={edicion.sesion}
          paciente={edicion.paciente}
          onCerrar={() => setEdicion(null)}
          onGuardado={(respuesta) => {
            setEdicion(null);
            recargar();
            setAviso(respuesta?.mensaje ?? 'Sesión actualizada correctamente');
          }}
        />
      )}
      <Snackbar open={Boolean(aviso)} autoHideDuration={4000} onClose={() => setAviso('')} message={aviso} />
    </AppLayout>
  );
}

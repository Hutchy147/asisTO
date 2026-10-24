// frontend/src/pages/AdminUsuarios.jsx
// Pantalla del administrador: qué correos pueden ingresar. Alta de cuentas con
// su clave (que se le entrega a la persona), habilitar o deshabilitar y
// restablecer la clave. No muestra datos clínicos.

import { useMemo, useState } from 'react';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Container from '@mui/material/Container';
import MenuItem from '@mui/material/MenuItem';
import Snackbar from '@mui/material/Snackbar';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';

import BarraAdmin from '../components/admin/BarraAdmin.jsx';
import DatosDeEntrega from '../components/admin/DatosDeEntrega.jsx';
import ModalClave from '../components/admin/ModalClave.jsx';
import ModalCuenta from '../components/admin/ModalCuenta.jsx';
import DataTable from '../components/data/DataTable.jsx';
import { Cargando, EstadoError, EstadoVacio } from '../components/estado/index.js';
import DialogoConfirmacion from '../components/modal/DialogoConfirmacion.jsx';
import { useEstadoEnUrl } from '../hooks/useEstadoEnUrl.js';
import { usePeticion } from '../hooks/usePeticion.js';
import {
  cambiarEstadoDeUsuario, listarUsuarios, NOMBRE_DE_ROL,
} from '../services/usuariosService.js';

function estadoDe(cuenta) {
  if (!cuenta.activo) return { etiqueta: 'Deshabilitada', color: 'default' };
  if (cuenta.bloqueado) return { etiqueta: 'Bloqueada 15 min', color: 'warning' };
  return { etiqueta: 'Habilitada', color: 'success' };
}

function ingreso(texto) {
  const m = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/.exec(texto ?? '');
  return m ? `${m[3]}/${m[2]}/${m[1]} ${m[4]}:${m[5]}` : 'Todavía no ingresó';
}

export default function AdminUsuarios() {
  const [rol, setRol] = useEstadoEnUrl('rol', '');
  const [estado, setEstado] = useEstadoEnUrl('estado', '');
  const [busqueda, setBusqueda] = useState('');
  const [busquedaAplicada, setBusquedaAplicada] = useState('');
  const cuentas = usePeticion(
    () => listarUsuarios({ rol, estado, busqueda: busquedaAplicada }),
    [rol, estado, busquedaAplicada],
  );

  const [creando, setCreando] = useState(false);
  const [claveDe, setClaveDe] = useState(null);
  const [aCambiar, setACambiar] = useState(null); // { cuenta, activar }
  const [procesando, setProcesando] = useState(false);
  const [entrega, setEntrega] = useState(null);
  const [aviso, setAviso] = useState('');

  const lista = useMemo(() => cuentas.datos?.usuarios ?? [], [cuentas.datos]);

  const confirmarEstado = async () => {
    setProcesando(true);
    try {
      const respuesta = await cambiarEstadoDeUsuario(aCambiar.cuenta.id, aCambiar.activar);
      setAviso(respuesta?.mensaje ?? 'Listo.');
      cuentas.recargar();
    } catch (error) {
      setAviso(error.message);
    } finally {
      setACambiar(null);
      setProcesando(false);
    }
  };

  const columnas = [
    {
      clave: 'nombre', etiqueta: 'Persona', truncar: true,
      render: (c) => (
        <Box>
          <span className="texto-libre">{c.nombre_completo}{c.es_usted ? ' (usted)' : ''}</span>
          {c.perfil && (
            <Typography variant="caption" color="text.secondary" component="div" className="texto-libre">{c.perfil}</Typography>
          )}
        </Box>
      ),
    },
    { clave: 'email', etiqueta: 'Correo', truncar: true, render: (c) => <span className="texto-libre">{c.email}</span> },
    { clave: 'rol', etiqueta: 'Rol', ancho: 150, render: (c) => NOMBRE_DE_ROL[c.rol] ?? c.rol },
    {
      clave: 'estado', etiqueta: 'Estado', ancho: 160,
      render: (c) => {
        const e = estadoDe(c);
        return <Chip size="small" color={e.color} label={e.etiqueta} />;
      },
    },
    { clave: 'ultimo', etiqueta: 'Último ingreso', ancho: 160, render: (c) => <span className="tabular">{ingreso(c.ultimo_ingreso)}</span> },
    {
      clave: 'acciones', etiqueta: '', ancho: 330, alinear: 'right',
      render: (c) => (
        <Stack direction="row" spacing={1} justifyContent="flex-end">
          <Button size="small" variant="text" color="inherit" sx={{ whiteSpace: 'nowrap' }} onClick={() => setClaveDe(c)}
            aria-label={`Restablecer la contraseña de ${c.nombre_completo}`}>
            Restablecer contraseña
          </Button>
          {!c.es_usted && (
            <Button
              size="small" variant="outlined" color={c.activo ? 'inherit' : 'primary'} sx={{ whiteSpace: 'nowrap' }}
              aria-label={`${c.activo ? 'Deshabilitar' : 'Habilitar'} a ${c.nombre_completo}`}
              onClick={() => setACambiar({ cuenta: c, activar: !c.activo })}
            >
              {c.activo ? 'Deshabilitar' : 'Habilitar'}
            </Button>
          )}
        </Stack>
      ),
    },
  ];

  return (
    <Box sx={{ minHeight: '100vh' }}>
      <BarraAdmin activa="usuarios" />

      <Container maxWidth="lg" sx={{ py: 4 }}>
        <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 2, mb: 3, flexWrap: 'wrap' }}>
          <Box sx={{ flex: 1, minWidth: 260 }}>
            <Typography variant="h4">Cuentas de acceso</Typography>
            <Typography variant="body2" color="text.secondary">
              Solo pueden ingresar los correos que figuran acá y están habilitados. Cargue el correo
              y una contraseña, y entréguesela a la persona.
            </Typography>
          </Box>
          <Button variant="contained" onClick={() => setCreando(true)}>Nueva cuenta</Button>
        </Box>

        <Box
          component="form"
          onSubmit={(e) => { e.preventDefault(); setBusquedaAplicada(busqueda.trim()); }}
          sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'center', mb: 2 }}
        >
          <TextField
            size="small" sx={{ minWidth: 280 }} label="Buscar" placeholder="Nombre, apellido o correo"
            value={busqueda}
            onChange={(e) => {
              setBusqueda(e.target.value);
              if (!e.target.value.trim()) setBusquedaAplicada('');
            }}
          />
          <TextField
            select size="small" label="Rol" sx={{ minWidth: 190 }} value={rol}
            SelectProps={{ displayEmpty: true }} InputLabelProps={{ shrink: true }}
            onChange={(e) => setRol(e.target.value)}
          >
            <MenuItem value="">Todos los roles</MenuItem>
            {Object.entries(NOMBRE_DE_ROL).map(([clave, nombre]) => <MenuItem key={clave} value={clave}>{nombre}</MenuItem>)}
          </TextField>
          <TextField
            select size="small" label="Estado" sx={{ minWidth: 190 }} value={estado}
            SelectProps={{ displayEmpty: true }} InputLabelProps={{ shrink: true }}
            onChange={(e) => setEstado(e.target.value)}
          >
            <MenuItem value="">Todas</MenuItem>
            <MenuItem value="activas">Habilitadas</MenuItem>
            <MenuItem value="deshabilitadas">Deshabilitadas</MenuItem>
          </TextField>
          <Button type="submit" variant="outlined">Buscar</Button>
        </Box>

        {cuentas.cargando && !cuentas.datos && <Cargando texto="Cargando las cuentas..." />}
        {cuentas.error && <EstadoError error={cuentas.error} onReintentar={cuentas.recargar} />}
        {cuentas.datos && !cuentas.error && (
          lista.length === 0 ? (
            <EstadoVacio titulo="No hay cuentas para mostrar" descripcion="Modifique la búsqueda o los filtros." />
          ) : (
            <>
              <DataTable columnas={columnas} filas={lista} claveFila={(c) => c.id} />
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
                {lista.length} {lista.length === 1 ? 'cuenta' : 'cuentas'}. Deshabilitar una cuenta le impide
                ingresar y cierra sus sesiones abiertas; no borra nada de lo que hizo.
              </Typography>
            </>
          )
        )}
      </Container>

      <ModalCuenta
        key={`cuenta-${creando}`}
        abierto={creando}
        onCerrar={() => setCreando(false)}
        onCreada={(respuesta) => {
          cuentas.recargar();
          setEntrega({
            titulo: 'Cuenta creada',
            persona: `${respuesta.usuario.nombre_completo} · ${NOMBRE_DE_ROL[respuesta.usuario.rol]}`,
            email: respuesta.usuario.email,
            contrasena: respuesta.contrasena,
          });
        }}
      />
      <ModalClave
        key={`clave-${claveDe?.id ?? 'ninguna'}`}
        abierto={Boolean(claveDe)}
        cuenta={claveDe}
        onCerrar={() => setClaveDe(null)}
        onRestablecida={(respuesta) => {
          cuentas.recargar();
          setEntrega({
            titulo: 'Contraseña restablecida',
            persona: `${respuesta.usuario.nombre_completo} · sus sesiones abiertas se cerraron`,
            email: respuesta.usuario.email,
            contrasena: respuesta.contrasena,
          });
        }}
      />
      <DatosDeEntrega datos={entrega} onCerrar={() => setEntrega(null)} />

      <DialogoConfirmacion
        abierto={Boolean(aCambiar)}
        titulo={aCambiar?.activar ? '¿Habilitar esta cuenta?' : '¿Deshabilitar esta cuenta?'}
        etiquetaConfirmar={aCambiar?.activar ? 'Habilitar' : 'Deshabilitar'}
        etiquetaProcesando="Guardando…"
        peligro={aCambiar ? !aCambiar.activar : false}
        procesando={procesando}
        onConfirmar={confirmarEstado}
        onCancelar={() => setACambiar(null)}
      >
        {aCambiar?.activar ? (
          <>
            <strong>{aCambiar?.cuenta.nombre_completo}</strong> ({aCambiar?.cuenta.email}) podrá volver a
            ingresar con su contraseña.
          </>
        ) : (
          <>
            <strong>{aCambiar?.cuenta.nombre_completo}</strong> ({aCambiar?.cuenta.email}) dejará de poder
            ingresar y se cerrarán sus sesiones abiertas. Lo que cargó se conserva.
            {aCambiar?.cuenta.pacientes_a_cargo > 0 && (
              <>
                {' '}<strong>Tiene {aCambiar.cuenta.pacientes_a_cargo}{' '}
                {aCambiar.cuenta.pacientes_a_cargo === 1 ? 'paciente asignado' : 'pacientes asignados'}</strong>:
                reasígnelos desde «Asignaciones» para que alguien pueda registrar sus sesiones.
              </>
            )}
          </>
        )}
      </DialogoConfirmacion>

      <Snackbar open={Boolean(aviso)} autoHideDuration={6000} onClose={() => setAviso('')} message={aviso} />
    </Box>
  );
}

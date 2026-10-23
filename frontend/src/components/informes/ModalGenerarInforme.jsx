// frontend/src/components/informes/ModalGenerarInforme.jsx
// Pide tipo y período y genera el informe. Si ya hay un borrador de ese
// período, generar lo reemplaza: el diálogo lo avisa antes de confirmar.

import { useMemo, useState } from 'react';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import FormControlLabel from '@mui/material/FormControlLabel';
import MenuItem from '@mui/material/MenuItem';
import Switch from '@mui/material/Switch';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';

import { Aviso } from '../estado/index.js';
import { TIPOS_INFORME, generarInforme } from '../../services/informesService.js';

const pad = (n) => String(n).padStart(2, '0');

function opcionesSemestre() {
  const hoy = new Date();
  const anio = hoy.getFullYear();
  // Entre enero y junio el segundo semestre del año todavía no empezó: no se
  // ofrece (y no queda elegido por omisión).
  const semestreActual = hoy.getMonth() < 6 ? 1 : 2;
  const lista = [];
  for (const a of [anio, anio - 1]) {
    for (const s of [2, 1]) {
      if (a === anio && s > semestreActual) continue;
      lista.push({ valor: `${a}-S${s}`, etiqueta: `${s === 1 ? 'Primer' : 'Segundo'} semestre de ${a}` });
    }
  }
  return lista;
}

export default function ModalGenerarInforme({
  abierto, idPaciente, iaDisponible, hayPuedePti = true, borradores = [],
  tipoInicial = 'mensual', periodoInicial = '', onCerrar, onGenerado,
}) {
  const hoy = new Date();
  const mesActual = `${hoy.getFullYear()}-${pad(hoy.getMonth() + 1)}`;
  const [tipo, setTipo] = useState(tipoInicial);
  const [mes, setMes] = useState(tipoInicial === 'mensual' && periodoInicial ? periodoInicial : mesActual);
  const [semestre, setSemestre] = useState(
    tipoInicial === 'semestral' && periodoInicial ? periodoInicial : opcionesSemestre()[0].valor,
  );
  const [usarIa, setUsarIa] = useState(true);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState(null);

  const semestres = useMemo(opcionesSemestre, []);
  const periodo = tipo === 'mensual' ? mes : tipo === 'semestral' ? semestre : 'pti';
  const reemplaza = borradores.some((b) => b.tipo === tipo && b.periodo === periodo);
  const mesInvalido = tipo === 'mensual' && (!/^\d{4}-\d{2}$/.test(mes) || mes > mesActual);

  const generar = async () => {
    setEnviando(true);
    setError(null);
    try {
      const resultado = await generarInforme(idPaciente, { tipo, periodo, usar_ia: iaDisponible && usarIa });
      onGenerado(resultado);
    } catch (fallo) {
      setError(fallo);
    } finally {
      setEnviando(false);
    }
  };

  return (
    <Dialog open={abierto} onClose={enviando ? undefined : onCerrar} PaperProps={{ sx: { width: 520, maxWidth: '95vw' } }}>
      <Box sx={{ px: 3, pt: 2.5 }}>
        <Typography variant="h5">Generar informe</Typography>
      </Box>
      <DialogContent sx={{ px: 3, py: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
        {error && <Aviso severidad="error">{error.message}</Aviso>}
        <TextField id="informe-tipo" select label="Tipo de informe" size="small" value={tipo} onChange={(e) => setTipo(e.target.value)}>
          {TIPOS_INFORME.filter((t) => t.valor !== 'pti' || hayPuedePti).map((t) => (
            <MenuItem key={t.valor} value={t.valor}>{t.etiqueta}</MenuItem>
          ))}
        </TextField>
        {tipo === 'mensual' && (
          <TextField
            id="informe-mes" label="Mes" type="month" size="small" value={mes} InputLabelProps={{ shrink: true }}
            onChange={(e) => setMes(e.target.value)} inputProps={{ max: mesActual }}
            error={mesInvalido} helperText={mesInvalido ? 'Elija un mes que ya haya empezado.' : ' '}
          />
        )}
        {tipo === 'semestral' && (
          <TextField id="informe-semestre" select label="Semestre" size="small" value={semestre} onChange={(e) => setSemestre(e.target.value)}>
            {semestres.map((s) => <MenuItem key={s.valor} value={s.valor}>{s.etiqueta}</MenuItem>)}
          </TextField>
        )}
        {tipo === 'pti' && (
          <Typography variant="body2" color="text.secondary">
            El plan terapéutico integral (PTI) se arma con la información del ingreso del paciente.
          </Typography>
        )}
        {/* Sin IA configurada no se ofrece nada: un interruptor apagado que decía
            «no configurada» asustaba a quien no sabía qué era (usabilidad). */}
        {iaDisponible && (
          <FormControlLabel
            control={<Switch checked={usarIa} onChange={(e) => setUsarIa(e.target.checked)} />}
            label="Redactar con inteligencia artificial"
          />
        )}
        <Typography variant="body2" color="text.secondary">
          {iaDisponible && usarIa
            ? 'Se envía a un proveedor externo el resumen del período, sin el nombre del paciente. Siempre queda como borrador para que usted lo revise.'
            : 'Se arma un borrador con la plantilla del centro a partir de los registros del período. Usted lo revisa antes de publicarlo.'}
        </Typography>
        {reemplaza && (
          <Aviso severidad="warning">
            Ya existe un borrador de este período. Al generar, se reemplaza su contenido por uno nuevo.
          </Aviso>
        )}
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2.5, gap: 1 }}>
        <Button variant="outlined" onClick={onCerrar} disabled={enviando}>Cancelar</Button>
        <Button variant="contained" onClick={generar} disabled={enviando || mesInvalido}
          startIcon={enviando ? <CircularProgress size={16} color="inherit" /> : null}>
          {enviando ? 'Generando…' : reemplaza ? 'Regenerar borrador' : 'Generar'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

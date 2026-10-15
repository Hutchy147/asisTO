// frontend/src/services/agendaRecurrenteService.js
// Agenda semanal recurrente (Entrega 3). Contrato: docs/api-agenda-recurrente.md

import { del, get, post } from './api.js';

export const SEMANAS_POR_DEFECTO = 4;
export const SEMANAS_MAXIMAS = 8;

export const DIAS_SEMANA = [
  { valor: 1, etiqueta: 'Lunes' },
  { valor: 2, etiqueta: 'Martes' },
  { valor: 3, etiqueta: 'Miércoles' },
  { valor: 4, etiqueta: 'Jueves' },
  { valor: 5, etiqueta: 'Viernes' },
];

/** Turnos de la semana de la terapeuta. -> { plantillas, total } */
export function listarAgendaSemanal() {
  return get('/agenda-recurrente');
}

export function crearTurno({ id_paciente, dia_semana, hora_inicio, hora_fin }) {
  return post('/agenda-recurrente', { id_paciente, dia_semana, hora_inicio, hora_fin: hora_fin || null });
}

export function quitarTurno(id) {
  return del(`/agenda-recurrente/${id}`);
}

/** -> { desde, hasta, semanas, creadas, existentes, omitidas: [{fecha, hora_inicio, paciente, motivo}] } */
export function generarAgenda(semanas = SEMANAS_POR_DEFECTO) {
  return post('/agenda-recurrente/generar', { semanas });
}

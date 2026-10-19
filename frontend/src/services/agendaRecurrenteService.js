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

/**
 * Crea un turno. Con id_paciente_2 crea una dupla (una terapeuta, dos
 * pacientes en el mismo horario). -> { turno, companero?, id_dupla?, mensaje }
 */
export function crearTurno({ id_paciente, id_paciente_2, dia_semana, hora_inicio, hora_fin }) {
  const cuerpo = { id_paciente, dia_semana, hora_inicio, hora_fin: hora_fin || null };
  if (id_paciente_2) cuerpo.id_paciente_2 = id_paciente_2;
  return post('/agenda-recurrente', cuerpo);
}

/** Suma un compañero a un turno individual, formando una dupla. */
export function sumarCompanero(idTurno, idPaciente) {
  return post(`/agenda-recurrente/${idTurno}/companero`, { id_paciente: idPaciente });
}

/** Con dupla = true quita los dos turnos; si no, solo el indicado. */
export function quitarTurno(id, { dupla = false } = {}) {
  return del(`/agenda-recurrente/${id}${dupla ? '?dupla=1' : ''}`);
}

/** -> { desde, hasta, semanas, creadas, existentes, omitidas: [{fecha, hora_inicio, paciente, motivo}] } */
export function generarAgenda(semanas = SEMANAS_POR_DEFECTO) {
  return post('/agenda-recurrente/generar', { semanas });
}

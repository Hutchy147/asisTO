// frontend/src/services/familiaresService.js
// Vínculo familiar–paciente (Entrega 4). Contrato: docs/api-familiares.md

import { get, post } from './api.js';

/** Familiares vinculados al paciente. -> { id_paciente, familiares, total } */
export function listarFamiliaresDePaciente(idPaciente) {
  return get(`/pacientes/${idPaciente}/familiares`);
}

/** Cuentas de familiar sin vincular a este paciente. -> { familiares } */
export function listarCandidatos(idPaciente, busqueda = '') {
  const consulta = busqueda ? `?q=${encodeURIComponent(busqueda)}` : '';
  return get(`/pacientes/${idPaciente}/familiares/candidatos${consulta}`);
}

/** Vincula una cuenta existente. -> { familiar, mensaje } */
export function vincularExistente(idPaciente, idFamiliar) {
  return post(`/pacientes/${idPaciente}/familiares`, { id_familiar: idFamiliar });
}

/**
 * Crea la cuenta y la vincula.
 * -> { familiar, mensaje, contrasena_temporal } (la contraseña se ve una sola vez)
 */
export function crearYVincular(idPaciente, datos) {
  return post(`/pacientes/${idPaciente}/familiares`, {
    nombre: datos.nombre,
    apellido: datos.apellido,
    email: datos.email,
    parentesco: datos.parentesco || null,
    telefono: datos.telefono || null,
  });
}

/** Quita el acceso del familiar al paciente (la cuenta se conserva). */
export function desvincularFamiliar(idPaciente, idFamiliar) {
  return post(`/pacientes/${idPaciente}/familiares/${idFamiliar}/desvinculacion`, {});
}

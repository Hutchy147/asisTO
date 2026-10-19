// frontend/src/services/ingresoService.js
// Flujo de ingreso e historia clínica (Entrega 4). Contrato: docs/api-ingreso.md

import { get, post, put } from './api.js';

/** Estado del ingreso y formulario de cada etapa. -> { ingreso | null, etapas, minimo_objetivos, objetivos_activos } */
export function obtenerIngreso(idPaciente) {
  return get(`/pacientes/${idPaciente}/ingreso`);
}

export function iniciarIngreso(idPaciente) {
  return post(`/pacientes/${idPaciente}/ingreso`, {});
}

/** `respuestas`: { clave: valor }. Un valor vacío borra la respuesta. */
export function guardarEtapa(idPaciente, etapa, respuestas) {
  return put(`/pacientes/${idPaciente}/ingreso/etapas/${etapa}`, { respuestas });
}

export function cerrarEtapa(idPaciente, etapa) {
  return post(`/pacientes/${idPaciente}/ingreso/etapas/${etapa}/cierre`, {});
}

export function reabrirEtapa(idPaciente, etapa) {
  return post(`/pacientes/${idPaciente}/ingreso/etapas/${etapa}/reapertura`, {});
}

export function completarIngreso(idPaciente) {
  return post(`/pacientes/${idPaciente}/ingreso/completado`, {});
}

/** Historia clínica generada al completar el ingreso. */
export function obtenerHistoriaClinica(idPaciente) {
  return get(`/pacientes/${idPaciente}/historia-clinica`);
}

// --- Configuración del formulario (administrador) ---

export function listarCamposDeIngreso() {
  return get('/admin/ingreso/campos');
}

export function crearCampoDeIngreso(datos) {
  return post('/admin/ingreso/campos', datos);
}

export function editarCampoDeIngreso(id, datos) {
  return put(`/admin/ingreso/campos/${id}`, datos);
}

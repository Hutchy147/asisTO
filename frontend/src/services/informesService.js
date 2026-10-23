// frontend/src/services/informesService.js
// Informes del tratamiento (Entrega 6). Contrato: docs/api-informes.md

import { construirQuery, del, descargarArchivo, get, post, put } from './api.js';

export const TIPOS_INFORME = [
  { valor: 'mensual', etiqueta: 'Informe mensual' },
  { valor: 'semestral', etiqueta: 'Informe semestral' },
  { valor: 'pti', etiqueta: 'PTI (plan terapéutico integral)' },
];

export const ETIQUETA_ESTADO_INFORME = {
  borrador: 'Borrador',
  final: 'Publicado',
  reemplazado: 'Reemplazado',
};

/** Historial de un paciente. -> { paciente, informes, total, ia_disponible } */
export const listarInformesDePaciente = (idPaciente) => get(`/pacientes/${idPaciente}/informes`);

/** Un informe con su contenido. */
export const obtenerInforme = (idInforme) => get(`/informes/${idInforme}`);

/** Diarios del período, antes de generar. */
export const obtenerDiariosDelPeriodo = (idPaciente, tipo, periodo) =>
  get(`/pacientes/${idPaciente}/informes/diarios${construirQuery({ tipo, periodo })}`);

/** Diarios del período de un informe ya creado. */
export const obtenerDiariosDeInforme = (idInforme) => get(`/informes/${idInforme}/diarios`);

/** Genera (o regenera el borrador de) un informe. */
export const generarInforme = (idPaciente, { tipo, periodo, usar_ia }) =>
  post(`/pacientes/${idPaciente}/informes`, { tipo, periodo, usar_ia });

export const guardarInforme = (idInforme, contenido) => put(`/informes/${idInforme}`, { contenido });
export const publicarInforme = (idInforme) => post(`/informes/${idInforme}/publicacion`);
export const corregirInforme = (idInforme) => post(`/informes/${idInforme}/correccion`);
export const descartarInforme = (idInforme) => del(`/informes/${idInforme}`);

export const descargarPdfInforme = (idInforme) => descargarArchivo(`/informes/${idInforme}/pdf`);

/** Control mensual. `mes` AAAA-MM; sin él, el mes en curso. */
export const obtenerControlMensual = (mes) => get(`/informes/control${construirQuery({ mes })}`);

// frontend/src/services/usuariosService.js
// Cuentas de acceso, solo para el administrador. Contrato: docs/api-usuarios.md

import { construirQuery, get, post, put } from './api.js';

/** Nombre de cada rol para una persona, no la clave interna. */
export const NOMBRE_DE_ROL = {
  terapeuta: 'Terapeuta',
  rrhh: 'Recursos Humanos',
  admin: 'Administrador',
  familiar: 'Familiar',
  paciente: 'Paciente',
};

/** Roles que se dan de alta desde la pantalla (el paciente se vincula desde su ficha). */
export const ROLES_CREABLES = ['terapeuta', 'rrhh', 'familiar', 'admin'];

/** -> { usuarios: [...], total } */
export function listarUsuarios({ rol = '', busqueda = '', estado = '' } = {}) {
  return get(`/admin/usuarios${construirQuery({ rol, busqueda, estado })}`);
}

/** Una clave al azar que cumple la política y se dicta sin confusiones. */
export function obtenerContrasenaSugerida() {
  return get('/admin/usuarios/contrasena-sugerida');
}

/** -> { usuario, mensaje } */
export function crearUsuario(datos) {
  return post('/admin/usuarios', datos);
}

export function cambiarEstadoDeUsuario(idUsuario, activo) {
  return put(`/admin/usuarios/${idUsuario}/estado`, { activo });
}

export function restablecerContrasenaDeUsuario(idUsuario, contrasena) {
  return put(`/admin/usuarios/${idUsuario}/contrasena`, { contrasena });
}

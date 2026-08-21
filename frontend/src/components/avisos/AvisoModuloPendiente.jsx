// frontend/src/components/avisos/AvisoModuloPendiente.jsx

import Aviso from '../estado/Aviso.jsx';
import { CAPACIDADES } from '../../config/entregas.js';

/**
 * El modulo de este rol llega en una entrega posterior.
 *
 * Existe para que una demostracion con esos roles no parezca rota. Un
 * dashboard vacio sin explicacion se lee como una pantalla que fallo; con
 * el aviso se lee como funcionalidad que todavia no toca.
 *
 * EL NUMERO DE ENTREGA SALE DE LA TABLA, no de aca. Hasta el 2026-08-21 este
 * archivo tenia su propia lista —`rrhh: 'Entrega 2'`, `familiar: 'Entrega 3'`,
 * `paciente: 'Entrega 3'`— y era una SEGUNDA declaracion de lo mismo. Ya habia
 * divergido: decia que RRHH llega en la 2 mientras el User Story Map lo ubica
 * en la 4. Es el defecto que la tabla unica existe para evitar, encontrado en
 * el propio codigo al conectarla.
 *
 * Lo que se conserva aca es el TEXTO de que hace cada modulo, que es copy y no
 * un dato: no tiene sentido meterlo en una tabla de configuracion.
 */
const CAPACIDAD_POR_ROL = {
  rrhh: {
    capacidad: 'rrhh.consulta',
    detalle: 'Verificación de asistencias, observaciones técnicas y exportación.',
  },
  familiar: {
    capacidad: 'familiar.portal',
    detalle: 'Seguimiento del paciente vinculado, notas de campo y notificaciones.',
  },
  paciente: {
    capacidad: 'paciente.portal',
    detalle: 'Consulta de tus objetivos y tu progreso.',
  },
};

export default function AvisoModuloPendiente({ rol }) {
  const info = CAPACIDAD_POR_ROL[rol];
  if (!info) return null;

  const entrega = CAPACIDADES[info.capacidad]?.entrega;
  const titulo = entrega
    ? `Este módulo llega en la Entrega ${entrega}`
    : 'Este módulo llega en una entrega posterior';

  return (
    <Aviso severidad="info" titulo={titulo}>
      {info.detalle} Tu usuario y tus permisos ya funcionan: lo que falta es
      la pantalla, no el acceso.
    </Aviso>
  );
}

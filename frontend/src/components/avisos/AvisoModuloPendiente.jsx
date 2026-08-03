// frontend/src/components/avisos/AvisoModuloPendiente.jsx

import Aviso from '../estado/Aviso.jsx';

/**
 * El modulo de este rol llega en una entrega posterior.
 *
 * Existe para que una demostracion con esos roles no parezca rota. Un
 * dashboard vacio sin explicacion se lee como una pantalla que fallo; con
 * el aviso se lee como funcionalidad que todavia no toca.
 */
const ENTREGA_POR_ROL = {
  rrhh: {
    entrega: 'Entrega 2',
    detalle: 'Verificación de asistencias, observaciones técnicas y exportación.',
  },
  familiar: {
    entrega: 'Entrega 3',
    detalle: 'Seguimiento del paciente vinculado, notas de campo y notificaciones.',
  },
  paciente: {
    entrega: 'Entrega 3',
    detalle: 'Consulta de tus objetivos y tu progreso.',
  },
};

export default function AvisoModuloPendiente({ rol }) {
  const info = ENTREGA_POR_ROL[rol];
  if (!info) return null;

  return (
    <Aviso severidad="info" titulo={`Este módulo llega en la ${info.entrega}`}>
      {info.detalle} Tu usuario y tus permisos ya funcionan: lo que falta es
      la pantalla, no el acceso.
    </Aviso>
  );
}

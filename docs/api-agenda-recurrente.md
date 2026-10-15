# API de agenda semanal recurrente — Entrega 3

Los turnos fijos de la semana de una terapeuta ("los lunes a las 9 viene este paciente") y la generación de sesiones a partir de ellos. Solo rol terapeuta; cada una ve y modifica la suya. Tabla `agenda_recurrente` (la plantilla **no** es una sesión: no cuenta como asistencia).

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/api/agenda-recurrente` | `{plantillas: [{id, id_paciente, paciente, dia_semana, dia, hora_inicio, hora_fin}], total}` |
| POST | `/api/agenda-recurrente` | Crea un turno `{id_paciente, dia_semana (1=lunes…5=viernes), hora_inicio, hora_fin?}`. 201 |
| DELETE | `/api/agenda-recurrente/<id>` | Quita el turno (queda inactivo). Las sesiones ya generadas no se tocan. 403 si es de otra terapeuta, 404 si no existe |
| POST | `/api/agenda-recurrente/generar` | `{semanas?: 1..8, default 4}` → `{desde, hasta, semanas, creadas, existentes, omitidas: [{fecha, hora_inicio, paciente, motivo}]}` |

## Reglas
- Sin `hora_fin`, el turno dura 45 minutos. `hora_fin` debe ser posterior a `hora_inicio` (también un CHECK en la tabla, igual que `dia_semana` entre 1 y 5).
- El paciente tiene que estar activo y asignado a la terapeuta (regla 8 aplicada a la plantilla). Dos turnos de la misma terapeuta no pueden pisarse el mismo día (400, `campo: hora_inicio`). Máximo 60 turnos.
- `generar` recorre desde **hoy** (inclusive) y agenda una sesión por cada fecha que cae en el día del turno, en estado `incompleta`, **a través de `registrar_sesion` → `p_registrar_sesion`**: la superposición, el paciente de baja y la asignación los sigue decidiendo la base. Lo que no se pudo agendar vuelve en `omitidas` con el motivo; no aborta el resto.
- Es idempotente: una sesión que ya existe (mismo paciente, fecha y hora) cuenta como `existente`. Si existe pero es de otra terapeuta, va a `omitidas`.
- Sin turnos cargados, `generar` responde 409.

## Decisiones
- Las reglas de la **plantilla** (día hábil, superposición entre turnos, asignación) están en el servicio y no en la base, por el mismo criterio de la norma de agenda (ver `api-sesiones-evoluciones.md`): son política de agenda, y las reglas de integridad de las sesiones generadas las aplica la base.
- La agenda recurrente lleva historia de usuario propia (HDU nueva, borrador en la documentación del Sprint 3).

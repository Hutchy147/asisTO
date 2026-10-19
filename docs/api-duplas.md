# API de duplas terapéuticas (Entrega 5)

Una **dupla** es una terapeuta que atiende a **dos pacientes en el mismo horario**. No es trabajo interdisciplinario. No hay tabla de parejas: dos sesiones (o dos turnos de `agenda_recurrente`) que comparten `id_dupla` **son** la dupla; el valor es el id de la primera fila. Las reglas viven en procedimientos almacenados (`p_registrar_dupla`, `p_agregar_a_dupla`, `p_crear_turno_dupla`, `p_sumar_companero_a_turno`) y en los triggers de superposición existentes (sin triggers nuevos).

## Reglas
- Máximo dos sesiones por dupla; las dos son de la **misma terapeuta**, el **mismo día** y el **mismo horario** (hora de fin efectiva incluida). La base lo hace cumplir.
- Las sesiones de una misma dupla **no** cuentan como superposición (ni en el trigger ni en `superposiciones` del reporte de RRHH).
- Los dos pacientes deben estar activos y asignados a la terapeuta; no puede ser el mismo paciente.
- Reprogramar una sesión de la dupla (`PUT /api/sesiones/<id>`) mueve **las dos** en una sola operación; el mensaje lo informa.
- La evolución sigue siendo por paciente y por objetivo; la autoría no cambia.
- Un turno que queda solo (se quitó al compañero) pasa a ser individual y puede recibir otro compañero.
- Las sesiones se crean al generar la agenda; no hay ruta HTTP para crear una dupla suelta.

## Endpoints (terapeuta)
| Método y ruta | Descripción |
|---|---|
| `POST /api/agenda-recurrente` con `id_paciente_2` | Crea el turno dupla. 201 |
| `POST /api/agenda-recurrente/<id>/companero` | Forma la dupla sobre un turno individual. 201 |
| `DELETE /api/agenda-recurrente/<id>?dupla=1` | Quita los dos turnos. Sin `dupla`, solo el indicado. |
| `POST /api/agenda-recurrente/generar` | Agenda cada dupla una vez por fecha; si ya existía la sesión de uno, agrega al otro. |
| `GET /api/sesiones`, `/api/sesiones/hoy`, `/api/sesiones/<id>` | Cada sesión trae `id_dupla` y `companero {id_sesion, id_paciente, nombre_completo}` (nada clínico del compañero). |

## Códigos
400 datos inválidos o regla de negocio · 403 paciente no asignado / turno ajeno · 404 inexistente · 409 turno ya en dupla, o turno duplicado por concurrencia.

## Pantallas
Calendario semanal (capacidad `duplas.vincular`): el turno dupla se dibuja como un solo bloque con los dos nombres; «Compañero de dupla» al crear, «Formar dupla», «Quitar solo a…» y «Quitar la dupla». Panel del día y detalle de sesión muestran «Dupla con…».

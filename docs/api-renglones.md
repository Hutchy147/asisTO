# API de renglones (notas de campo) — Entrega 3

Cada sesión tiene dos listas de renglones de una línea (máx. 160 caracteres, máx. 30 por momento):
`plan` (qué se piensa trabajar) y `registro` (qué pasó). Las reglas viven en la base
(`p_agregar_renglon`, `p_editar_renglon`, `p_cerrar_renglon`, `p_borrar_renglon`).

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/api/sesiones/<id>/renglones` | `{id_sesion, es_propia, plan, registro, arrastre}` |
| POST | `/api/sesiones/<id>/renglones` | Agrega `{momento, texto, destacado?}` |
| PUT | `/api/renglones/<id>` | Edita `{texto?, destacado?}` |
| POST | `/api/renglones/<id>/cierre` | `{cierre: 'hecho'｜'descartado'｜null}` (null reabre). Solo plan |
| DELETE | `/api/renglones/<id>` | Borra |

## Reglas
- Solo el terapeuta de la sesión escribe (403 si no); renglón inexistente → 404; el resto de rechazos → 400 con `campo`.
- `registro` no se admite en sesiones futuras ni en ausencias.
- No se puede marcar ausencia si la sesión ya tiene renglones de registro (el plan se conserva).
- `arrastre`: renglones de plan sin cerrar de sesiones anteriores del mismo paciente y del mismo terapeuta (con `fecha_sesion`).
- `GET /api/sesiones/hoy` agrega `renglones: {plan, registro, arrastre}` (conteos) por sesión.
- `destacado` es booleano (no usa las tablas `etiquetas`).

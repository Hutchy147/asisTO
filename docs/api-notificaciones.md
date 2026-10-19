# API de notificaciones (Entrega 4)

Avisos del tratamiento para la familia. **Emisión** automática desde el servidor; **consulta** solo del rol `familiar` y solo de sus propios avisos.

## Emisión

`p_notificar_paciente(paciente, tipo, texto)` crea un aviso por cada familiar vinculado con cuenta activa que no haya desactivado ese tipo (sin fila en `preferencias_notificacion` el tipo está habilitado). Se llama **después** de confirmar el cambio avisado, en una transacción aparte y con mejor esfuerzo: si falla, queda en el log y el cambio original se mantiene.

| Tipo | Cuándo se emite |
|---|---|
| `nueva_sesion` | Al registrar una sesión con fecha de hoy o anterior (también ausencias, sin decir quién faltó). Las sesiones a futuro y las que genera la agenda recurrente **no** avisan |
| `cambio_objetivo` | Al agregar, modificar (solo si el texto cambia) o archivar un objetivo |
| `informe_generado` | Gancho listo (`notificaciones_service.avisar_informe`) para cuando la Entrega 6 genere informes |

## Consulta (rol `familiar`)

| Método y ruta | Qué hace |
|---|---|
| `GET /api/familiar/notificaciones?tipo=&leida=0\|1&id_paciente=&limite=&desplazamiento=` | `{notificaciones: [{id, id_paciente, paciente, tipo, tipo_etiqueta, mensaje, leida, fecha}], total, no_leidas}`, del más reciente al más antiguo (límite 1 a 100, por omisión 50) |
| `GET /api/familiar/notificaciones/no-leidas` | `{no_leidas}` |
| `POST /api/familiar/notificaciones/<id>/lectura` | Cuerpo `{leida: true\|false}`. 404 si el aviso no es suyo |
| `POST /api/familiar/notificaciones/lectura-masiva` | Marca todos como leídos |
| `GET /api/familiar/notificaciones/preferencias` | Los tres tipos con `habilitada` |
| `PUT /api/familiar/notificaciones/preferencias/<tipo>` | Cuerpo `{habilitada: bool}`. 404 si el tipo no existe, 400 si no es booleano |

Desactivar un tipo corta los avisos nuevos; el historial se conserva.

## Pruebas

`tests/nube/test_notificaciones_api.py` y `tests/nube/ui_notificaciones.py` (cruza dos roles: la terapeuta carga y la familiar ve).

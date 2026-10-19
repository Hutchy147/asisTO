# API del portal familiar (Entrega 4)

Consulta de la evolución por el familiar. Solo rol `familiar` y solo sobre pacientes vinculados a su cuenta (ver `api-familiares.md`). Es una **vista reducida** armada en el servidor, no la respuesta clínica con campos ocultos en el front.

| Método y ruta | Qué hace |
|---|---|
| `GET /api/familiar/pacientes` | Pacientes vinculados: `{pacientes: [{id, nombre_completo, fecha_nacimiento, fecha_alta, estado, fecha_baja}], total}`. `estado`: `en_tratamiento`, `pausa` o `alta` |
| `GET /api/familiar/pacientes/<id>/evolucion?desde=&hasta=` | `{paciente, periodo, objetivos: [{id, descripcion, activo, fecha_archivado, puntos: [{id_sesion, fecha, estado_sesion, valor}], resumen: {calificados, ultimo}}], sesiones: [{id_sesion, fecha, hora_inicio, estado_sesion, valores: [{id_objetivo, objetivo, valor}]}], total_sesiones, total_calificados}` |

## Qué no se envía

Diagnóstico, observaciones de cada evolución, notas de sesión, nombres de terapeutas, motivo de baja, número de historia y obra social. Tampoco promedios: la escala se comunica con palabras.

## Reglas

- Paciente no vinculado o inexistente: 403 (no se revela si existe).
- Solo sesiones con fecha menor o igual a hoy; `periodo.hasta` se recorta a hoy.
- Sin fechas: todo el tratamiento. Con fechas: mismas validaciones que la API clínica (rango invertido o excesivo = 400).
- Desvincular al familiar corta el acceso de inmediato.

## Pruebas

`tests/nube/test_portal_familiar_api.py` y `tests/nube/ui_portal_familiar.py`.

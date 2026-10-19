# API del portal familiar (Entrega 4)

Consulta de la evolución por el familiar. Solo rol `familiar` y solo sobre pacientes vinculados a su cuenta (ver `api-familiares.md`). Es una **vista reducida** armada en el servidor, no la respuesta clínica con campos ocultos en el front.

| Método y ruta | Qué hace |
|---|---|
| `GET /api/familiar/pacientes` | Pacientes vinculados: `{pacientes: [{id, nombre_completo, fecha_nacimiento, fecha_alta, estado, fecha_baja}], total}`. `estado`: `en_tratamiento`, `pausa` o `alta` |
| `GET /api/familiar/pacientes/<id>/evolucion?desde=&hasta=` | `{paciente, periodo, objetivos: [{id, descripcion, activo, fecha_archivado, puntos: [{id_sesion, fecha, estado_sesion, valor}], resumen: {calificados, ultimo}}], sesiones: [{id_sesion, fecha, hora_inicio, estado_sesion, valores: [{id_objetivo, objetivo, valor}]}], total_sesiones, total_calificados}` |

## Informes publicados (Entrega 6)

El familiar lee los informes **publicados** de sus pacientes vinculados. Nunca ve borradores ni versiones reemplazadas, y el informe no muestra el nombre de quien lo redactó: el PDF se firma como «Equipo terapéutico del centro».

| Método y ruta | Qué hace |
|---|---|
| `GET /api/familiar/pacientes/<id>/informes` | `{paciente, informes: [{id, tipo, tipo_etiqueta, periodo, periodo_etiqueta, fecha_desde, fecha_hasta, version, estado, fecha_publicacion}], total}` |
| `GET /api/familiar/pacientes/<id>/informes/<id_informe>` | El informe con su `contenido` |
| `GET /api/familiar/pacientes/<id>/informes/<id_informe>/pdf` | PDF del informe (adjunto) |

- Paciente no vinculado: 403. Informe inexistente, de otro paciente, borrador o reemplazado: 404 (no se distingue).
- Al publicarse un informe se emite el aviso `informe_generado` a los familiares vinculados (ver `api-notificaciones.md`).
- Contrato completo de generación y publicación: `api-informes.md`.

## Qué no se envía

Diagnóstico, observaciones de cada evolución, notas de sesión, nombres de terapeutas, motivo de baja, número de historia y obra social. Tampoco promedios: la escala se comunica con palabras.

## Reglas

- Paciente no vinculado o inexistente: 403 (no se revela si existe).
- Solo sesiones con fecha menor o igual a hoy; `periodo.hasta` se recorta a hoy.
- Sin fechas: todo el tratamiento. Con fechas: mismas validaciones que la API clínica (rango invertido o excesivo = 400).
- Desvincular al familiar corta el acceso de inmediato.

## Pruebas

`tests/nube/test_portal_familiar_api.py` y `tests/nube/ui_portal_familiar.py`.

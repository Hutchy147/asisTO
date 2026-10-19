# API del portal del paciente (Entrega 6, HDU 10)

El paciente con cuenta ve **sus** objetivos y **su** progreso. Solo lectura. Rol `paciente`.

| Método y ruta | Qué hace |
|---|---|
| `GET /api/paciente/mi-progreso?desde=&hasta=` | `{paciente, periodo, objetivos: [{id, descripcion, activo, fecha_archivado, puntos: [{id_sesion, fecha, estado_sesion, valor}], resumen: {calificados, ultimo}}], total_sesiones, total_calificados}` |

## Reglas

- **La identidad sale del token.** El endpoint no recibe ningún id: no hay forma de pedir el progreso de otra persona.
- Es la misma vista reducida que recibe el familiar (`evolucion_reducida`), sin el detalle por sesión: sin diagnóstico, observaciones, notas, nombres de terapeutas, número de historia ni obra social.
- **No incluye informes.** La HDU 10 es objetivos y progreso propio; los informes son un documento del equipo para la familia.
- Solo sesiones ya ocurridas; `periodo.hasta` se recorta a hoy. Sin fechas: todo el tratamiento.
- La escala se comunica con palabras, nunca como número ni promedio.
- Una cuenta de paciente sin ficha asociada recibe 409 con un mensaje que indica comunicarse con el centro. El login del paciente es opcional: un paciente sin cuenta existe como registro clínico y no entra al portal.
- Otros roles: 403.

## Pruebas

`tests/nube/test_portal_paciente_api.py` y `tests/nube/ui_portal_paciente.py`.

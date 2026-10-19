# API de plantillas de objetivos por área (Entrega 5)

Catálogo de textos sugeridos, agrupados por área, que la terapeuta elige al crear un objetivo. Tabla `plantillas_objetivos`. Las reglas viven en procedimientos almacenados (`p_crear_plantilla_objetivo`, `p_editar_plantilla_objetivo`, `p_eliminar_plantilla_objetivo`).

## Reglas
- El texto de la plantilla se **copia** al objetivo y queda editable: el objetivo no guarda ninguna referencia. Editar o quitar una plantilla **no** toca objetivos ya creados.
- Área obligatoria (hasta 120 caracteres) y descripción obligatoria (hasta 700, el mismo tope que un objetivo). Se recortan los espacios de los extremos.
- No puede haber dos plantillas iguales (misma área y misma descripción).
- Las áreas no son una tabla: una plantilla con un área nueva crea el área, y el área desaparece cuando se quita su última plantilla.
- Lee el catálogo la **terapeuta** (para elegir) y el **administrador** (que lo cura). Solo el administrador crea, edita y quita. RRHH, familia y paciente: 403. No es contenido clínico.

## Endpoints
| Método y ruta | Rol | Descripción |
|---|---|---|
| `GET /api/plantillas-objetivos` | terapeuta, admin | `{areas: [{area, plantillas: [{id, descripcion}]}], total}`, áreas en orden alfabético. |
| `POST /api/plantillas-objetivos` | admin | `{area, descripcion}` → 201 `{plantilla}`. |
| `PUT /api/plantillas-objetivos/<id>` | admin | `{area, descripcion}` → `{plantilla}`. |
| `DELETE /api/plantillas-objetivos/<id>` | admin | → `{mensaje}`. |

## Códigos
400 dato faltante, demasiado largo o de tipo inválido (con `campo`: `area` o `descripcion`) · 401 sin sesión · 403 sin permiso · 404 plantilla inexistente · 409 plantilla duplicada.

## Pantallas
Selector **Área** → **Texto sugerido** en «Nuevo objetivo terapéutico» (capacidad `objetivos.plantillas`; solo en el alta) y **Plantillas de objetivos** del administrador, ruta `/admin/plantillas`.

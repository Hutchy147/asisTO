# API de ingreso e historia clínica (Entrega 4)

Flujo de ingreso de un paciente nuevo: **cuatro etapas** (`carpeta`, `evaluacion`,
`entrevista`, `pti`) y generación de la historia clínica del centro. Las reglas
viven en procedimientos almacenados (`p_iniciar_ingreso`, `p_guardar_ingreso_etapa`,
`p_cerrar_ingreso_etapa`, `p_reabrir_ingreso_etapa`, `p_completar_ingreso`).

## Reglas
- Un ingreso por paciente. Solo el **terapeuta asignado** inicia, escribe, cierra y reabre etapas (lo hace cumplir la base).
- Para completar: las 4 etapas cerradas y **al menos 3 objetivos activos**.
- Al completar se guarda una copia (JSON) en `ingresos.historia_clinica`: cambios posteriores al formulario no alteran historias ya generadas.
- Lectura abierta entre terapeutas. El administrador solo configura el formulario y **nunca** lee respuestas. Familia y paciente: 403.
- Los campos del formulario no se borran: se desactivan.

## Endpoints (terapeuta)
| Método y ruta | Descripción |
|---|---|
| `GET /api/pacientes/<id>/ingreso` | Estado del ingreso, etapas con sus campos y valores, objetivos activos y mínimo requerido. `ingreso: null` si no se inició. |
| `POST /api/pacientes/<id>/ingreso` | Inicia el ingreso (201). |
| `PUT /api/pacientes/<id>/ingreso/etapas/<etapa>` | Guarda respuestas: `{"respuestas": {"clave": "valor"}}`. |
| `POST .../etapas/<etapa>/cierre` | Cierra la etapa (exige los obligatorios). |
| `POST .../etapas/<etapa>/reapertura` | Reabre una etapa cerrada. |
| `POST /api/pacientes/<id>/ingreso/completado` | Completa y genera la historia clínica. |
| `GET /api/pacientes/<id>/historia-clinica` | Historia generada (datos, objetivos y respuestas por etapa). |

## Endpoints (administrador)
| Método y ruta | Descripción |
|---|---|
| `GET /api/admin/ingreso/campos` | Etapas y campos (incluye inactivos). |
| `POST /api/admin/ingreso/campos` | Alta de campo: `etapa`, `clave`, `etiqueta`, `ayuda`, `tipo` (`texto`, `texto_largo`, `fecha`, `opcion`), `opciones`, `obligatorio`, `orden`. |
| `PUT /api/admin/ingreso/campos/<id>` | Edita etiqueta, ayuda, orden, opciones, `obligatorio`, `activo`. Clave y tipo no cambian. |

## Códigos
400 datos inválidos o regla de negocio · 401 sin sesión · 403 sin permiso / no asignado · 404 inexistente · 409 estado incompatible (ya cerrada, ya completado).

## Pantallas
Pestaña **Ingreso** de la ficha (capacidad `ingreso.flujo`) e **Formulario de ingreso** del administrador, ruta `/admin/formularios` (`ingreso.configurar`). La historia se imprime con «Imprimir o guardar como PDF».

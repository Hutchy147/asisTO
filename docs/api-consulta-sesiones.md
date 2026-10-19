# API de consulta de sesiones y tendencias (Entrega 5)

Dos lecturas para revisar lo ya registrado: la **lista de sesiones registradas** (filtros y paginación) y la **tendencia por objetivo** con comparación contra el período anterior. Solo rol terapeuta; lectura abierta entre terapeutas (igual que la ficha clínica). Administrador, RRHH, familia y paciente: 403.

## Sesiones registradas
`GET /api/sesiones/registradas`

| Parámetro | Descripción |
|---|---|
| `desde`, `hasta` | Período (AAAA-MM-DD). Sin ninguno: los últimos 90 días. `hasta` nunca pasa de hoy. Rango invertido o de más de 366 días: 400. |
| `id_paciente` | Un paciente. |
| `terapeuta` | `mias` (por defecto) o `todas`. |
| `estado` | `completa`, `incompleta` o `ausencia`. |
| `pagina`, `por_pagina` | Desde 1; `por_pagina` por defecto 20, máximo 50. |

Respuesta: `{desde, hasta, terapeuta, pagina, por_pagina, total, paginas, sesiones: [...]}`, de la más reciente a la más antigua. Cada sesión trae lo de `GET /api/sesiones` (`paciente`, `terapeuta`, `companero`, `tiene_evolucion`, `admite_evolucion`) más `es_propia`.

**Qué es «registrada»:** ya ocurrió (su hora de inicio pasó) y se la cerró como `completa` o `ausencia`, o tiene al menos una evolución cargada. Lo agendado hacia adelante y lo ocurrido sin registro no entra: eso es el Panel.

## Tendencia por objetivo
`GET /api/pacientes/<id>/tendencias?dias=30` — `dias` ∈ {30, 60, 90, 180} (por defecto 30, el ritmo mensual de revisión; otro valor: 400). Compara los últimos `dias` días (hasta hoy) con los `dias` anteriores. Incluye pacientes dados de baja.

Respuesta: `{paciente, dias, periodo, periodo_anterior, objetivos: [{id, descripcion, activo, calificaciones, calificaciones_anterior, nivel_actual, nivel_anterior, tendencia, cambio}]}`.

El criterio vive en `p_tendencia_paciente`:
- **`tendencia`** (dentro del período): con **al menos 4** calificaciones se compara el promedio de la primera mitad con el de la segunda (en orden cronológico; si son impares, la del medio no entra). Diferencia de **media escala o más**: `mejora` / `retrocede`; menos: `se_mantiene`. Con menos de 4: `sin_datos`.
- **`cambio`** (contra el período anterior): con al menos 2 calificaciones en cada uno, mismo umbral: `mejoro` / `retrocedio` / `igual`; si no, `sin_datos`.
- `nivel_*` es la palabra de la escala (1 a 5) más cercana al promedio del período, o `null`. **No se devuelve ningún promedio ni porcentaje.**
- Un objetivo archivado aparece solo si tuvo calificaciones en alguno de los dos períodos; uno activo aparece siempre.

## Códigos
400 parámetro inválido (con `campo`) · 401 sin sesión · 403 sin permiso · 404 paciente inexistente.

## Pantallas
**Sesiones** (`/sesiones`, capacidad `sesiones.consultar`): filtros, tabla paginada y detalle de la sesión (de solo lectura si es de otra terapeuta). **Progreso** de la ficha del paciente, sección «Tendencia por objetivo» (capacidad `evoluciones.tendencias`).

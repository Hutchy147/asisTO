# Contrato de API — RRHH

Base: `/api` · Formato: JSON · Autenticación: `Authorization: Bearer <token>`

**Todos los endpoints de este documento son exclusivos del rol `rrhh`.**

> Los ejemplos de JSON están **copiados de respuestas reales** de la API
> corriendo contra una base descartable, no escritos a mano.

Las convenciones generales (códigos de autenticación, forma de los errores)
son las mismas que en [`api-pacientes-objetivos.md`](api-pacientes-objetivos.md).

Estado: **camino de datos + panel de consulta.** El export no está construido.

La pantalla es `frontend/src/pages/PanelRrhh.jsx`, ruta `/rrhh`, capacidad
`rrhh.consulta` (entrega 2). Es **de sólo lectura**: el módulo no expone
ningún endpoint de escritura.

---

## Qué es RRHH acá

Lleva el recuento de **qué terapeuta atendió a qué paciente** y registra las
**ausencias, del paciente y del terapeuta**, para alimentar la parte
administrativa del centro.

**La facturación no es parte del sistema.**

---

## El límite clínico

RRHH verifica asistencias. **No accede a contenido clínico**: ni evoluciones,
ni notas, ni objetivos, ni diagnóstico. Es un límite duro del proyecto.

**Hoy ese límite no lo sostiene la base.** No hay un usuario de MySQL separado
para RRHH ni `GRANT`s por columna — es el hallazgo **A3**, abierto. Lo que lo
sostiene son tres cosas, todas de código:

1. El blueprint aislado `rrhh_bp`, que no importa ningún servicio clínico.
2. La lista de columnas del `SELECT` de `p_reporte_sesiones_periodo`.
3. `COLUMNAS_REPORTE` en `rrhh_service.py`, que es la tupla sobre la que se
   arma cada fila de la respuesta.

La (3) es la que cierra: **el dict de respuesta se construye recorriendo esa
tupla**, no las claves que vengan de la base. Una columna que el
procedimiento empezara a devolver de más **no saldría** por este camino sin
que alguien la agregue a mano a esa lista.

Lo que **no puede entrar** a ninguna de las dos listas: `sesiones.notas`,
`evoluciones.observaciones`, `objetivos_terapeuticos.descripcion` y
`pacientes.diagnostico`. Si alguna hiciera falta, no es una columna: es un
cambio de alcance de RRHH, y eso es una HDU.

---

## `GET /api/rrhh/reporte-sesiones?desde=&hasta=&id_terapeuta=`

Sesiones del período, con el recuento de ausencias por origen.

| Parámetro | Obligatorio | Notas |
|---|---|---|
| `desde` | **sí** | `AAAA-MM-DD` |
| `hasta` | **sí** | `AAAA-MM-DD` |
| `id_terapeuta` | no | Sin él, todos los terapeutas |

Rango máximo **366 días**, igual que `GET /api/sesiones` y por el mismo
motivo: sin tope se puede pedir "1900 a 2100" y traerse todo de una.

**200 OK**

```json
{
  "desde": "2026-06-17",
  "hasta": "2026-06-25",
  "id_terapeuta": null,
  "mensaje": "Se listaron 4 sesiones en el periodo",
  "resumen": {
    "ausencia_declarable_desde": "2026-09-10",
    "ausencias": {
      "paciente": 1,
      "sin_declarar": 1,
      "terapeuta": 1
    },
    "periodo_anterior_a_ausencia_declarable": true,
    "por_estado": {
      "ausencia": 3,
      "completa": 1
    },
    "total_sesiones": 4
  },
  "sesiones": [
    {
      "ausencia_de": "terapeuta",
      "estado": "ausencia",
      "fecha": "2026-06-17",
      "hora_fin": null,
      "hora_inicio": "11:00",
      "id_sesion": 7,
      "id_terapeuta": 2,
      "nro_historia": "HC-0002",
      "paciente": "Sosa, Valentina",
      "superposiciones": 0,
      "terapeuta": "Moyano, Diego"
    },
    {
      "ausencia_de": null,
      "estado": "completa",
      "fecha": "2026-06-19",
      "hora_fin": "12:00",
      "hora_inicio": "11:00",
      "id_sesion": 13,
      "id_terapeuta": 1,
      "nro_historia": "HC-0004",
      "paciente": "Peralta, Ignacio",
      "superposiciones": 0,
      "terapeuta": "Fernandez, Laura"
    }
  ]
}
```

### Las once columnas de una sesión, y ninguna más

| Campo | Notas |
|---|---|
| `id_sesion` | |
| `fecha` | `AAAA-MM-DD` |
| `hora_inicio` | `HH:MM` |
| `hora_fin` | `HH:MM` o `null` — es NULLABLE, se asume una hora |
| `estado` | `completa`, `incompleta`, `ausencia` |
| `ausencia_de` | `paciente`, `terapeuta` o `null` |
| `id_terapeuta` | Identifica; el nombre solo no alcanza con homónimos |
| `terapeuta` | `Apellido, Nombre` — para leer, no para identificar |
| `paciente` | `Apellido, Nombre` |
| `nro_historia` | Identificador administrativo, no clínico |
| `superposiciones` | Cuántas sesiones del mismo terapeuta pisan ese horario |

`hora_fin` y `ausencia_de` viajan como `null`, no como cadena vacía: en este
reporte la diferencia entre "no declarado" y "declarado vacío" es justamente
lo que hay que conservar.

### El resumen, y por qué tiene tres baldes y no dos

`ausencias` separa **`paciente`**, **`terapeuta`** y **`sin_declarar`**.

`sin_declarar` **no se reparte** entre los otros dos ni se suma a ninguno. Son
las ausencias cargadas antes de que existiera la columna `ausencia_de`
(2026-09-10). Ese dato no está y **no hay forma de reponerlo**: el reporte lo
dice en vez de elegir uno.

`periodo_anterior_a_ausencia_declarable` avisa que el período pedido empieza
antes de esa fecha, o sea que el reparto **puede venir incompleto por origen**.
No invalida el reporte: lo califica.

### Lo que el reporte NO afirma

**`completa` no distingue una declaración de una omisión** en el período
viejo. Hasta el 2026-09-10 el formulario traía ese estado preseleccionado, así
que una sesión en `completa` puede significar "el terapeuta declaró que fue
completa" o "nadie tocó el campo". En `asisto` son 502 de 644 sesiones.

Por eso el resumen da `por_estado` como **recuento** y no como tasa de
asistencia, y no existe ningún campo de "porcentaje de asistencia": sería un
número con dos significados mezclados.

Lo que sí es confiable en todo el período es el conteo de **ausencias**, que
nunca fue un valor por defecto: alguien la eligió siempre.

### Período sin sesiones

**200 OK** con `sesiones: []` y el resumen en cero. No es un 404: "no hubo
sesiones" es una respuesta del reporte, no la ausencia del reporte.

### Errores

| Caso | Código |
|---|---|
| Falta `desde` o `hasta` | 400 |
| Fecha que no es `AAAA-MM-DD` | 400 |
| `hasta` anterior a `desde` | 400 |
| Rango mayor a 366 días | 400 |
| `id_terapeuta` no numérico | 400 |
| Sin token | 401 |
| Token válido, rol distinto de `rrhh` | 403 `rol_no_autorizado` |

---

## El procedimiento

`p_reporte_sesiones_periodo` — **4 parámetros, sin cambios**:

```
IN p_fecha_desde DATE, IN p_fecha_hasta DATE,
IN p_id_terapeuta INT UNSIGNED, OUT p_mensaje VARCHAR(255)
```

`ausencia_de` se agregó como **columna del `SELECT`**, no como parámetro. La
firma quedó intacta a propósito: está sujetada por
`tests/contratos/firmas-procedimientos.txt` y cambiarla habría roto ese
contrato sin necesidad.

**No toma ningún lock.** No lleva `FOR UPDATE` ni `FOR SHARE`: es una lectura
consistente, no entra en el orden canónico de adquisición y no puede formar un
ciclo con nadie.

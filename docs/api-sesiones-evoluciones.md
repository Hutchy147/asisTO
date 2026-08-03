# Contrato de API — Sesiones y Evolución

Base: `/api` · Formato: JSON · Autenticación: `Authorization: Bearer <token>`

**Todos los endpoints de este documento son exclusivos del rol `terapeuta`.**

> Los ejemplos de JSON están **copiados de respuestas reales** de la API
> corriendo contra la base, no escritos a mano.

Las convenciones generales (códigos de autenticación, forma de los errores)
son las mismas que en [`api-pacientes-objetivos.md`](api-pacientes-objetivos.md).

---

## Quién ve y quién escribe

Decisión de este módulo, importante para el diseño:

| Acción | Alcance |
|---|---|
| **Leer** una sesión y sus evoluciones | Cualquier terapeuta |
| **Cargar** evolución sobre una sesión | Solo el terapeuta que la atendió |
| Listar sesiones (`GET /api/sesiones`, `/hoy`, `/pendientes-evolucion`) | Solo las propias |

En esta entrega todos los terapeutas ven todos los pacientes, y el schema
contempla **duplas terapéuticas** (dos terapeutas sobre el mismo paciente),
así que restringir la lectura contradiría las dos cosas. Pero una evolución
es la valoración clínica de quien atendió: cargarla en nombre de otro
falsearía la autoría de la historia clínica.

El detalle de sesión trae **`es_propia`** para que la interfaz sepa si
mostrar el formulario de evolución o solo la vista de lectura.

---

## `GET /api/sesiones?desde=&hasta=`

Sesiones **del terapeuta logueado** en el rango, ordenadas por fecha y hora.

| Parámetro | Obligatorio | Notas |
|---|---|---|
| `desde` | no | `AAAA-MM-DD` |
| `hasta` | no | `AAAA-MM-DD` |

Sin parámetros devuelve **desde hoy y 7 días hacia adelante**. Si se manda
solo uno, el otro se completa con esa misma ventana.

**200 OK**

```json
{
  "desde": "2026-06-01",
  "hasta": "2026-06-30",
  "total": 7,
  "sesiones": [
    {
      "id": 1,
      "id_terapeuta": 1,
      "id_paciente": 1,
      "fecha": "2026-06-02",
      "hora_inicio": "09:00:00",
      "hora_fin": "10:00:00",
      "estado": "completa",
      "notas": "Buena disposicion. Trabajamos con masa y pinzas de ropa.",
      "fecha_registro": "2026-08-02T22:20:06",
      "admite_evolucion": true,
      "tiene_evolucion": true,
      "paciente": {
        "id": 1,
        "nombre": "Tomas",
        "apellido": "Aguirre",
        "nombre_completo": "Tomas Aguirre",
        "nro_historia": "HC-0001"
      }
    }
  ]
}
```

Campos calculados, pensados para el calendario:

- **`estado`** — `completa`, `incompleta` o `ausencia`.
- **`admite_evolucion`** — `false` cuando el estado es `ausencia`. Es la
  regla 2: sobre una ausencia no se puede cargar evolución.
- **`tiene_evolucion`** — si ya tiene al menos una cargada.

La combinación de esos dos es lo que define el estado visual de cada sesión:

| `admite_evolucion` | `tiene_evolucion` | Situación |
|---|---|---|
| `true` | `false` | Falta cargar evolución |
| `true` | `true` | Completa |
| `false` | `false` | Ausencia — no corresponde cargar |

**Errores**

| Caso | Status | `mensaje` |
|---|---|---|
| `desde` posterior a `hasta` | `400` | `El rango de fechas esta invertido: "desde" es posterior a "hasta".` |
| Rango de más de 366 días | `400` | `El rango pedido es de 2557 dias y el maximo es 366. Acotá las fechas.` |
| Fecha con formato inválido | `400` | `La fecha "desde" tiene que estar en formato AAAA-MM-DD.` |

El rango invertido devuelve **error, no una lista vacía**: una lista vacía
escondería el error en vez de mostrarlo.

---

## `GET /api/sesiones/hoy`

Las del día, para el panel principal. Mismo formato de `sesiones` que arriba.

**200 OK**

```json
{
  "fecha": "2026-08-02",
  "sesiones": [],
  "total": 0
}
```

La pantalla tiene que contemplar el **día sin sesiones** — es lo normal un
fin de semana.

---

## `GET /api/sesiones/pendientes-evolucion`

Sesiones **ya ocurridas**, en estado `completa` o `incompleta`, que todavía
no tienen ninguna evolución. Ordenadas de la más reciente a la más vieja.

"Ya ocurridas" incluye las de hoy cuyo horario de inicio ya pasó: una sesión
de las 9 está pendiente a las 11, no recién mañana.

Las de estado `ausencia` **nunca** aparecen: no es que les falte evolución,
es que no pueden tenerla.

**200 OK**

```json
{
  "total": 2,
  "sesiones": [
    {
      "id": 12,
      "id_terapeuta": 1,
      "id_paciente": 3,
      "fecha": "2026-06-05",
      "hora_inicio": "09:00:00",
      "hora_fin": "10:00:00",
      "estado": "completa",
      "notas": null,
      "fecha_registro": "2026-08-02T22:20:16",
      "admite_evolucion": true,
      "tiene_evolucion": false,
      "paciente": {
        "id": 3,
        "nombre": "Camila",
        "apellido": "Rios",
        "nombre_completo": "Camila Rios",
        "nro_historia": "HC-0003"
      }
    }
  ]
}
```

Es la lista de "trabajo pendiente" del terapeuta. `total` sirve directamente
como número de aviso en el panel.

---

## `POST /api/sesiones`

Registra una sesión llamando a `p_registrar_sesion`. El campo `mensaje` es
la salida del procedimiento.

**Recibe:**

```json
{
  "id_paciente": 1,
  "fecha": "2026-06-05",
  "hora_inicio": "08:00:00",
  "hora_fin": "09:00:00",
  "estado": "completa",
  "notas": "Sesion de prueba."
}
```

| Campo | Obligatorio | Notas |
|---|---|---|
| `id_paciente` | sí | |
| `fecha` | sí | `AAAA-MM-DD` |
| `hora_inicio` | sí | `HH:MM:SS` |
| `hora_fin` | no | Si falta, se asume **una hora** de duración |
| `estado` | no | `completa`, `incompleta` o `ausencia`. Por defecto `incompleta` |
| `notas` | no | Contenido clínico |

**El terapeuta es siempre el logueado.** Un `id_terapeuta` en el cuerpo se
ignora: si no, cualquier terapeuta podría llenarle la agenda a otro.

**201 Created**

```json
{
  "mensaje": "Sesion registrada correctamente",
  "sesion": {
    "id": 11,
    "id_terapeuta": 1,
    "id_paciente": 1,
    "fecha": "2026-06-05",
    "hora_inicio": "08:00:00",
    "hora_fin": "09:00:00",
    "estado": "completa",
    "notas": "Sesion de prueba.",
    "fecha_registro": "2026-08-02T22:20:16"
  }
}
```

**Errores**

| Caso | Status | `mensaje` |
|---|---|---|
| Falta un obligatorio | `400` | `Faltan datos obligatorios: fecha, hora_inicio` |
| `estado` no válido | `400` | `El estado tiene que ser uno de: completa, incompleta, ausencia.` |
| **Superposición horaria** | `400` | `El terapeuta ya tiene 1 sesion(es) que se superponen con ese horario` |
| Hora de fin anterior al inicio | `400` | `La hora de fin debe ser posterior a la hora de inicio` |
| Paciente inexistente | `400` | `El paciente indicado no existe` |

La superposición es la **regla 6** y el mensaje viene del procedimiento, con
la cantidad de sesiones en conflicto.

Dos sesiones que **se tocan** no se superponen: una que termina 09:00 y otra
que arranca 09:00 conviven sin problema. Las sesiones en `ausencia` **sí**
bloquean el horario: el paciente faltó, pero el turno estaba ocupado.

---

## `GET /api/sesiones/<id>`

Detalle con todo lo necesario para la pantalla de carga de evolución.

**200 OK** (recortado)

```json
{
  "sesion": {
    "id": 11,
    "estado": "completa",
    "fecha": "2026-06-05",
    "hora_inicio": "08:00:00",
    "hora_fin": "09:00:00",
    "notas": "Sesion de prueba.",
    "admite_evolucion": true,
    "tiene_evolucion": true,
    "es_propia": true
  },
  "paciente": {
    "id": 1,
    "nombre_completo": "Tomas Aguirre",
    "nro_historia": "HC-0001",
    "diagnostico": "Trastorno del procesamiento sensorial. Dificultades en motricidad fina.",
    "fecha_nacimiento": "2015-03-12",
    "activo": true,
    "tiene_login": false
  },
  "terapeuta": {
    "id": 1,
    "nombre_completo": "Laura Fernandez"
  },
  "evoluciones": [
    {
      "id": 12,
      "id_sesion": 11,
      "id_objetivo": 2,
      "valor": 4,
      "observaciones": "Buena respuesta a la consigna.",
      "fecha_registro": "2026-08-02T22:20:16"
    }
  ],
  "objetivos_activos": [
    {
      "id": 1,
      "id_paciente": 1,
      "descripcion": "Mejorar la pinza fina para la escritura",
      "activo": true,
      "fecha_creacion": "2026-03-02T10:15:00",
      "fecha_archivado": null
    }
  ]
}
```

`objetivos_activos` es **contra qué se puede calificar**: son las opciones
del formulario de evolución. Si viene **vacío**, el paciente no tiene
objetivos activos y no hay nada que evaluar — hay que crear un objetivo
primero.

**Errores:** `404` con `La sesion indicada no existe.`

---

## `POST /api/evoluciones`

Registra vía `p_registrar_evolucion`.

**Recibe:**

```json
{
  "id_sesion": 11,
  "id_objetivo": 2,
  "valor": 4,
  "observaciones": "Buena respuesta a la consigna."
}
```

`valor` es un entero de **1 a 5**. `observaciones` es opcional.

**201 Created**

```json
{
  "mensaje": "Evolucion registrada correctamente",
  "evolucion": {
    "id": 12,
    "id_sesion": 11,
    "id_objetivo": 2,
    "valor": 4,
    "observaciones": "Buena respuesta a la consigna.",
    "fecha_registro": "2026-08-02T22:20:16"
  }
}
```

**Errores — los cuatro que importan para la pantalla**

| Caso | Status | `mensaje` |
|---|---|---|
| **Regla 2** — sesión en ausencia | `400` | `No se puede cargar evolucion: la sesion esta marcada como ausencia` |
| **Regla 3** — objetivo de otro paciente | `400` | `El objetivo evaluado no pertenece al paciente de esta sesion` |
| **Regla 4** — objetivo archivado | `400` | `No se puede cargar evolucion sobre un objetivo archivado` |
| Mismo objetivo dos veces en la sesión | `400` | `Ya existe una evolucion para ese objetivo en esa sesion` |

Los tres primeros son mensajes emitidos por los triggers de la base y se
propagan **tal cual**: son accionables y mostrables al usuario sin reescribir.

**Otros errores**

| Caso | Status | `mensaje` |
|---|---|---|
| `valor` fuera de 1–5 | `400` | `El valor de la evolucion tiene que estar entre 1 y 5.` |
| `valor` no numérico o ausente | `400` | `El valor de la evolucion tiene que ser un numero entre 1 y 5.` |
| **Paciente sin objetivos activos** | `409` | `El paciente no tiene objetivos activos: no hay contra que calificar. Creá un objetivo antes de cargar la evolucion.` |
| **Sesión de otro terapeuta** | `403` | `Solo el terapeuta que atendio la sesion puede cargarle evolucion.` |
| Sesión inexistente | `404` | `La sesion indicada no existe.` |
| Falta `id_sesion` o `id_objetivo` | `400` | `Faltan datos obligatorios: id_sesion, id_objetivo.` |

---

## `GET /api/evoluciones/sesion/<id>`

Evoluciones de una sesión, **con la descripción del objetivo** para no tener
que cruzarlas en el cliente.

**200 OK**

```json
{
  "id_sesion": 11,
  "total": 1,
  "evoluciones": [
    {
      "id": 12,
      "id_sesion": 11,
      "id_objetivo": 2,
      "valor": 4,
      "observaciones": "Buena respuesta a la consigna.",
      "fecha_registro": "2026-08-02T22:20:16",
      "objetivo": {
        "id": 2,
        "descripcion": "Tolerar texturas nuevas en la alimentacion",
        "activo": true
      }
    }
  ]
}
```

`objetivo.activo` puede ser `false`: el objetivo se archivó **después** de
cargar la evolución. Es un estado válido y frecuente — la historia se
conserva. La pantalla debería mostrarlo como histórico, no como error.

---

## Resumen para el diseño de pantallas

| Método | Ruta | Éxito |
|---|---|---|
| GET | `/api/sesiones?desde=&hasta=` | `200` |
| GET | `/api/sesiones/hoy` | `200` |
| GET | `/api/sesiones/pendientes-evolucion` | `200` |
| POST | `/api/sesiones` | `201` |
| GET | `/api/sesiones/<id>` | `200` |
| POST | `/api/evoluciones` | `201` |
| GET | `/api/evoluciones/sesion/<id>` | `200` |

Estados que las pantallas tienen que contemplar:

1. **Sesión en ausencia** — `admite_evolucion: false`. No mostrar el
   formulario de evolución; explicar por qué, no dejar un botón que falle.
2. **Sesión pendiente de evolución** — `admite_evolucion: true` y
   `tiene_evolucion: false`. Es el trabajo pendiente del terapeuta.
3. **Paciente sin objetivos activos** — `objetivos_activos` vacío. Hay que
   ofrecer crear un objetivo, no un formulario sin opciones.
4. **Sesión de otro terapeuta** — `es_propia: false`. Vista de lectura, sin
   formulario de evolución.
5. **Día sin sesiones** — lista vacía, es normal.
6. **Objetivo archivado en una evolución vieja** — `objetivo.activo: false`.
   Histórico, no error.
7. **Superposición al registrar** — el mensaje trae cuántas sesiones chocan;
   conviene mostrarlo junto al campo de horario.
8. **Rango de fechas inválido** — devuelve `400`, no lista vacía.

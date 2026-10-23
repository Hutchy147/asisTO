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

En esta entrega todos los terapeutas ven todos los pacientes, así que
restringir la lectura no aportaría control real. Pero una evolución es la
valoración clínica de quien atendió: cargarla en nombre de otro falsearía
la autoría de la historia clínica.

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
      "id": 623,
      "id_terapeuta": 2,
      "id_paciente": 1,
      "fecha": "2026-07-17",
      "hora_inicio": "11:00:00",
      "hora_fin": "12:00:00",
      "estado": "incompleta",
      "ausencia_de": null,
      "notas": "Se trabajo parcialmente, la sesion se corto antes.",
      "fecha_registro": "2026-08-03T19:53:20",
      "admite_evolucion": true,
      "tiene_evolucion": true,
      "objetivos": { "calificados": 1, "total": 3 },
      "paciente": {
        "id": 1,
        "nombre": "Tomas",
        "apellido": "Aguirre",
        "nombre_completo": "Tomas Aguirre",
        "nro_historia": "HC-0001"
      },
      "terapeuta": {
        "id": 2,
        "nombre_completo": "Diego Moyano"
      }
    }
  ]
}
```

Campos calculados, pensados para el calendario:

- **`estado`** — `completa`, `incompleta` o `ausencia`. **Son los tres del
  ENUM y no hay más.** No existe un estado "pendiente" ni "futura".
- **`ausencia_de`** (2026-09-11) — `paciente`, `terapeuta` o `null`. Solo
  tiene valor cuando `estado = "ausencia"`; eje distinto del estado (QUIÉN
  faltó, no QUÉ pasó). Puede ser `null` con `estado = "ausencia"` en
  sesiones sembradas antes de esta columna, donde nadie puede reponer el
  dato retroactivamente.
- **`admite_evolucion`** — `false` cuando el estado es `ausencia`. Es la
  regla 2: sobre una ausencia no se puede cargar evolución.
- **`tiene_evolucion`** — si ya tiene al menos una cargada.
- **`objetivos`** — `{ calificados, total }`. Ver abajo.
- **`terapeuta`** — quién atendió, con nombre para mostrar.

La combinación de esos dos es lo que define el estado visual de cada sesión:

| `admite_evolucion` | `tiene_evolucion` | Situación |
|---|---|---|
| `true` | `false` | Falta cargar evolución |
| `true` | `true` | Completa |
| `false` | `false` | Ausencia — no corresponde cargar |

### `objetivos` — "3 de 4"

Es el dato más repetido de la interfaz: cuántos objetivos se calificaron en
esa sesión sobre cuántos había.

**El denominador son los objetivos activos AL MOMENTO DE LA SESIÓN, no los
activos hoy.** Para un historial es lo único que tiene sentido: una sesión
de marzo donde se calificaron 3 de 3 no puede pasar a "3 de 1" porque desde
entonces se archivaron dos objetivos. Con el denominador de hoy, el pasado
cambiaría solo cada vez que alguien archiva algo.

Se reconstruye con `fecha_creacion` y `fecha_archivado` del objetivo.

> **Limitación conocida.** Si un objetivo se archivó, se reactivó y se
> volvió a archivar, solo sobrevive la última `fecha_archivado`, así que el
> total de las sesiones del primer tramo puede quedar corto. Es un caso raro
> y resolverlo requeriría una tabla de historial de estados, que no se
> justifica para esta entrega.

En una **ausencia** el par viene igual (normalmente `0 de N`), pero no
corresponde calificar nada: la pantalla lo muestra como `—`.

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

## `GET /api/pacientes/<id>/sesiones`

Historial completo de sesiones del paciente, de la más reciente a la más
vieja. Es lo que alimenta la pestaña **Sesiones** de la ficha.

**Devuelve las sesiones de TODOS los terapeutas**, no solo las del logueado.
Es coherente con la regla de autoría del módulo: la lectura es abierta y lo
restringido es cargar evolución. Filtrar por terapeuta acá mostraría media
historia clínica, que es peor que mostrarla entera.

**200 OK** (recortado)

```json
{
  "paciente": {
    "id": 1,
    "nombre_completo": "Tomas Aguirre",
    "nro_historia": "HC-0001",
    "fecha_alta": "2026-03-02",
    "fecha_nacimiento": "2015-03-12",
    "diagnostico": "Trastorno del procesamiento sensorial. Dificultades en motricidad fina.",
    "activo": true,
    "tiene_login": false
  },
  "total": 44,
  "sesiones": [
    {
      "id": 623,
      "fecha": "2026-07-17",
      "hora_inicio": "11:00:00",
      "hora_fin": "12:00:00",
      "estado": "incompleta",
      "admite_evolucion": true,
      "tiene_evolucion": true,
      "objetivos": { "calificados": 1, "total": 3 },
      "terapeuta": { "id": 2, "nombre_completo": "Diego Moyano" },
      "paciente": {
        "id": 1,
        "nombre_completo": "Tomas Aguirre",
        "nro_historia": "HC-0001"
      }
    }
  ]
}
```

Cada sesión trae la misma forma que en los otros listados, así que la tabla
del historial y la del calendario comparten el mismo componente de fila.

**Errores:** los mismos 404 que `GET /api/pacientes/<id>` — "no existe" y
"está dado de baja", con mensajes distintos.

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
  "ausencia_de": null,
  "notas": "Sesion de prueba."
}
```

| Campo | Obligatorio | Notas |
|---|---|---|
| `id_paciente` | sí | |
| `fecha` | sí | `AAAA-MM-DD` |
| `hora_inicio` | sí | `HH:MM:SS` |
| `hora_fin` | no | Si falta, la API la completa con **45 minutos** (Entrega 3). Las sesiones viejas sin hora de fin siguen leyéndose como una hora |
| `estado` | **sí** | `completa`, `incompleta` o `ausencia`. Sin default: hasta el 2026-09-10 un estado ausente se guardaba como `incompleta` sin que nadie lo haya declarado — ver el hallazgo A de `AUDITORIA.md`. Ahora se rechaza igual que cualquier otro obligatorio faltante |
| `ausencia_de` | **condicional** (2026-09-11) | `paciente` o `terapeuta`. **Obligatorio si y solo si `estado = "ausencia"`.** Fuera de una ausencia tiene que venir `null`/ausente: mandarlo con cualquier otro estado se rechaza. Es un eje distinto de `estado` (QUIÉN faltó, no QUÉ pasó con la sesión) — ver la columna en `schema.sql` |
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
    "ausencia_de": null,
    "notas": "Sesion de prueba.",
    "fecha_registro": "2026-08-02T22:20:16"
  }
}
```

**Errores**

| Caso | Status | `mensaje` |
|---|---|---|
| Falta un obligatorio | `400` | `Faltan datos obligatorios: estado, hora_inicio` |
| `estado` no válido | `400` | `El estado tiene que ser uno de: completa, incompleta, ausencia.` |
| `ausencia` sin `ausencia_de` | `400` | `Falta declarar quien falto: tiene que ser "paciente" o "terapeuta".` |
| `ausencia_de` fuera de una ausencia | `400` | `Quien falto solo se declara en una sesion marcada como ausencia.` |
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
    "ausencia_de": null,
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

## `PUT /api/sesiones/<id>`

Edita una sesión ya registrada, vía `p_editar_sesion`. **PUT y no PATCH**,
mismo criterio que `PUT /api/pacientes/<id>`: el formulario manda la sesión
entera, no un delta.

**Editable:** `estado`, `ausencia_de`, `notas`, `fecha`, `hora_inicio`,
`hora_fin`. **NO editable:** `id_paciente` ni `id_terapeuta` — no se
aceptan en el cuerpo. El terapeuta es siempre el logueado, igual que en el
`POST`; el paciente es un hecho de la sesión, no un dato que se corrija
desde acá.

**Solo el terapeuta que atendió puede editar.** La lectura sigue abierta a
cualquiera por `GET /api/sesiones/<id>` — es la misma decisión de "quién ve
y quién escribe" del principio de este documento, aplicada ahora a la
sesión entera y no solo a la evolución. El detalle ya trae `es_propia` para
que la interfaz sepa si mostrar el formulario de edición.

**Recibe:**

```json
{
  "estado": "completa",
  "ausencia_de": null,
  "notas": "Se retiro 20 minutos antes por malestar.",
  "fecha": "2026-06-16",
  "hora_inicio": "09:00:00",
  "hora_fin": "10:00:00"
}
```

| Campo | Obligatorio | Notas |
|---|---|---|
| `estado` | sí | `completa`, `incompleta` o `ausencia` |
| `ausencia_de` | **condicional** (2026-09-11) | Mismo criterio que en el `POST`: obligatorio si y solo si `estado = "ausencia"`, `null`/ausente en cualquier otro caso |
| `fecha` | sí | `AAAA-MM-DD` |
| `hora_inicio` | sí | `HH:MM:SS` |
| `hora_fin` | no | Si falta, se asume **una hora** de duración |
| `notas` | no | Contenido clínico; se puede mandar vacío para borrarlas |

**200 OK**

```json
{
  "mensaje": "Sesion actualizada correctamente",
  "sesion": {
    "id": 12,
    "id_terapeuta": 1,
    "id_paciente": 4,
    "fecha": "2026-06-12",
    "hora_inicio": "11:00:00",
    "hora_fin": "12:00:00",
    "estado": "completa",
    "ausencia_de": null,
    "notas": "Secuencia de vestido con apoyo verbal (editado).",
    "fecha_registro": "2026-06-12T14:00:00"
  }
}
```

### Sesiones de ausencia sembradas antes del 2026-09-11

Las filas con `estado = "ausencia"` cargadas antes de que existiera
`ausencia_de` quedaron con ese campo en `NULL` — nadie puede reponer
retroactivamente quién faltó. Al editar una de esas sesiones por esta
puerta, `ausencia_de` viaja igual que cualquier otro campo del formulario:
si la edición no toca ni `estado` ni `ausencia_de`, se guarda sin pedir
nada nuevo; pero **la interfaz siempre pide declarar quién faltó cuando
`estado` es `ausencia`**, así que en la práctica la primera vez que alguien
vuelve a abrir una de esas sesiones para editar cualquier cosa, tiene que
completar el dato antes de poder guardar. No es un bloqueo del backend: es
el mismo formulario obligatorio que rige para una ausencia nueva.

### Lo que la base revalida en cada edición, y cuándo

La regla 6 (superposición), la fecha contra la baja del paciente y la regla
2 aplicada al revés (ausencia con evolución ya cargada) las aplica
`trg_sesiones_solape_update`, **no este endpoint ni el procedimiento**. El
trigger revalida cada una exactamente cuando cambia el campo del que
depende:

| Se revalida | Cuándo | Por qué alcanza |
|---|---|---|
| Superposición horaria | Cambia `fecha`, `hora_inicio` u `hora_fin` | Si el horario no se toca, no puede haber una superposición nueva |
| Sesión posterior a la baja del paciente | Cambia `fecha` | El paciente no es editable; si la fecha no se mueve, la sesión sigue donde ya estaba validada |
| Ausencia con evolución ya cargada | Cambia `estado` a `ausencia` | Es la única de las cuatro que corre **siempre**, sin guardia: no depende de qué otro campo se tocó |
| Sesión ya registrada movida al futuro (2026-10-23) | Cambia `fecha` u `hora_inicio` a un momento posterior a ahora | Solo puede ir al futuro una sesión `incompleta` sin evoluciones ni renglones de registro: lo que ya ocurrió no se reprograma |
| Consistencia `estado`/`ausencia_de` (2026-09-11) | Cambia `estado` o `ausencia_de` | Igual criterio que las otras dos guardadas: una fila de ausencia sembrada antes de esta columna, con `ausencia_de` en `NULL`, no se puede dejar congelada para cualquier edición que no toque ninguno de los dos campos |

Una edición que solo cambia `notas` no dispara ninguna de las cuatro — y no
hace falta: ninguna depende de `notas`.

**Errores**

| Caso | Status | `mensaje` |
|---|---|---|
| Falta un obligatorio | `400` | `Faltan datos obligatorios: estado, fecha` |
| `estado` no válido | `400` | `El estado tiene que ser uno de: completa, incompleta, ausencia.` |
| `ausencia` sin `ausencia_de` | `400` | `Falta declarar quien falto: tiene que ser "paciente" o "terapeuta".` |
| `ausencia_de` fuera de una ausencia | `400` | `Quien falto solo se declara en una sesion marcada como ausencia.` |
| **Sesión de otro terapeuta** | `403` | `Solo el terapeuta que atendio la sesion puede editarla.` |
| **Superposición horaria** | `400` | `El terapeuta ya tiene sesiones que se superponen con ese horario` |
| Hora de fin anterior al inicio | `400` | `La hora de fin debe ser posterior a la hora de inicio` |
| Fecha posterior a la baja del paciente | `400` | `El paciente no esta en tratamiento activo: solo se pueden cargar sesiones hasta el dia del cierre` |
| **A `ausencia` con evoluciones cargadas** | `400` | `No se puede marcar la sesion como ausencia: ya tiene evoluciones cargadas` |
| **`ausencia` sin `ausencia_de` (trigger)** | `400` | `No se puede marcar la sesion como ausencia sin declarar quien falto` |
| **Sesión ya registrada a una fecha futura** | `400` (`campo: fecha`) | `Una sesion realizada o ausente no se puede pasar a una fecha futura` / `Una sesion con evoluciones o notas registradas no se puede pasar a una fecha futura` |
| Sesión inexistente | `404` | `La sesion indicada no existe.` |

Los del bloque de `trg_sesiones_solape_update` se propagan tal cual desde
`p_editar_sesion`: son los mismos textos que ya usa `POST /api/sesiones`, y
significan lo mismo. Las dos primeras filas de `ausencia_de` las valida
Python (`_validar_ausencia_de`, mismo criterio que `_validar_estado`) antes
de llegar a la base; la del trigger es la misma regla vista desde un `CALL`
directo, que no pasa por Python.

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

## `PUT /api/evoluciones/<id>` y `DELETE /api/evoluciones/<id>` (2026-10-23)

Corrigen o quitan una calificación ya guardada (`p_corregir_evolucion`). Antes
no había ninguna forma de arreglar una calificación mal tocada.

- Solo el terapeuta que atendió la sesión.
- Solo con el registro **abierto** (sesión `incompleta`). Una sesión terminada
  se reabre primero (`PUT /api/sesiones/<id>` con `estado: incompleta`).
- `PUT` recibe `{ "valor": 1..5, "observaciones": "texto o null" }`. Las reglas
  2 y 4 las revalida `trg_evoluciones_validar_update`.
- `DELETE` deja el objetivo sin calificar en esa sesión.

| Caso | Status | `mensaje` |
|---|---|---|
| Corregida / quitada | `200` | `Calificación corregida` / `Calificación quitada` |
| Valor fuera de escala | `400` (`campo: valor`) | `El valor de la evolución tiene que estar entre 1 y 5.` |
| Sesión terminada | `400` | `La sesión ya fue terminada: reabra el registro para corregir una calificación` |
| Otro terapeuta | `403` | `Solo el terapeuta que atendió la sesión puede corregir sus calificaciones` |
| No existe | `404` | `La calificación indicada no existe` |

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
| GET | `/api/pacientes/<id>/sesiones` | `200` |
| POST | `/api/sesiones` | `201` |
| GET | `/api/sesiones/<id>` | `200` |
| PUT | `/api/sesiones/<id>` | `200` |
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
   formulario de evolución ni de edición: ninguno de los dos es de esta sesión.
5. **Día sin sesiones** — lista vacía, es normal.
6. **Objetivo archivado en una evolución vieja** — `objetivo.activo: false`.
   Histórico, no error.
7. **Superposición al registrar** — el mensaje trae cuántas sesiones chocan;
   conviene mostrarlo junto al campo de horario.
8. **Rango de fechas inválido** — devuelve `400`, no lista vacía.


## Norma de agenda (Entrega 3)

- **Lunes a viernes:** `POST /api/sesiones` rechaza con 400 (`campo: fecha`, "Las sesiones se agendan de lunes a viernes.") una fecha en sábado o domingo, y `PUT /api/sesiones/<id>` lo hace solo si la **fecha cambia**: una sesión ya guardada en fin de semana se sigue viendo y editando.
- **45 minutos:** sin `hora_fin`, la API pone `hora_inicio + 45 min`.
- Es política operativa y vive en `sesiones_service.py`, no en la base: la base admite cualquier día y duración (carga retroactiva, sesiones históricas).
- Tests: `tests/nube/test_agenda_api.py`.

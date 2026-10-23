# Contrato de API — Pacientes y Objetivos

Base: `/api` · Formato: JSON · Autenticación: `Authorization: Bearer <token>`

**Todos los endpoints de este documento son exclusivos del rol `terapeuta`.**

> Los ejemplos de JSON de este documento están **copiados de respuestas
> reales** de la API corriendo contra la base, no escritos a mano. Se
> capturaron con el script de verificación del módulo. Si un campo aparece
> acá, existe con ese nombre exacto.

---

## Convenciones generales

### Autenticación y permisos

| Situación | Status | `codigo` |
|---|---|---|
| Falta el header `Authorization` | `401` | `token_faltante` |
| Token inválido o manipulado | `401` | `token_invalido` |
| Token vencido | `401` | `token_expirado` |
| Cuenta deshabilitada o borrada | `401` | `usuario_inactivo` |
| Token válido pero rol distinto de `terapeuta` | `403` | `rol_no_autorizado` |

La distinción importa para la interfaz: **401 significa "volvé a
autenticarte"** (mandar al login), **403 significa "estás autenticado pero
esto no es para vos"** (mostrar el 403, no el login).

### Forma de los errores

Todos los errores tienen la misma forma, sin excepción:

```json
{
  "codigo": "error_aplicacion",
  "mensaje": "Ya existe un paciente con el numero de historia HC-0001",
  "campo": "nro_historia"
}
```

**`campo`** identifica el campo del formulario responsable, cuando el
servidor lo puede determinar. Es **metadato al lado del mensaje**, no una
reescritura: el texto viaja igual que antes.

Sirve para marcar el input correcto sin que el cliente tenga que deducirlo
leyendo el mensaje. Es `null` cuando el rechazo no es culpa de un campo en
particular — el límite de 4 objetivos activos, por ejemplo:

```json
{
  "codigo": "error_base_de_datos",
  "mensaje": "El paciente ya tiene 4 objetivos activos. Archive uno antes de crear otro",
  "campo": null
}
```

Con `campo: null` la interfaz muestra solo el aviso general, que es lo que
hacía antes de que este campo existiera.

Valores que devuelve hoy: `nro_historia`, `descripcion`, `hora_inicio`,
`hora_fin`, `id_paciente`, `id_terapeuta`, `id_usuario`, `id_sesion`,
`id_objetivo`, `valor`.

| `codigo` | Origen |
|---|---|
| `error_aplicacion` | Validación del backend o regla de negocio |
| `error_base_de_datos` | Regla aplicada por un trigger o constraint |
| `rol_no_autorizado`, `token_*`, `usuario_inactivo` | Autenticación / permisos |
| `no_encontrado`, `metodo_no_permitido` | Ruta o método inexistente |
| `error_interno` | Error no contemplado |

**`mensaje` siempre está en castellano y es mostrable al usuario tal cual.**
Nunca contiene nombres de tablas, constraints ni texto de MySQL.

---

## `GET /api/pacientes`

Lista los pacientes **activos**, ordenados por apellido y nombre. Los
pacientes dados de baja no aparecen.

**Recibe:** nada.

**200 OK**

```json
{
  "pacientes": [
    {
      "activo": true,
      "apellido": "Aguirre",
      "diagnostico": "Trastorno del procesamiento sensorial. Dificultades en motricidad fina.",
      "fecha_nacimiento": "2015-03-12",
      "id": 1,
      "nombre": "Tomas",
      "nombre_completo": "Tomas Aguirre",
      "nro_historia": "HC-0001",
      "fecha_alta": "2026-03-02",
      "objetivos_activos": 3,
      "tiene_login": false
    },
    {
      "activo": true,
      "apellido": "Rios",
      "diagnostico": "Lesion de muneca derecha. Rehabilitacion funcional post quirurgica.",
      "fecha_nacimiento": "1998-11-05",
      "id": 3,
      "nombre": "Camila",
      "nombre_completo": "Camila Rios",
      "nro_historia": "HC-0003",
      "fecha_alta": "2026-04-06",
      "objetivos_activos": 1,
      "tiene_login": true
    }
  ],
  "total": 3
}
```

Notas para el diseño de la pantalla:

- `objetivos_activos` va de **0 a 4**. El máximo es 4 (regla de negocio).
- `fecha_alta` es desde cuándo está en tratamiento. Sirve para el
  *"en tratamiento desde…"* de la ficha y para contar altas del mes.
- `tiene_login` es `false` para los pacientes sin credenciales — típicamente
  menores. **No es un dato faltante ni un error a mostrar:** es un estado
  válido y frecuente. La ficha clínica está completa igual.
- `fecha_nacimiento` viene como `YYYY-MM-DD`, sin hora.

---

## `POST /api/pacientes`

Alta de paciente. Internamente llama al procedimiento almacenado
`p_alta_paciente`; el campo `mensaje` de la respuesta es su salida.

**Recibe:**

```json
{
  "nombre": "Bruno",
  "apellido": "Peralta",
  "fecha_nacimiento": "2014-09-01",
  "diagnostico": "Dificultades de coordinacion motora.",
  "nro_historia": "HC-TEST-01",
  "id_usuario": null
}
```

| Campo | Obligatorio | Notas |
|---|---|---|
| `nombre` | sí | |
| `apellido` | sí | |
| `fecha_nacimiento` | sí | `YYYY-MM-DD` |
| `nro_historia` | sí | Único en todo el sistema |
| `diagnostico` | no | Puede ser `null` |
| `id_usuario` | no | `null` = paciente **sin login**. Es lo normal para menores. |

**201 Created**

```json
{
  "mensaje": "Paciente registrado correctamente",
  "paciente": {
    "activo": true,
    "apellido": "Peralta",
    "diagnostico": "Dificultades de coordinacion motora.",
    "fecha_nacimiento": "2014-09-01",
    "id": 4,
    "nombre": "Bruno",
    "nombre_completo": "Bruno Peralta",
    "nro_historia": "HC-TEST-01",
    "tiene_login": false
  }
}
```

**Errores**

| Caso | Status | Respuesta |
|---|---|---|
| Falta un campo obligatorio | `400` | `{"codigo": "error_aplicacion", "mensaje": "Faltan datos obligatorios: apellido, fecha_nacimiento, nro_historia"}` |
| `nro_historia` ya existe | `400` | `{"codigo": "error_aplicacion", "mensaje": "Ya existe un paciente con el numero de historia HC-TEST-01"}` |
| `id_usuario` que no existe | `400` | `{"codigo": "error_aplicacion", "mensaje": "El usuario indicado no existe"}` |

El mensaje de historia duplicada **incluye el número**, así que se puede
mostrar tal cual junto al campo del formulario.

---

## `GET /api/pacientes/<id>`

Detalle del paciente con sus objetivos **activos** (no incluye archivados;
para eso está el endpoint de objetivos).

**200 OK**

```json
{
  "paciente": {
    "activo": true,
    "apellido": "Peralta",
    "diagnostico": "Dificultades de coordinacion motora.",
    "fecha_nacimiento": "2014-09-01",
    "id": 4,
    "nombre": "Bruno",
    "nombre_completo": "Bruno Peralta",
    "nro_historia": "HC-TEST-01",
    "tiene_login": false
  },
  "objetivos_activos": [
    {
      "activo": true,
      "descripcion": "Descripcion editada",
      "fecha_archivado": null,
      "fecha_creacion": "2026-07-30T09:57:43",
      "id": 10,
      "id_paciente": 4
    }
  ]
}
```

**Errores**

| Caso | Status | `mensaje` |
|---|---|---|
| No existe | `404` | `El paciente indicado no existe.` |
| Dado de baja | `404` | `El paciente indicado no esta en tratamiento activo.` |

Son dos mensajes distintos a propósito: "no existe" puede ser un id mal
tipeado, "dado de baja" es un registro real que sigue en la base.

---

## `GET /api/objetivos/paciente/<id>`

Objetivos del paciente **separados en activos y archivados**, más el estado
del cupo.

**200 OK**

```json
{
  "paciente": {
    "activo": true,
    "apellido": "Peralta",
    "diagnostico": "Dificultades de coordinacion motora.",
    "fecha_nacimiento": "2014-09-01",
    "id": 4,
    "nombre": "Bruno",
    "nombre_completo": "Bruno Peralta",
    "nro_historia": "HC-TEST-01",
    "tiene_login": false
  },
  "activos": [
    {
      "activo": true,
      "descripcion": "Mejorar la precision en actividades de motricidad fina",
      "fecha_archivado": null,
      "fecha_creacion": "2026-05-04T00:15:00",
      "id": 1,
      "id_paciente": 1,
      "seguimiento": {
        "ultimo_valor": 5,
        "fecha_ultima_evolucion": "2026-07-14",
        "total_evoluciones": 14
      }
    }
  ],
  "archivados": [
    {
      "activo": false,
      "descripcion": "Realizar actividades de la vida diaria de forma autonoma",
      "fecha_archivado": "2026-08-03T19:53:21",
      "fecha_creacion": "2026-05-04T01:00:00",
      "id": 12,
      "id_paciente": 3,
      "seguimiento": {
        "ultimo_valor": 2,
        "fecha_ultima_evolucion": "2026-07-16",
        "total_evoluciones": 16
      }
    }
  ],
  "cupo": {
    "disponibles": 1,
    "maximo": 4,
    "usados": 3
  }
}
```

### `seguimiento` — última calificación y acumulado

Lo trae **cada objetivo, activo o archivado**:

| Campo | Qué es |
|---|---|
| `ultimo_valor` | Última calificación (1 a 5). `null` si nunca se calificó. |
| `fecha_ultima_evolucion` | Fecha de la **sesión** de esa calificación. `null` si no hay. |
| `total_evoluciones` | Cuántas veces se calificó en total. |

**"Última" se ordena por fecha y hora de la sesión, no por cuándo se cargó
la evolución.** Importa cuándo ocurrió la sesión, no cuándo el terapeuta se
sentó a registrarla.

Para la interfaz: `ultimo_valor: null` con `total_evoluciones: 0` es un
objetivo recién creado, no un error. Un archivado con
`total_evoluciones` alto es justamente el caso que hay que poder consultar
—por eso archivar no borra—.

`cupo` está pensado para la interfaz: permite deshabilitar el botón de
"nuevo objetivo" **antes** de intentar el alta, y mostrar algo tipo "3 de 4".
No es la validación — esa la hace la base — pero evita el viaje de ida y
vuelta para un error previsible.

Los objetivos vienen ordenados por fecha de creación.

**Errores:** los mismos 404 que `GET /api/pacientes/<id>`.

---

## `POST /api/objetivos`

**Recibe:**

```json
{
  "id_paciente": 4,
  "descripcion": "Sostener el lapiz con pinza tripode"
}
```

**201 Created**

```json
{
  "mensaje": "Objetivo creado correctamente.",
  "objetivo": {
    "activo": true,
    "descripcion": "Sostener el lapiz con pinza tripode",
    "fecha_archivado": null,
    "fecha_creacion": "2026-07-30T09:57:43",
    "id": 8,
    "id_paciente": 4
  }
}
```

**Errores**

| Caso | Status | Respuesta |
|---|---|---|
| Falta `id_paciente` | `400` | `{"codigo": "error_aplicacion", "mensaje": "Falta indicar el paciente."}` |
| Descripción vacía | `400` | `{"codigo": "error_aplicacion", "mensaje": "La descripcion del objetivo no puede estar vacia."}` |
| Paciente inexistente o de baja | `404` | igual que arriba |
| **Ya hay 4 objetivos activos** | `400` | `{"codigo": "error_base_de_datos", "mensaje": "El paciente ya tiene 4 objetivos activos. Archive uno antes de crear otro"}` |
| **Descripción repetida entre activos** | `409` | `{"codigo": "error_aplicacion", "mensaje": "Ya existe un objetivo activo con esa descripcion para este paciente."}` |

Los dos últimos son los casos interesantes para la pantalla:

- El del **cupo** viene con `codigo: "error_base_de_datos"` porque lo emite
  un trigger. El texto es igualmente mostrable al usuario.
- El de **descripción repetida** solo choca contra objetivos **activos**.
  Repetir la descripción de uno **archivado** está permitido y devuelve
  `201`: es el caso clínico de retomar un objetivo viejo.

---

## `PUT /api/objetivos/<id>`

Edita **solo la descripción**. No cambia el estado activo/archivado.

**Recibe:**

```json
{ "descripcion": "Descripcion editada" }
```

**200 OK**

```json
{
  "mensaje": "Objetivo actualizado correctamente.",
  "objetivo": {
    "activo": true,
    "descripcion": "Descripcion editada",
    "fecha_archivado": null,
    "fecha_creacion": "2026-07-30T09:57:43",
    "id": 10,
    "id_paciente": 4
  }
}
```

**Errores**

| Caso | Status | `mensaje` |
|---|---|---|
| Descripción vacía | `400` | `La descripcion del objetivo no puede estar vacia.` |
| Objetivo inexistente | `404` | `El objetivo indicado no existe.` |
| La nueva descripción ya la usa otro objetivo **activo** | `409` | `Ya existe un objetivo activo con esa descripcion para este paciente.` |
| **El objetivo está archivado** | `400` | `El objetivo esta archivado: su descripcion quedo fija y no se puede editar` |

Mandar la misma descripción que ya tenía devuelve `200` sin escribir nada.

### Un objetivo archivado no se puede editar

Su descripción es **inmutable**. No es una limitación técnica: un objetivo
archivado tiene evoluciones colgando, y reescribir su texto dejaría
calificaciones históricas puntuando contra algo que hoy dice otra cosa.
Estos registros respaldan el tratamiento ante obras sociales e
instituciones, así que el pasado no se reescribe.

Para la interfaz: en la lista de archivados, **no ofrecer la acción de
editar**. El backend la rechaza igual, pero un botón que siempre falla es
peor que no tenerlo.

La regla vive en la base (trigger), no solo en el endpoint: cualquier
camino de escritura la respeta.

---

## `DELETE /api/objetivos/<id>`

**Archiva** el objetivo. No borra la fila.

Pone `activo = false` y la base completa `fecha_archivado`. Las evoluciones
ya cargadas sobre ese objetivo **se conservan**: son historia clínica y no se
pierden. Archivar libera cupo.

**200 OK**

```json
{
  "mensaje": "Objetivo archivado. Las evoluciones cargadas se conservan.",
  "objetivo": {
    "activo": false,
    "descripcion": "Sostener el lapiz con pinza tripode",
    "fecha_archivado": "2026-07-30T09:57:43",
    "fecha_creacion": "2026-07-30T09:57:43",
    "id": 8,
    "id_paciente": 4
  }
}
```

**Errores**

| Caso | Status | `mensaje` |
|---|---|---|
| Objetivo inexistente | `404` | `El objetivo indicado no existe.` |
| Ya estaba archivado | `409` | `El objetivo ya estaba archivado.` |

Para la interfaz: conviene que la acción se llame **"Archivar"** y no
"Eliminar". No hay endpoint de borrado y no va a haberlo — los datos
clínicos no se borran.

---

## Resumen para el diseño de pantallas

| Método | Ruta | Éxito |
|---|---|---|
| GET | `/api/pacientes` | `200` |
| POST | `/api/pacientes` | `201` |
| GET | `/api/pacientes/<id>` | `200` |
| GET | `/api/pacientes/<id>/sesiones` | `200` — ver el otro contrato |
| GET | `/api/objetivos/paciente/<id>` | `200` |
| POST | `/api/objetivos` | `201` |
| PUT | `/api/objetivos/<id>` | `200` |
| DELETE | `/api/objetivos/<id>` | `200` |

Estados que las pantallas tienen que contemplar:

1. **Paciente sin login** (`tiene_login: false`) — normal, no es un error.
2. **Cupo lleno** (`cupo.disponibles === 0`) — deshabilitar el alta y decir
   por qué.
3. **Objetivos archivados** — hay que poder verlos; guardan la historia.
   **No se pueden editar:** no ofrecer la acción sobre ellos.
4. **Descripción repetida** — el error distingue activo de archivado, y la
   interfaz debería explicar que contra un archivado sí se puede.
5. **401 vs 403** — el primero va al login, el segundo a la pantalla de 403.
6. **Paciente de baja** — mensaje distinto al de inexistente.


---

## Entrega 3 — Pausa, alta y mínimo de 3 objetivos

### `POST /api/pacientes/{id}/baja` (cambia el cuerpo)

Ahora el cuerpo es obligatorio:

| Campo | Regla |
|---|---|
| `tipo` | `"pausa"` o `"alta"`. Sin él → `400`, `campo: "tipo"`. |
| `motivo` | Solo para `pausa`: obligatorio, hasta 200 caracteres. → `400`, `campo: "motivo"`. |

- **`pausa`** (`p_pausar_paciente`): el tratamiento se interrumpe y se puede
  retomar. NO archiva objetivos ni cierra la asignación. Respuesta con
  `objetivos_archivados: 0` y `asignaciones_cerradas: 0`.
- **`alta`** (`p_baja_paciente`, sin cambios de comportamiento): archiva los
  objetivos activos y cierra las asignaciones vigentes.

`POST /pacientes/{id}/reactivacion` limpia `tipo_cierre` y `motivo_baja`.

### Campos nuevos del paciente

`tipo_cierre` (`"pausa"`, `"alta"` o `null` si está activo) y `motivo_baja`.
Una baja anterior a la Entrega 3 (sin tipo) se devuelve como `"alta"`.

### Mínimo de objetivos

- Regla en el trigger `trg_objetivos_limite_activos_update`: archivar un
  objetivo de un paciente **en tratamiento** que deje menos de 3 activos se
  rechaza (`400`, `campo: "id_objetivo"`: «El paciente tiene que mantener al
  menos 3 objetivos activos: cree el reemplazo antes de archivar este»).
  No rige con el paciente de baja, así que el alta no se frena.
- Los pacientes que ya tienen menos de 3 siguen siendo válidos: no se les
  exige crear, solo no pueden archivar hasta llegar a 3.
- `GET /pacientes/{id}` trae `minimo_objetivos` (3) y `faltan_objetivos`;
  el listado trae `faltan_objetivos` por paciente.

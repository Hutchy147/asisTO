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
  "mensaje": "El paciente indicado no existe."
}
```

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
      "objetivos_activos": 1,
      "tiene_login": true
    }
  ],
  "total": 3
}
```

Notas para el diseño de la pantalla:

- `objetivos_activos` va de **0 a 4**. El máximo es 4 (regla de negocio).
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
  "mensaje": "Paciente dado de alta correctamente",
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
| Dado de baja | `404` | `El paciente indicado esta dado de baja.` |

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
      "descripcion": "Objetivo numero 2",
      "fecha_archivado": null,
      "fecha_creacion": "2026-07-30T09:57:43",
      "id": 11,
      "id_paciente": 4
    }
  ],
  "archivados": [
    {
      "activo": false,
      "descripcion": "Sostener el lapiz con pinza tripode",
      "fecha_archivado": "2026-07-30T09:57:43",
      "fecha_creacion": "2026-07-30T09:57:43",
      "id": 8,
      "id_paciente": 4
    }
  ],
  "cupo": {
    "disponibles": 0,
    "maximo": 4,
    "usados": 4
  }
}
```

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

Mandar la misma descripción que ya tenía devuelve `200` sin escribir nada.

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
| GET | `/api/objetivos/paciente/<id>` | `200` |
| POST | `/api/objetivos` | `201` |
| PUT | `/api/objetivos/<id>` | `200` |
| DELETE | `/api/objetivos/<id>` | `200` |

Estados que las pantallas tienen que contemplar:

1. **Paciente sin login** (`tiene_login: false`) — normal, no es un error.
2. **Cupo lleno** (`cupo.disponibles === 0`) — deshabilitar el alta y decir
   por qué.
3. **Objetivos archivados** — hay que poder verlos; guardan la historia.
4. **Descripción repetida** — el error distingue activo de archivado, y la
   interfaz debería explicar que contra un archivado sí se puede.
5. **401 vs 403** — el primero va al login, el segundo a la pantalla de 403.
6. **Paciente de baja** — mensaje distinto al de inexistente.

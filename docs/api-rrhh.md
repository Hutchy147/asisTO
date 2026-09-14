# Contrato de API — RRHH

Base: `/api` · Formato: JSON · Autenticación: `Authorization: Bearer <token>`

**Todos los endpoints de este documento son exclusivos del rol `rrhh`.**

> Los ejemplos de JSON están **copiados de respuestas reales** de la API
> corriendo contra una base descartable, no escritos a mano.

Las convenciones generales (códigos de autenticación, forma de los errores)
son las mismas que en [`api-pacientes-objetivos.md`](api-pacientes-objetivos.md).

Estado: **camino de datos, panel, export a CSV y observaciones técnicas.**
Cerrado el criterio de la HDU 6.

La pantalla es `frontend/src/pages/PanelRrhh.jsx`, ruta `/rrhh`, capacidad
`rrhh.consulta` (entrega 2). Es **de lectura salvo por una cosa**: la
observación técnica sobre una sesión, que es el único camino de escritura del
rol en todo el sistema (ver el final de este documento).

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

### Las doce columnas de una sesión, y ninguna más

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
| `obs_rrhh` | Cuántas observaciones técnicas tiene. Conteo, no texto |

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

---

## Observaciones técnicas — el único camino de escritura de RRHH

Hasta el 2026-09-14 este módulo era de sólo lectura. Hoy tiene **un** endpoint
de escritura, y es este.

**Qué es:** un comentario **administrativo** sobre una sesión, para dejar
constancia de algo que pasó — llegó tarde, faltaba material, se avisó a
coordinación.

**Qué no es:** contenido clínico. **No reemplaza ni modifica
`sesiones.notas`**, que es del terapeuta. Son dos campos de dos personas
distintas sobre el mismo hecho, y la pantalla lo dice con todas las letras
antes de mostrar ninguna.

**No toca la sesión.** Es una fila aparte en `observaciones_rrhh` que la
referencia por FK. Una sesión puede tener varias o ninguna.

### `GET /api/rrhh/sesiones/<id>/observaciones`

De la más nueva a la más vieja.

**200 OK**

```json
{
  "id_sesion": 5,
  "total": 1,
  "observaciones": [
    {
      "id": 16,
      "id_sesion": 5,
      "texto": "Llego 20 minutos tarde. Se aviso a coordinacion.",
      "fecha_registro": "2026-09-14T09:00:52",
      "autor": {
        "id_rrhh": 1,
        "nombre_completo": "Silvia Quiroga",
        "nro_legajo": "LEG-00231"
      }
    }
  ]
}
```

`autor` viaja con **nombre y legajo**, no sólo con id: donde se muestre tiene
que poder leerse de quién es sin pedir otra cosa. Una observación
administrativa sin autor visible es exactamente la que se lee como nota
clínica.

### `POST /api/rrhh/sesiones/<id>/observaciones`

```json
{ "texto": "Llego 20 minutos tarde. Se aviso a coordinacion." }
```

**El autor NO viaja en el cuerpo**: sale del token. Aceptarlo del cliente
dejaría que cualquiera con rol `rrhh` firme con el legajo de otro.

**201 Created** con la observación creada y el `mensaje` del procedimiento.

| Caso | Código |
|---|---|
| `texto` vacío, sólo espacios o ausente | 400 |
| `texto` de más de 1000 caracteres | 400 |
| Sesión inexistente | 400 `La sesion indicada no existe` |
| Sin token | 401 |
| Rol distinto de `rrhh` | 403 |

**No hay `PUT` ni `DELETE`, y es una decisión.** Una observación es la
constancia de algo que pasó; editarla o borrarla después es reescribir el
registro. Si hace falta rectificar, se agrega otra.

### El procedimiento

`p_registrar_observacion_rrhh` — **5 parámetros**:

```
IN p_id_sesion INT UNSIGNED, IN p_id_rrhh INT UNSIGNED, IN p_texto TEXT,
OUT p_id_observacion INT UNSIGNED, OUT p_mensaje VARCHAR(255)
```

**Orden de locks: `sesiones` → `observaciones_rrhh`.** La sesión se toma
`FOR SHARE` antes de insertar; sin eso puede borrarse entre la verificación y
el `INSERT`, y el fallo saldría como error de FK en vez de con mensaje
propio. `observaciones_rrhh` se ubica al final del orden canónico por el
criterio que ya lo fija: se toma después de todo lo que referencia.

### Lo que este endpoint NO abrió

Es la primera puerta de escritura del rol, así que conviene el dato medido:
con token de `rrhh`, los **diez** endpoints de escritura que existen —alta,
edición, baja y reactivación de paciente; registrar y editar sesión; cargar
evolución; crear, editar y borrar objetivo— siguen contestando **403**.
Verificado por HTTP el mismo día, con el POST de observaciones dando 201 en
la misma corrida para que los 403 no puedan ser un token muerto.

### La columna del reporte se llama `obs_rrhh`

`GET /api/rrhh/reporte-sesiones` trae por sesión un **conteo** de
observaciones, para que el panel distinga las que tienen de las que no.

Se llama `obs_rrhh` y **no** `observaciones`, que sería lo natural: en este
proyecto `observaciones` ya significa `evoluciones.observaciones`, que es
clínico, y un test de auditoría bloquea ese nombre en el reporte de RRHH. El
test tenía razón —el nombre era ambiguo—, así que se renombró la columna.

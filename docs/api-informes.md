# API de informes (Entrega 6, HDU 5 y 8)

Informes del tratamiento: **mensual**, **semestral** y **PTI** (plan terapéutico individual). Cada uno se genera como **borrador**, la terapeuta lo revisa y lo edita, y recién al **publicar** queda disponible para la familia. Los publicados no se editan: se **corrigen**, y el historial conserva todas las versiones.

Rol `terapeuta` en todas las rutas. RRHH y el administrador reciben 403: es contenido clínico. **Leer** es abierto entre terapeutas (igual que la ficha clínica); **escribir** exige estar asignado al paciente en el período del informe, y lo hace cumplir la base.

## Rutas

| Método y ruta | Qué hace |
|---|---|
| `GET /api/pacientes/<id>/informes` | Historial completo, de la versión más reciente a la más vieja: `{paciente, informes: [...], total, ia_disponible}` |
| `POST /api/pacientes/<id>/informes` | Genera el informe. Cuerpo: `{tipo, periodo, usar_ia}`. 201 con el informe y `advertencia` (texto si se pidió IA y se usó la plantilla) |
| `GET /api/pacientes/<id>/informes/diarios?tipo=&periodo=` | Diarios del período, para consultar antes de generar |
| `GET /api/informes/<id>` | Un informe con su `contenido` y `contenido_original` |
| `GET /api/informes/<id>/diarios` | Diarios del período de ese informe |
| `PUT /api/informes/<id>` | Guarda el texto de un borrador. Cuerpo: `{contenido}` |
| `POST /api/informes/<id>/publicacion` | Publica el borrador. Avisa al familiar y devuelve `familiares_avisados` |
| `POST /api/informes/<id>/correccion` | Crea un borrador (versión + 1) a partir de uno publicado. 201 |
| `DELETE /api/informes/<id>` | Descarta un borrador |
| `GET /api/informes/<id>/pdf` | PDF del informe (adjunto). Un borrador sale con la marca «BORRADOR» |
| `GET /api/informes/control?mes=AAAA-MM` | Control mensual: pacientes de la terapeuta y estado de sus informes |

## Tipos y períodos

| `tipo` | `periodo` | Cubre |
|---|---|---|
| `mensual` | `AAAA-MM` | El mes; el mes en curso llega hasta hoy |
| `semestral` | `AAAA-S1` o `AAAA-S2` | Enero–junio o julio–diciembre |
| `pti` | se ignora (queda `pti`) | Desde el inicio del ingreso. Exige que el paciente tenga un ingreso iniciado (409 si no) |

Un período que todavía no empezó se rechaza (400).

## Ciclo de vida

`borrador` → `final` (publicado) → `reemplazado` (cuando se publica una corrección). La corrección es un borrador nuevo con `version + 1`; **la versión publicada sigue vigente para la familia hasta que se publica la nueva.**

- Generar sobre un período que ya tiene borrador **regenera ese borrador** (no crea otro).
- Generar sobre un período que ya tiene un publicado: 409, hay que usar la corrección.
- El texto usa una convención mínima: `## Título` abre una sección, `- ` abre un ítem y una línea en blanco separa párrafos.
- Las marcas `[COMPLETAR ...]` son lo que el generador no pudo resolver. **Mientras queden, el informe no se publica** (400).
- Publicar guarda antes el texto que se está viendo en pantalla.

## Generación: plantilla o IA

El generador es un adaptador. Sin configuración usa la **plantilla** del centro y funciona sin red. Si el `.env` define `INFORMES_IA_PROVEEDOR` e `INFORMES_IA_API_KEY` y la terapeuta no apagó `usar_ia`, redacta con IA. Las dos salidas quedan como borrador y se marcan en `generado_con` (`plantilla` o `ia`) y `proveedor`.

- Al proveedor **no se envían el nombre ni el apellido del paciente**: se reemplazan por «el paciente» en todos los datos y la cabecera con el nombre se arma del lado del servidor. Es un resguardo de mejor esfuerzo, no una garantía: un nombre propio de otra persona escrito en una nota libre no se detecta. Por eso la terapeuta siempre revisa antes de publicar.
- Si la IA falla o tarda más que `INFORMES_IA_TIMEOUT`, se genera con la plantilla y la respuesta trae `advertencia`.
- La escala va **siempre en palabras** (No logrado, Inicial, En proceso, Avanzado, Logrado); nunca números ni promedios. Las tendencias salen de `p_tendencia_paciente`.

## Control mensual

`GET /api/informes/control` devuelve, para cada paciente asignado a la terapeuta en el mes: `{id_paciente, paciente, sesiones_registradas, mensual, semestral, pti}`. Cada celda es `{estado, id?, version?}` con `estado` en `publicado`, `borrador`, `pendiente` o `no_corresponde`. El semestral solo corresponde en junio y diciembre; el PTI solo si el paciente tiene ingreso. `resumen` cuenta los mensuales publicados, en borrador y pendientes.

## Errores frecuentes

| Código | Cuándo |
|---|---|
| 400 | Período inválido o futuro; marcas `[COMPLETAR]` sin resolver; contenido vacío |
| 403 | No está asignada al paciente en el período; rol sin acceso |
| 404 | El informe o el paciente no existen |
| 409 | Ya hay un publicado de ese período; PTI sin ingreso |

## Base de datos

Tabla `informes` (UNIQUE `paciente + tipo + período + versión`) y cinco procedimientos con `OUT p_mensaje`: `p_crear_informe`, `p_editar_informe`, `p_publicar_informe`, `p_corregir_informe`, `p_descartar_informe`. En el orden de locks, `informes` va **última** (referencia a pacientes y terapeutas; nada la referencia). Todos los endpoints de escritura van con `@reintentar_en_deadlock`.

## Pruebas

`tests/nube/test_informes_api.py` (API) y `tests/nube/ui_informes.py` (pantalla).

# Auditoría de la V6 — ronda de QA y barrido general

Fecha: 22/10/2026. Alcance: lo que reportaron Leandro, Franco y Tomás en el QA
de la V6, más un barrido rápido de todo el sistema (API, pantallas, lógica y
navegación). Esta nota registra qué se encontró, qué se corrigió y qué queda.

## 1. Corregido

### Lo que reportó el QA
| Tema | Qué pasaba | Corrección |
|---|---|---|
| Alta de Ingreso (Windows) | Los procedimientos guardan la collation de la conexión que los creó. Con el cliente `mysql` de Windows (utf8mb4) quedaban en `utf8mb4_0900_ai_ci` y `JSON_TABLE` chocaba con las tablas (error 1267). En la nube no se veía porque el cliente usa latin1. | `schema.sql` fija `SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci` y declara la collation en las 3 columnas de `JSON_TABLE`. `build_db.sh` carga ahora en utf8mb4: la suite reproduce la condición de Windows. |
| Enumeración de emails | Un email inexistente no se bloqueaba y la recuperación respondía más rápido si la cuenta no existía. | Bloqueo por intentos también para emails sin cuenta; la recuperación tarda lo mismo exista o no la cuenta. |
| Terapeuta no asignado | Podía editar, pausar, dar de alta, reactivar un paciente ajeno y crearle objetivos (solo se bloqueaba en pantalla). | El servidor responde 403 salvo para el responsable vigente. La ficha ya no ofrece esos botones. |
| Paciente pausado | Se podían editar y archivar objetivos. | 409: quedan de solo lectura. |
| Avisos | La familia no se enteraba al cerrar la sesión; una sesión "incompleta" avisaba como si estuviera registrada. | Aviso al pasar a realizada/ausencia, una sola vez por sesión. |
| Asignación | Se podía asignar con fecha anterior al ingreso. | El procedimiento lo rechaza (400). |
| Tildes | Mensajes de la API sin tildes ("contrasena", "esta cerrado"). | Restitución central en la respuesta (`acentuar`) y diccionario ampliado. Frontend: login, gráfico, avisos. |
| Familiares de un paciente de baja | Nadie podía quitar el acceso tras el alta. | Quien fue responsable ve la pestaña Familia y puede quitar accesos (no vincular). |
| Buscador de familiares | `%` y `_` actuaban como comodín. | Se escapan. |
| Informes | "Se registró 22 sesiones"; marcas `[completar]` en minúscula no se detectaban en pantalla; el contador "En borrador" ignoraba PTI y correcciones; una corrección en curso no se veía en el control; un paciente de baja sin sesiones figuraba como Pendiente. | Concordancia, detección sin distinguir mayúsculas, contador completo, "Corrección en borrador" con acceso directo, "No corresponde" para bajas sin actividad. |
| Observaciones en el informe | La familia lee el informe tal cual, observaciones incluidas. | Decisión: no se filtra (el informe lo revisa y publica la terapeuta); se agregó un aviso en el editor. |

### Encontrado en el barrido
| Hallazgo | Gravedad | Corrección |
|---|---|---|
| Un cuerpo JSON que no es un objeto (`[]`, `"x"`, `5`) daba **500** en ~28 endpoints. | Media | `before_request` global: 400 "El cuerpo de la solicitud debe ser un objeto JSON". |
| Un campo con tipo equivocado (número, lista u objeto donde va texto) daba **500** en 11 endpoints (sesiones, objetivos, pacientes, renglones, agenda recurrente, observaciones de RRHH, recuperación de contraseña). | Media | Manejador global: 400 "Alguno de los datos enviados tiene un formato inválido". |
| `POST /pacientes/:id/informes` con `tipo`/`periodo` no textuales. | Baja | 400 con el campo. |
| Test dependiente del día de la semana (`test_preferencias_apagan_el_tipo`). | Baja | Horario distinto en la segunda sesión. |
| Columna "Usuario N" en la auditoría de accesos (no dice nada). | Baja | Pasa a "Registrada" / "Sin cuenta"; el email ya está en su propia columna. |

Verificación: suite de API completa en verde; barrido de los 89 endpoints × 7
identidades (sin sesión + 6 roles) × cuerpos de tipos raros → 0 respuestas 500;
recorrido de pantallas de los 6 roles con Playwright sin errores de consola ni
respuestas 4xx/5xx inesperadas, en los modos de entrega 3, 5 y 6 (30 rutas por modo).

## 2. Pendiente (no se tocó en esta ronda)

- Auditar cambios y recuperaciones de contraseña (requiere ampliar el enum de `auditoria_accesos`).
- Pantalla de administrador para desvincular familiares de cualquier paciente.
- Instrucciones del mail del QA y notas viejas de la documentación.
- F6.1 (pasar `area` al editar una plantilla), F4.4 (sugerencia de número de historia), F5.3 (encontrar pacientes pausados), vocabulario alta/baja/pausa.
- F5/H32 (pestaña, paciente y filtros en la URL), T4.1 (editar renglones), H8/H13/H15/H21/H22/H25/H27/H34/H40.
- Nombres de estados ("En registro"/"incompleta"), F5.5 (error mostrado como éxito).
- Paginación del PDF de informes, nombre del PTI, mes repetido en la tabla de control.
- H37: salida para el paciente en los modos de demostración 4/5.
- `DialogoConfirmacion` anida `<ul>` dentro de `<p>` (aviso de React), el 403 muestra el nombre interno del rol.
- Ruido de log: los errores de negocio de la base (triggers) se registran como ERROR con traza; conviene bajarlos a WARNING.
- La deduplicación del aviso de cierre es por fecha y paciente: dos sesiones del mismo día generan un solo aviso.

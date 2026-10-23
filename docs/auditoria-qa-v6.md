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
- Ruido de log: los errores de negocio de la base (triggers) se registran como ERROR con traza; conviene bajarlos a WARNING.

## 3. Segunda pasada (22/10/2026, auditoría profunda)

Barrido de los 89 endpoints con parámetros de consulta raros (fechas extremas,
números mal formados), cuerpos mal formados y content-types distintos; escrituras
cruzadas entre terapeutas, familiares y roles; lectura de código del backend y
del frontend (lint con reglas de hooks); recorrido de pantallas de los 6 roles en
los modos 6 y 3, con reloj simulado a las 23:30.

| Hallazgo | Gravedad | Corrección |
|---|---|---|
| Una fecha válida pero extrema (`9999-12-31`) en `desde`/`hasta` daba **500** en 6 endpoints (sesiones, registradas, evolución, portal familiar, portal del paciente, auditoría). | Media | Manejador global: 400 «Alguna de las fechas indicadas está fuera del rango permitido». |
| `GET /familiar/notificaciones?id_paciente=abc` daba **500**. | Baja | 400 con `campo: id_paciente`. |
| Al anonimizar los datos para la IA, el nombre se reemplazaba como subcadena: «Ana» rompía «semana», «Paz» rompía «capaz», y «Lucia» no tapaba «Lucía». | Media | Reemplazo por palabra entera y sin distinguir tildes. |
| RRHH y Auditoría armaban el rango por omisión con `toISOString()` (UTC): después de las 21 h la fecha «hasta» era mañana. | Baja | Fecha local (`aIsoLocal` en `utils/fechas.js`). |
| Edad en meses (menores de un año) leía la fecha en UTC: el día 1 contaba un mes de más y no miraba el día del mes. | Baja | Cálculo con las partes de la fecha. |
| Portal familiar y del paciente: el campo «Desde» quedaba más abajo que «Hasta». | Baja | Mismo espacio de ayuda en los dos campos. |
| Exportación CSV de RRHH: un nombre que empieza con `=`, `+`, `-` o `@` se ejecutaba como fórmula en Excel. | Baja | Se antepone un apóstrofo a esos textos. |
| Dos sesiones del mismo paciente el mismo día generaban un solo aviso de cierre. | Baja | El texto del aviso lleva la hora («del 22/10/2026 a las 15:00»). |
| Mensajes sin tilde: renglón, vacía, después, límite, reactívelo, válida, creó, vínculo. | Baja | Agregadas al diccionario de `acentuar`. |
| `DialogoConfirmacion` anidaba `<ul>` en `<p>`; el 403 mostraba la clave interna del rol. | Baja | `div` en vez de `p`; nombre legible del rol. |
| Generar informe semestral ofrecía (y preseleccionaba entre enero y junio) el segundo semestre del año en curso, que todavía no empezó. | Baja | Solo semestres ya empezados. |
| `FLASK_DEBUG` valía 1 si faltaba en el `.env`: depurador de Werkzeug encendido y el token de recuperación en la respuesta. | Media | Sin la variable, 0. `.env.example` sigue pidiendo 1 para desarrollo. |
| Prueba de pantalla `ui_seguridad` esperaba «se genero» sin tilde (quedó vieja con la ronda anterior). | Baja | Actualizada. |
| Código muerto: import de `Dashboard`, `hoyIso`, `MARCA`, import de `Paciente` en sesiones. | — | Quitado. |

Verificación: suite de API 177 OK (5 pruebas nuevas en `test_auditoria_profunda.py`);
sondeo de 500 → 0; pruebas de pantalla `ui_portal_familiar`, `ui_portal_paciente`,
`ui_notificaciones`, `ui_seguridad`, `ui_auditoria` e `ui_informes` en verde;
recorrido de los 6 roles sin errores de consola en los modos 6 y 3.

## 4. Tercera pasada (23/10/2026): pendientes, QA completo y seguridad

Se tomaron los informes finales de Leandro (H1–H40), Tomás (T1.5, T4.1, T7.2,
T7.4, ORTO-01) y Franco (F1–F11) y los pendientes de la sección 2, se
verificó cada uno contra el código actual y se corrigió lo que seguía abierto.

### Corregido
| Hallazgo | Qué pasaba | Corrección |
|---|---|---|
| H9, H10, F4.3, T1.5 | En la versión completa el calendario era solo la semana tipo: no había dónde agendar una sesión puntual ni cómo cambiar de semana. | Selector «Semana tipo / Agenda por fecha». La agenda por fecha navega semanas, agenda, reprograma y abre el detalle. La vista y la semana van en la URL. |
| H32, F5 transversal | F5 volvía a la primera pestaña, al primer paciente del portal o a la página 1. | Pestaña de la ficha, paciente del portal y de informes, filtros y página de Sesiones, mes del control y filtro de Pacientes en la URL (`useEstadoEnUrl`). |
| T4.1 | Los renglones no se podían editar. | Botón «Editar» en el lugar (Enter guarda, Escape cancela). |
| F5.3 | Un paciente pausado solo se encontraba por URL. | Filtro «En pausa o con alta» en Pacientes (`GET /pacientes?estado=inactivos`). |
| F4.4 | El N.º de historia de ejemplo ya estaba usado. | El listado devuelve `siguiente_nro_historia` (el siguiente libre, contando todos los pacientes). |
| F5.5 | Archivar por debajo de 3 se rechazaba con un aviso verde. | Se avisa antes de abrir la confirmación, en amarillo; los rechazos del servidor salen en rojo. |
| F6.1 / F6.2 | Editar una plantilla abría el Área vacía; el duplicado marcaba el Área; pegar más de 700 caracteres cortaba sin avisar. | El área viaja al editar; el duplicado marca el texto; el campo avisa cuando recorta lo pegado. |
| H21 / H22 / H30 | Con una sola fecha el rango era de 8 días; un período futuro daba «del 01/12 al 22/10»; el portal mostraba la sesión de hoy antes de su hora. | `resolver_rango_pasado`: solo «desde» llega hasta hoy, solo «hasta» arranca en el ingreso, «desde» futuro es 400 y los campos no ofrecen días futuros. El portal mira la hora. |
| H34 | `2026-02-30` decía «formato incorrecto». | «La fecha … no existe en el calendario.» |
| H26 | Avisos: filtros inválidos ignorados, paciente no vinculado 200. | 400 con el campo y 403; los avisos de un paciente desvinculado dejan de verse. |
| T7.2 | Un semestral publicado figuraba en mayo. | El semestral solo se controla en junio y diciembre. |
| H7 / H12 | La misma sesión se llamaba «En registro», «incompleta» e «Incompleta». | Desde la V3, en todas las pantallas: Realizada / En registro / Ausente. |
| H8 | «Sin cuenta» parecía hablar del familiar. | «Portal del paciente: con / sin acceso», con explicación. |
| H13, H11, H15, H19, H20, H29, H31, H36, H37 | Contadores ambiguos, Reabrir sin explicación, duplas sin horario, ingreso ajeno que pedía acciones imposibles, pacientes ajenos en «Mis sesiones», avisos de informes en modos 4/5, dos textos para «pocos datos», «Retrocede» sin explicación, paciente sin salida en modos 4/5. | «marcados»/«calificados», ayuda de Reabrir, horario en la dupla, textos de solo lectura, filtro de pacientes propios, tipos de aviso por capacidad, «Sin datos suficientes» en los dos casos, ayuda de tendencia y «Cerrar sesión» en la pantalla fuera de entrega. |
| H16 | Nadie con pantalla podía quitar el acceso de la familia a un paciente de baja. | Botón «Familia» en la pantalla del administrador (solo quitar si el paciente no está en tratamiento). |
| F1.3 | Con un enlace usado se completaban las dos claves antes de enterarse. | `POST /auth/restablecer/verificar` al abrir la pantalla. |
| Vocabulario alta/baja/pausa | «Alta» significaba ingreso y fin; «baja» también la pausa. | Crear: «Paciente registrado». Dar el alta: «Alta del tratamiento registrada». Pausa: «Motivo de la pausa». Mensajes: «no está en tratamiento activo». Pruebas de la base actualizadas. |
| PTI | «individual» e «integral» en la misma pantalla. | «integral» en todas partes. |
| H35 | 41 mensajes «por un error interno». | «por un problema inesperado. Intente nuevamente.» |
| Plurales | «1 sesión(es)», «2 campo(s)», «1 etapa(s)», «objetivo(s)». | Concordancia en pantalla y en los procedimientos. |
| F8.4 / F8.6 / mes repetido | Marca `[completar` sin corchete no se detectaba; el error del diálogo quedaba fuera de la vista; «Descartar» en verde; mes duplicado en el control. | Misma regla que el servidor; el error se desplaza a la vista; botón rojo; solo el aviso de semestre. |
| H3, ORTO-01, H24, H28 | Seed de demostración sin tildes, avisos de sesiones que no existen, pacientes con 2 objetivos. | Seed con tildes (como bytes UTF-8: el archivo sigue ASCII), avisos generados de los datos reales, 3 o 4 objetivos por paciente. |
| Auditar contraseñas (pendiente) | Recuperaciones y cambios de clave no quedaban auditados; la cuenta deshabilitada figuraba como «Fallido». | Resultados `recuperacion`, `restablecida` e `inactiva`. |
| Ruido de log (pendiente) | Las reglas de negocio de la base salían como ERROR con traza. | WARNING sin traza. |
| Pruebas | Dos pruebas fallaban según el día de la semana; `tests/backend` tenía 7 pruebas desactualizadas. | Horarios y limpieza corregidos; `tests/backend` en verde. |

### Seguridad
Ver `docs/seguridad.md`: sesión en cookie HttpOnly con defensa CSRF, revocación
al cerrar sesión y al cambiar la clave, límites por IP, política de claves,
cabeceras, configuración insegura que no arranca y dependencias sin fallas
conocidas.

### Decisiones (no se cambian)
- **Avisar cuántos intentos quedan (F2):** no; permitiría distinguir emails con cuenta.
- **Borradores ajenos:** cualquier terapeuta los lee (lectura clínica abierta) y una coasignada en el período puede descartarlos: ambas son responsables del paciente.
- **Observaciones en el informe (H23):** se mantiene la decisión de la sección 1.

### Verificación
Suite de API (`tests/nube/run.sh`) en verde con las pruebas nuevas
`test_qa_segunda_ronda` y `test_seguridad_web`; `tests/backend` en verde; las 19
pruebas de pantalla en verde (nuevas: `ui_correcciones_qa`, `ui_seguridad_web`);
barrido de todas las rutas GET × 8 identidades sin 500 ni accesos indebidos;
`pip-audit` limpio.

## 5. Pruebas de usabilidad (23/10/2026)

Doce personas simuladas, cada una con un subagente que **no podía leer el
código ni la base**: solo veía la pantalla (navegador real, capturas) y hacía
tres tareas de su rol. Cuatro roles (terapeuta, RRHH, padre, madre) por tres
niveles de conocimiento de computación (sin, medio, mucho). Se corrigió entre
una ola y la siguiente, así que cada ola probó la versión ya corregida.

| Rol | Sin conocimiento | Medio | Mucho |
|---|---|---|---|
| Terapeuta | 6/10 | 7/10 | 6/10 |
| RRHH | 6/10 | 7/10 | 8/10 |
| Padre | 6/10 | 7/10 | 8/10 |
| Madre | 5/10 (celular) | 7/10 | 7/10 |

La nota es la que puso cada persona **antes** de las correcciones de su ola.
La del terapeuta con mucho conocimiento baja porque probó casos borde que las
otras no (reprogramar una sesión ya calificada, corregir una calificación).

### Lo más importante que encontraron y se corrigió
- **Datos equivocados:** una sesión futura figuraba «Falta la evolución»; el
  informe mensual contaba como realizadas sesiones en registro (14 contra 10 de
  la lista); una sesión calificada se podía reprogramar al futuro (ahora lo
  rechaza la base: `trg_sesiones_solape_update`); la frase de tendencia del
  portal contradecía el gráfico; la misma sesión tenía tres estados distintos
  según la pantalla; la exportación de RRHH bajaba datos de otro período con
  un rango de fechas inválido.
- **Corregir lo que se cargó mal:** `PUT` y `DELETE /api/evoluciones/<id>`
  (p_corregir_evolucion), solo con el registro abierto; una sesión terminada se
  muestra en lectura y se reabre para cambiarla.
- **Familias:** explicación de cada nivel, atajos de período, resumen de
  asistencia, hora bien escrita, gráfico legible en el celular, avisos que
  respetan la preferencia, el hijo elegido se conserva entre secciones.
- **RRHH:** filtro «Mostrar» (solo ausencias, por quién faltó, sin cerrar),
  «Mostrar más» en el listado, totales de la auditoría que cierran, hora con
  segundos, aviso de filtros sin aplicar.
- **Seguridad:** aviso al entrar de los intentos fallidos desde el ingreso
  anterior, la clave nueva tiene que ser distinta de la actual, el 403 no
  sobrevive al cierre de sesión (ni la caché de Atrás), aviso contra phishing
  en la recuperación.

### Lo que no se cambió
- **Formato de fecha mm/dd/aaaa:** lo pone el navegador según su idioma. Con el
  navegador en español sale dd/mm/aaaa (verificado). Las pruebas lo vieron en
  inglés porque el Chromium de pruebas estaba en inglés.
- **Editor del informe con «##» y «- »:** sigue siendo texto con marcas; un
  editor con formato es trabajo nuevo.
- **Campo «reposición» al agendar y vínculo con la ausencia:** funcionalidad
  nueva, fuera de alcance.
- **Dos ventanas para cargar evolución** (Registro del día y Cargar evolución):
  se mantienen; la del Panel es la principal.
- **Texto escrito sin «Agregar» se pierde al cerrar:** queda como mejora.
- **Bloqueo a los 5 intentos y sin contador de intentos restantes:** decisión
  de la sección 4 (F2).

### Verificación
`tests/nube/run.sh` (incluye `test_usabilidad_ola3`), `tests/backend` y las 21
pruebas de pantalla (nuevas: `ui_usabilidad_ola2`, `ui_usabilidad_ola3`).

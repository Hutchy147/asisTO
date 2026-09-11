# Reglas de negocio: dónde vive cada una, y por qué ahí

Las siete reglas del dominio, el lugar exacto donde están escritas, y el
criterio que decide ese lugar.

---

## 1. El principio de fondo

> **Una regla que vive en un solo camino de escritura se elude por cualquier
> otro.**

Es el criterio que ordena todo este documento. Una regla implementada sólo en
el servicio de aplicación la esquiva un `INSERT` directo, un script de
migración, un `CALL` al procedimiento o un endpoint que todavía no existe. La
base es el único punto por el que pasa **todo**: la API, un script, alguien
con un cliente de MySQL abierto.

De ahí salen dos corolarios que este proyecto ya pagó por aprender:

**a) Cada regla vive en la base, y la aplicación traduce el veredicto — no lo
reimplementa.** Si el backend duplicara la validación, en algún momento las
dos versiones dirían cosas distintas y habría que averiguar cuál miente.

**b) Una regla necesita las DOS puertas: INSERT y UPDATE.** El patrón *"se
valida en INSERT pero no en UPDATE"* apareció en tres tablas a la vez y se
cerró con un `BEFORE UPDATE` por tabla, espejo del `BEFORE INSERT`, con los
mismos mensajes. Sin eso, el límite de objetivos activos se saltea con un
`UPDATE` en vez de un `INSERT`, y la regla del solape se elude moviendo una
sesión en vez de creándola.

### 1.1. Los tres casos que lo demostraron

| Caso | Dónde vivía | Cómo se eludía | Dónde vive ahora |
|---|---|---|---|
| **Solape de sesiones** (regla 6) | sólo en `p_registrar_sesion` | cualquier `INSERT`/`UPDATE` directo | trigger en la tabla; el procedimiento **conserva** su validación como mensaje legible |
| **Autoría de la evolución** | sólo en el servicio de aplicación | un `CALL` directo al procedimiento | `p_registrar_evolucion` exige `p_id_terapeuta` y **rechaza `NULL`** |
| **Paciente dado de baja** | sólo en una función de lectura de la aplicación | crear objetivo, desarchivar objetivo o abrir asignación por SQL directo | las cuatro ramas de trigger correspondientes |

El del medio tiene un matiz que vale: el caso que más importa no es que el
terapeuta no coincida, sino que venga **`NULL`**. Si `NULL` pasara, **omitir
el autor equivaldría a un permiso**. El 403 de la capa de aplicación se
mantiene igual: son dos defensas contra dos amenazas distintas.

El de la baja se midió por SQL directo, sin pasar por la aplicación, y dio
esto:

| Camino | ¿Lo frenaba la base? |
|---|---|
| Registrar sesión | **Sí** |
| Crear objetivo | **No** |
| Desarchivar un objetivo | **No** |
| Abrir una asignación | **No** |

Los tres huecos dejaban el mismo estado: **un paciente inactivo con un objetivo
activo o una asignación vigente**. El de desarchivar era el más barato de
explotar y el peor: deshace parte de la baja **sin tocar `pacientes`**, así que
ni siquiera hay que dar de alta nada.

### 1.2. El momento barato es antes de que exista el endpoint

La regla de asignaciones se cerró cuando **todavía no había endpoint de
asignaciones**. Decidirlo entonces costó cuatro líneas de trigger; después
habría costado una migración sobre datos.

### 1.3. Duplicación deliberada entre INSERT y UPDATE

Los pares de triggers son **copias explícitas**, no un cuerpo compartido, y es
una decisión:

- En MySQL no hay forma limpia de compartir el cuerpo entre dos triggers: un
  procedimiento auxiliar no puede leer `NEW` y agrega una capa que oscurece
  qué se valida.
- Tener los dos cuerpos a la vista hace evidente, al revisarlos, si uno quedó
  desactualizado respecto del otro.

**El riesgo conocido es que uno quede viejo. La contramedida es la regla: si se
toca uno, se toca el otro en el mismo commit.** Y los mensajes de las dos
puertas son idénticos **palabra por palabra** — hay un test que compara los
textos carácter por carácter justamente para sostener eso.

---

## 2. Las siete reglas

### Regla 1 — Máximo 4 objetivos ACTIVOS por paciente

Un objetivo **archivado no consume cupo** y se puede recrear con la misma
descripción (escenario clínico normal: se retoma un objetivo viejo).

| Dónde vive | Qué hace ahí |
|---|---|
| `trg_objetivos_limite_activos_insert` | rama `NEW.activo = TRUE`: lock de `pacientes` + conteo `FOR SHARE` |
| `trg_objetivos_limite_activos_update` | el mismo límite **al reactivar** un objetivo archivado, y al mover un objetivo activo a otro paciente |
| `objetivos_terapeuticos.descripcion_activa` + UNIQUE | hace posible archivar y recrear con el mismo texto |

**Por qué el segundo trigger no es opcional:** sin él, el límite se saltea con
un `UPDATE` en vez de un `INSERT`.

**Cómo funciona lo de recrear con el mismo texto.** `descripcion_activa` es una
columna **generada STORED** que replica la descripción sólo si el objetivo está
activo, y `NULL` si está archivado. La UNIQUE va sobre
`(id_paciente, descripcion_activa)`. En MySQL los `NULL` no participan de una
UNIQUE, así que las filas archivadas quedan exentas **automáticamente**. Con
una UNIQUE sobre `descripcion` a secas, archivar y recrear fallaría.

**Regla vecina, de la misma tabla: la descripción de un objetivo ARCHIVADO es
inmutable.** El motivo no es técnico — un objetivo archivado tiene evoluciones
colgando, y reescribir su texto dejaría calificaciones históricas puntuando
contra algo que hoy dice otra cosa. Estos registros respaldan el tratamiento
ante obras sociales e instituciones: **el pasado no se reescribe.** Reactivar y
reescribir en la **misma** sentencia también se rechaza: el objetivo todavía
estaba archivado cuando se pidió el cambio.

### Regla 2 — No se puede cargar evolución si la sesión está marcada como ausencia

| Dónde vive | Qué hace ahí |
|---|---|
| `trg_evoluciones_validar_insert` | lee `sesiones.estado` con `FOR SHARE` y rechaza |
| `trg_evoluciones_validar_update` | espejo exacto |
| `trg_sesiones_solape_update` | **la puerta inversa:** rechaza pasar a `ausencia` una sesión que ya tiene evoluciones cargadas |

La tercera fila es la parte que se olvida. Sin ella, la regla se cumple al
cargar la evolución y se viola después, cambiando el estado de la sesión.

### Regla 3 — El objetivo evaluado debe pertenecer al paciente de esa sesión

| Dónde vive | Qué hace ahí |
|---|---|
| `trg_evoluciones_validar_insert` / `_update` | compara el paciente de la sesión contra el del objetivo |
| `trg_objetivos_limite_activos_update` | rechaza **mover** a otro paciente un objetivo que ya tiene evoluciones |

La segunda fila cierra la violación **retroactiva**: mover un objetivo a otro
paciente deja las evoluciones ya cargadas apuntando a un objetivo cuyo paciente
no coincide con el de sus sesiones.

### Regla 4 — No se puede cargar evolución sobre un objetivo archivado

Vive en `trg_evoluciones_validar_insert` / `_update`, leyendo
`objetivos_terapeuticos.activo` con `FOR SHARE`.

**Se evalúa antes que la regla 3, y ese orden es load-bearing.** Ver §3.

### Regla 5 — El login del paciente es opcional

Es la única de las siete que **no es un trigger**: vive en la forma de la
tabla.

```sql
id_usuario  INT UNSIGNED NULL DEFAULT NULL,
...
UNIQUE KEY uq_pacientes_usuario (id_usuario),
CONSTRAINT fk_pacientes_usuario
  FOREIGN KEY (id_usuario) REFERENCES usuarios (id)
  ON DELETE SET NULL ON UPDATE CASCADE
```

Tres decisiones ahí adentro:

- **`NULLABLE` a propósito.** El login sólo se le ofrece a mayores de edad con
  capacidad de usarlo. Un menor existe como registro clínico completo, **sin
  credenciales**.
- **La UNIQUE sobre `id_usuario` permite varios `NULL`** (así funciona UNIQUE
  en MySQL), que es justo lo que hace falta: N pacientes sin login, pero un
  usuario no puede estar vinculado a dos pacientes.
- **`ON DELETE SET NULL`:** si se borra el usuario, el paciente sobrevive y
  pierde sólo el acceso. **Nunca se pierde la historia clínica.**

Por eso `nombre`, `apellido` y `fecha_nacimiento` viven en `pacientes` y **no**
en `usuarios`: esa tabla es la fuente de verdad de la identidad clínica, tenga
login o no. No mover esos campos a `usuarios`.

### Regla 6 — Un terapeuta no puede tener dos sesiones solapadas

| Dónde vive | Qué hace ahí |
|---|---|
| `trg_sesiones_solape_insert` | lock de `terapeutas` + conteo de superpuestas `FOR SHARE` |
| `trg_sesiones_solape_update` | el chequeo corre **sólo si cambió algo del horario** |
| `p_registrar_sesion` | conserva su validación, que devuelve `p_mensaje` en vez de un error |

**Los tres, no dos.** El procedimiento existe para dar un mensaje legible por
el camino normal; los triggers son la red de seguridad para cualquier otro
camino de escritura. El criterio de solape es **idéntico** en los tres.

Dos detalles del criterio, los dos decisiones tomadas:

- **Se usa `<` y `>`, no `<=` y `>=`.** Una sesión que termina 10:00 y otra que
  arranca 10:00 **se tocan, no se pisan**. Si `hora_fin` es `NULL` se asume una
  hora de duración.
- **Las sesiones en `ausencia` TAMBIÉN bloquean el horario.** El paciente
  faltó, pero el turno estaba ocupado igual.

### Regla 7 — No se puede calificar una sesión contra un objetivo creado DESPUÉS de esa sesión

Vive en `trg_evoluciones_validar_insert` / `_update`, y **va última** en los
dos. Ver §3 para el orden.

**Por qué es una regla y no una molestia.** `p_evolucion_paciente` arma las
series con los objetivos **vivos al momento de cada sesión**
(`o.fecha_creacion <= TIMESTAMP(s.fecha, s.hora_inicio)`), así que una
evolución sobre un objetivo creado después **no entra en ninguna serie, con
ningún rango de fechas que se pida**. Es una escritura que la lectura no puede
devolver nunca: el sistema la acepta, contesta 201, y después no la muestra en
ningún lado.

**Aceptar lo que la lectura nunca puede devolver es pérdida silenciosa, y por
eso se corta en la escritura.**

El caso que la originó se encontró buscando otra cosa: un paciente tenía 38
evoluciones en el período y sólo **37** entraban en alguna serie. La que
faltaba estaba contra un objetivo creado **nueve días después** de su sesión.

**Se midió antes de aplicarla**, y ese paso no era opcional: en la base con
datos reales había **1 fila así sobre 460** evoluciones; en los dos seeds
recién cargados, **cero**. Un trigger que afirma que algo no puede pasar
mientras el seed lo hace sería peor que no tenerlo.

> **El trigger no arregla la fila que ya está. Sólo cierra la puerta.** Las
> filas preexistentes que violan una regla nueva son una decisión aparte, y se
> toma explícitamente — ver §5.

---

## 3. El orden de evaluación dentro de los triggers de evoluciones

**Es load-bearing y es idéntico en los dos triggers. Tiene que seguir
siéndolo.**

Un solo trigger valida las cuatro reglas, y no tres triggers separados, porque
las validaciones necesitan **los mismos dos `SELECT`** (la sesión y el
objetivo): separarlas multiplicaría las consultas por tres para el mismo
`INSERT`, y el orden de disparo entre triggers del mismo evento no sería
explícito. Cada regla conserva su propio mensaje de error.

El orden es:

```
1. Guardas de existencia   ¿existe la sesión? ¿existe el objetivo?
2. Regla 2                 sesión marcada como ausencia
3. Regla 4                 objetivo archivado
4. Regla 3                 objetivo de otro paciente
5. Regla 7                 objetivo creado después de la sesión
```

### 3.1. Por qué la regla 4 va ANTES que la 3

**Un solo `UPDATE` puede violar las dos a la vez:** mover la evolución a un
objetivo que está archivado **y además** es de otro paciente.

Cuando pasan las dos, la que hay que reportar es **el objetivo archivado**: es
la condición que el terapeuta puede corregir por sí mismo, desarchivando o
eligiendo otro. Decirle primero que el objetivo es de otro paciente lo manda a
resolver el problema equivocado.

### 3.2. Por qué la regla 7 va última

Porque es **estrictamente aditiva**: es la única de las cuatro que **no cambia
el veredicto de ninguna entrada que las otras tres ya rechazaban**.

Puesta en el medio, le cambiaría el mensaje a casos que hoy ya se rechazan por
otro motivo. Puesta al final, sólo habla cuando el objetivo ya demostró ser un
objetivo legítimo de ese paciente y no archivado. Decirle a alguien *"ese
objetivo no existía todavía"* sobre un objetivo que además es de otro paciente
lo mandaría a corregir lo que no importa.

### 3.3. Qué no cambió al agregarla

La regla 7 **no sumó ningún lock ni ninguna tabla al orden de adquisición**:
las tres columnas que necesita —`fecha`, `hora_inicio` y `fecha_creacion`—
salen de los **mismos dos `SELECT`** que ya estaban, con su mismo `FOR SHARE` y
en el mismo orden (`sesiones` antes que `objetivos_terapeuticos`). Ver
[`concurrencia.md`](concurrencia.md).

---

## 4. Reglas derivadas que viven en los mismos triggers

No son parte de las siete, pero se implementan con el mismo criterio y
conviene tenerlas ubicadas.

### 4.1. Paciente dado de baja

**El corte es la FECHA de la sesión contra `fecha_baja`, no el estado del
paciente.** El caso real es la terapeuta que atendió el viernes y recién carga
el lunes; si entre medio el paciente se dio de baja, esa sesión **ocurrió
igual** y tiene que poder registrarse. Lo que se rechaza es una sesión
**posterior** a la baja, que no ocurrió.

Sin esa distinción, la única salida sería reactivar, cargar y volver a dar de
baja — lo que además **pisa `fecha_baja`**: la corrección de un olvido
administrativo terminaría falseando la fecha del alta médica.

Vive en **tres puertas para sesiones** (`p_registrar_sesion` y los dos triggers
de solape, con **mensaje idéntico** en las tres) y en **cuatro ramas de
trigger** para objetivos y asignaciones.

**El chequeo del `UPDATE` corre bajo una condición angosta**, y la angostura es
el punto:

- Si corriera **sólo cuando cambia el horario**, se abre el agujero de mover la
  sesión a otro paciente de baja sin tocar la hora.
- Si corriera **siempre**, una sesión agendada legítimamente mientras el
  paciente estaba activo queda **congelada**: después de la baja no se la puede
  marcar como ausencia, ni cargarle una nota, ni nada. La única salida sería
  borrarla o reactivar al paciente.

Los dos son la misma condición mirada desde dos lados. Lo que separa los casos
es correr el chequeo **sólo cuando cambia `fecha` o cambia `id_paciente`**. Con
eso, mover la sesión sigue rechazado y cerrar una sesión ya agendada vuelve a
ser posible. Reescribir la **misma** fecha (`SET fecha = fecha`) se acepta: se
mira si el valor cambió, no si la columna se tocó.

### 4.2. Ausencia y quién faltó viajan juntos

En los dos triggers de `sesiones`, y en las dos direcciones:

- `estado = 'ausencia'` con `ausencia_de` en `NULL` → rechazado.
- `ausencia_de` cargado con un estado que no es `ausencia` → rechazado.

Va **primero** dentro del trigger, antes de cualquier lock: compara `NEW`
contra sí misma, no lee ninguna tabla, así que no tiene sentido gastar el lock
de `pacientes` en una fila que de todos modos se va a rechazar.

### 4.3. El estado de la sesión es obligatorio

El procedimiento de registro tenía un `IFNULL(p_estado, 'incompleta')`. Un
`CALL` directo sin estado entraba igual, **declarado como si alguien hubiera
dicho "incompleta" sin haberlo dicho**. Es la misma clase de hallazgo que el
resto de este documento: la regla se había cerrado en la capa de aplicación y
este otro camino de escritura la eludía.

Se midió antes de aplicar el cambio: los llamadores existentes del
procedimiento **mandaban todos un estado explícito**, ninguno dependía del
default.

---

## 5. Qué hacer con las filas que ya violan una regla nueva

Una regla nueva no puede reescribir el pasado, y **el criterio tiene que ser
una decisión dicha, no un efecto**.

Los dos casos resueltos hasta hoy:

- **Una evolución sobre un objetivo posterior a su sesión** (1 fila) se
  **borró**, después de dejar registrado qué era y por qué no podía verse en
  ningún gráfico.
- **Las sesiones `ausencia` sin `ausencia_de`** (59 filas) se **dejaron en
  `NULL`**. Nadie puede reponer retroactivamente quién faltó, así que inventar
  un valor sería peor que dejarlo vacío.

La consecuencia del segundo caso se declaró explícitamente, porque no es
obvia:

- Por `CALL` directo o por un `UPDATE` que no toca `estado` ni `ausencia_de`,
  esas filas **nunca se revalidan**: la guarda del trigger las deja en paz.
  Editar sólo las notas de una de ellas sigue funcionando.
- Por la interfaz, el formulario pide el campo **cada vez** que el estado es
  `ausencia`, así que la primera vez que alguien abra una de esas filas para
  editar cualquier cosa tendrá que completar quién faltó. **Es el mecanismo por
  el que esas filas se completan solas con el uso normal**, sin script de
  relleno ni dato inventado. No es un bloqueo nuevo.

---

## 6. Cómo se verifica que una regla está donde dice estar

Las siete se prueban **por el camino directo**: SQL crudo contra la base, sin
pasar por la aplicación. Ese es justamente el camino que la ubicación en el
trigger promete cerrar; probarlas por la API no distinguiría una regla que vive
en la base de una que vive en el servicio.

Lo que cada test tiene que afirmar, mínimo:

1. El caso prohibido **se rechaza**.
2. El rechazo **no deja fila** (ni la inserta ni la deja a medias).
3. El caso legítimo vecino **se acepta** — si no, la regla podría estar
   rechazando de más.
4. El **mensaje** es el esperado, y es idéntico en todas las puertas de esa
   regla.

Y el test se falsa mutando el trigger **dentro de una base descartable**
(`DROP` + `CREATE`, sin tocar el schema fuente) para confirmar que se pone en
rojo. Ver [`verificacion.md`](verificacion.md) §1 y
[`base-de-datos.md`](base-de-datos.md).

> **Cuidado con las cascadas al leer una falsación.** Al mutar un trigger, un
> caso puede ponerse en rojo **por sí mismo** y arrastrar otros que comparten
> fixture. La señal propia es el primero; los demás confirman. Conviene decirlo
> al reportar, o el número de rojos exagera lo que la mutación demostró.

---

## 7. Nota sobre el conteo

Las reglas son **siete**. La séptima se agregó después de que se escribieran
varios de los artefactos que las cuentan, así que quedan referencias vigentes a
"las 6 reglas de negocio" — entre ellas la tabla de estado del `README.md` y el
nombre del módulo de regresión `tests/db/reglas_negocio/test_reglas_1_a_6.ps1`.

Es un conteo que quedó corto, no un desacuerdo sobre qué reglas existen: la
séptima está implementada en los dos triggers y descrita arriba. Cuando esos
artefactos se toquen por otro motivo, el número se ajusta.

---

## Documentos relacionados

- [`concurrencia.md`](concurrencia.md) — cómo toma los locks cada trigger.
- [`verificacion.md`](verificacion.md) — cómo se prueba una regla.
- [`base-de-datos.md`](base-de-datos.md) — bases descartables para falsar.

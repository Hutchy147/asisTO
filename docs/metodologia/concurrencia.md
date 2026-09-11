# Concurrencia

Orden de adquisición de locks, forma de tomarlos y reintento ante deadlock.

**No son sugerencias de estilo.** Cada punto de este documento sale de un
deadlock o de una condición de carrera **reproducidos**, con dos o más
conexiones simultáneas y el contador de InnoDB como testigo. Las secciones
traen el escenario exacto que las originó.

Vinculante para todo el código que escriba en la base: procedimientos
almacenados, triggers y servicios de aplicación.

---

## 1. Orden de adquisición de locks

Cualquier operación que toque varias tablas las bloquea **siempre** en este
orden:

```
pacientes → terapeutas → asignaciones → sesiones →
objetivos_terapeuticos → evoluciones
```

Invertirlo produce deadlocks reales, ya reproducidos. Si una transacción
necesita `objetivos_terapeuticos` y `sesiones`, toma `sesiones` primero,
aunque el código quede menos natural.

Aplica igual a **triggers y procedimientos almacenados**, no sólo al código de
aplicación.

### 1.1. El criterio que fija el orden

**Una tabla se toma después de todas las que referencia.**

Ese criterio es lo que permite ubicar una tabla nueva sin tener que reproducir
un deadlock primero. Se usó por primera vez con `asignaciones`, que se agregó
al orden cuando el módulo de baja de pacientes fue la primera operación que la
tocaba junto con otras tablas: va entre `terapeutas` y `sesiones` porque
apunta a `pacientes` y a `terapeutas`, y nada la apunta a ella.

> **Una tabla nueva se ubica ANTES de escribir la primera línea de la consulta
> que la lee, no después.** Meter una tabla sin posición asignada en medio de
> una secuencia de locks existente es exactamente la clase de cosa que produjo
> los deadlocks que esta convención vino a evitar.

### 1.2. Qué respeta el schema, tramo por tramo

| Tramo | Dónde |
|---|---|
| `pacientes` → `objetivos_terapeuticos` | los dos triggers de objetivos |
| `pacientes` → `asignaciones` | los dos triggers de asignaciones |
| `pacientes` → `terapeutas` → `sesiones` | `p_registrar_sesion` y `trg_sesiones_solape_insert` |
| `sesiones` → `objetivos_terapeuticos` | los dos triggers de evoluciones |

---

## 2. Cómo se toma el lock: dos formas, y cuál corresponde

Todo trigger que valide un **conteo** o un **rango** usa dos locks, y los dos
hacen falta. Sacar cualquiera de los dos reabre una condición de carrera real,
confirmada con dos conexiones simultáneas.

**1. Lock sobre la fila padre.**

```sql
SELECT ... FROM <tabla_padre> WHERE id = ... FOR UPDATE
```

Serializa a quienes escriben sobre el **mismo** paciente o el **mismo**
terapeuta. No bloquea la tabla entera ni a los demás pacientes.

**2. El conteo sobre la propia tabla lleva `FOR SHARE`.**

Sin esto el lock de arriba **no alcanza**. En `REPEATABLE READ` —el nivel por
defecto de MySQL— un `SELECT` común lee del snapshot que la transacción fijó
en su **primera** lectura, así que el trigger no ve la fila que la otra
transacción acaba de confirmar, **aunque haya esperado su lock**. `FOR SHARE`
es lectura con lock, y toda lectura con lock lee la versión actual confirmada.

Se probó con sólo el lock del padre: quedaron **2 filas en conflicto**.

### 2.1. Por qué el conteo va con `FOR SHARE` y no con `FOR UPDATE`

Porque MySQL **rechaza** `FOR UPDATE` sobre la tabla del propio trigger:

```
ERROR 1442: Can't update table ... already used by statement which invoked this trigger
```

`FOR SHARE` sí está permitido y alcanza, porque el lock de la fila padre ya
garantiza que sólo una transacción esté en la sección crítica a la vez.

De ahí la regla práctica:

| Qué tabla se lee | Cómo se bloquea |
|---|---|
| **Otra** tabla (no la del trigger) | `FOR SHARE` (o `FOR UPDATE`) directo sobre la fila |
| La **propia** tabla del trigger | lock de fila padre + `FOR SHARE` en el conteo |

Los triggers de evoluciones están en el primer caso: validan contra `sesiones`
y `objetivos_terapeuticos`, que no son la tabla del trigger, así que bloquean
la fila leída directamente sin el rodeo del lock de padre.

### 2.2. Por qué `FOR SHARE` y no `FOR UPDATE` en los triggers de evoluciones

Aun pudiendo usar `FOR UPDATE`, se usa `FOR SHARE`, y el motivo está escrito
en el propio trigger:

- **Alcanza.** `FOR SHARE` conflictúa con el lock exclusivo de quien esté
  modificando esa fila —que es exactamente de lo que hay que protegerse— y
  hace lectura actual, no del snapshot.
- **Cuesta menos.** Deja que dos evoluciones sobre el mismo objetivo entren en
  paralelo, que no se pisan entre sí.
- **No hay ascenso de S a X.** El trigger no actualiza ninguna de las dos filas
  que leyó, así que no hay que subir de lock compartido a exclusivo — y no
  aparece el deadlock que ese ascenso traería.

De qué protege, concretamente: sin lock, esas serían lecturas consistentes de
MVCC y **no verían** que otra transacción, todavía sin confirmar, ya archivó el
objetivo, lo movió de paciente o marcó la sesión como ausencia. El `INSERT`
pasaba las tres validaciones contra datos viejos.

Que los `FOR SHARE` hacen lo que dicen se confirmó con sincronización real:
con una transacción archivando el objetivo en paralelo, el trigger rechaza con
`ERROR 1644 ... No se puede cargar evolucion sobre un objetivo archivado`, y
quedan **0** evoluciones sobre el objetivo archivado.

### 2.3. `pacientes FOR SHARE` antes que `terapeutas FOR UPDATE`

`p_registrar_sesion` abre su transacción tomando **`pacientes` primero**:

```sql
START TRANSACTION;

SELECT activo, fecha_baja INTO v_activo_pac, v_fecha_baja
  FROM pacientes
 WHERE id = p_id_paciente
 FOR SHARE;            -- pacientes, ANTES que terapeutas

-- ... y recién después el FOR UPDATE sobre terapeutas
```

**Por qué va antes:** por el orden canónico (`pacientes → terapeutas → …`).
Invertirlo aquí abre un ciclo con cualquier baja concurrente.

**Por qué `FOR SHARE` y no `FOR UPDATE`:** alcanza con impedir que una baja
**escriba** esa fila mientras dura la transacción. `FOR UPDATE` serializaría
además dos registros de sesión de **pacientes distintos**, que no tienen por
qué esperarse entre sí. El lock más chico que cierra la carrera es el que va.

El mismo criterio está en el trigger de INSERT de `sesiones`: el chequeo de
paciente dado de baja se hace **antes** del lock de `terapeutas`, y va **dentro
de ese trigger y no en uno propio** — MySQL corre los triggers del mismo evento
en orden de creación, así que un trigger nuevo correría después y tomaría
`pacientes` **después** de `terapeutas`.

### 2.4. El dato con el que se decide viene de la lectura que sostiene el lock

Un chequeo hecho **fuera** de la transacción no sirve por sí solo, aunque el
valor leído sea correcto en ese instante. Se demostró con dos conexiones
detenidas: la víctima pasaba el chequeo de `activo`, quedaba esperando el lock
de `terapeutas`, la baja entraba, y **la sesión terminaba insertada sobre un
paciente ya dado de baja**.

La corrección no es leer antes con más cuidado: es **rehacer el chequeo dentro
de la transacción, con el lock tomado**. Y el valor contra el que se compara
—en este caso `fecha_baja`— se lee **en ese mismo `SELECT`**: leerlo afuera y
compararlo adentro es el mismo TOCTOU con otra cara, porque entre las dos
operaciones la baja puede entrar y cambiar justamente ese valor.

El patrón inverso también se midió y también falla: dos procedimientos leían
el estado **antes** del `START TRANSACTION` y no lo revalidaban después del
`FOR UPDATE`. Dos bajas simultáneas sobre el mismo paciente **devolvían las
dos** "Paciente dado de baja correctamente", una con 1 objetivo archivado y la
otra con 0.

---

## 3. El deadlock que originó la convención

El único deadlock reproducible que el proyecto tiene documentado de punta a
punta es **`sesiones` ↔ `objetivos_terapeuticos`, por el trigger de
evoluciones**.

Es consecuencia directa de los locks de la sección 2: **abrieron un deadlock
que antes no existía**, reproducido a propósito. No es un defecto de esa
corrección, es su costo. Por eso toda transacción que toque `sesiones` y
`objetivos_terapeuticos` las toma en ese orden.

**Cómo se lo reproduce**, y las dos condiciones que hacen falta para que el
ciclo se forme de verdad:

- **Orden invertido con lectura CON LOCK.** El atacante toma
  `objetivos_terapeuticos` antes que `pacientes`, al revés del canónico, y usa
  `SELECT ... FOR UPDATE`, **no** `UPDATE`. Un `UPDATE` toma de paso un lock
  compartido sobre la fila padre por la FK y termina respetando el orden sin
  querer.
- **El atacante tiene que ser más pesado.** InnoDB elige como víctima a la
  transacción con menos trabajo hecho. La víctima llega con **cero** filas
  modificadas (el trigger corre `BEFORE INSERT`), así que el atacante se carga
  con ~200 filas modificadas antes de pedir el primer lock. Sin ese lastre
  InnoDB mata al atacante y la víctima nunca reintenta.

### 3.1. El caso que no se puede reordenar desde adentro del trigger

**No es simétrico entre `BEFORE INSERT` y `BEFORE UPDATE`, y eso sorprende.**

- Un `BEFORE INSERT` corre **antes de que la fila exista**, así que lee
  `pacientes` primero y el lock de `sesiones` llega después: orden canónico,
  sin ciclo.
- Un `BEFORE UPDATE` corre con el lock exclusivo de la fila **ya tomado**, así
  que el orden queda `sesiones → pacientes`, **invertido**, y no hay forma de
  reordenarlo desde adentro del trigger.

Por eso vale una regla para todo camino nuevo que escriba en `sesiones`:

> **Todo camino de escritura sobre `sesiones` pasa por un procedimiento que
> tome `pacientes FOR SHARE` ANTES que `terapeutas`.** Un llamador que lo haga
> llega al trigger con el lock ya en su propia transacción, el `SELECT` de
> adentro no espera a nadie, y evita los dos modos de falla de abajo.

Un endpoint escrito con un `UPDATE` del ORM y sin procedimiento **va a
funcionar en las pruebas de a uno** y va a empezar a frenar bajas en cuanto
haya dos personas trabajando a la vez.

### 3.2. Los dos modos de falla, y el frecuente no es el deadlock

**MODO 1 — ESPERA. Dos actores. Es el caso frecuente.**

Alguien edita una sesión mientras se da una baja del mismo paciente, sin nadie
registrando en el medio. **No hay ciclo y no hay deadlock: hay espera.** Quien
edita toma la fila de `sesiones` y pide `pacientes`; la baja nunca toca
`sesiones`, así que no necesita nada que quien edita tenga, y la cola se
resuelve sola.

Medido: la baja **espera 19,18 s** con un retenedor de 20 s, y completa. Cero
deadlocks, verificado además en `performance_schema.data_locks`.

**El riesgo de este modo no es el 1213, es el 1205.** Si la espera supera
`innodb_lock_wait_timeout`, la baja recibe lock wait timeout. El decorador
también lo reintenta, pero si quien retiene sigue ahí los tres intentos se
agotan y **la baja falla**. Una transacción larga sobre `sesiones` es, por sí
sola, suficiente para voltear una baja.

**MODO 2 — DEADLOCK. Tres actores en el ciclo, y un cuarto para montarlo.**

```
A  UPDATE directo        tiene X(sesión)     y quiere S(pacientes)
B  la baja                                     quiere X(pacientes)
C  p_registrar_sesion    tiene S(pacientes)  y quiere S(sesión), por el solape
```

A queda detrás de la X **encolada** de B —InnoDB no deja que una S nueva se
adelante a una X que ya espera—, B detrás de la S de C, y C detrás de la X de
A. Medido: `delta lock_deadlocks = 1`, `ERROR 1213`, y la víctima que elige
InnoDB es **la baja**.

Hace falta un **cuarto** actor para armarlo, y por eso no aparece solo: C
tiene que quedarse detenido después de tomar `pacientes` y antes de leer el
solape, y el único punto entre esas dos cosas es el `terapeutas FOR UPDATE`.
Alguien reteniendo esa fila abre la ventana.

Y sólo lo abre un `UPDATE` que mueva `fecha` o `id_paciente`, porque el chequeo
sólo corre en ese caso. Medido de los dos lados: `SET notas` → sin deadlock;
`SET fecha` → 1213 con la baja como víctima.

> **El error de método que quedó a la vista, y conviene no repetir:** se
> probaron las combinaciones de **dos** actores, no se encontró ciclo, y se
> generalizó a "no hay ciclo". El tercero lo cierra. **Con locks, no haberlo
> encontrado con N actores no dice nada sobre N+1.**

---

## 4. Reintento ante deadlock

Todo endpoint que escriba va decorado con `@reintentar_en_deadlock`
(`backend/app/utils/db.py`).

| Parámetro | Valor | Por qué |
|---|---|---|
| Intentos | 3 | después del último el error se propaga: si persiste, no es transitorio |
| Backoff | 50 ms → 100 ms, exponencial | un deadlock se resuelve en cuanto la otra transacción termina; esperar más sólo alarga la respuesta |
| Errores que reintenta | **1213** (deadlock) y **1205** (lock wait timeout) | los dos son transitorios, y se tratan en la misma rama |

Tras cada fallo reintentable hace `rollback()` de la sesión: la transacción ya
quedó abortada del lado de MySQL y hay que descartarla antes de volver a
intentar.

### 4.1. La transacción entera va adentro de la función decorada

**Requisito, no recomendación.** La función decorada tiene que contener la
transacción **completa, commit incluido**:

```python
@reintentar_en_deadlock()
def registrar_algo(...):
    ...
    db.session.commit()
```

Si el commit queda afuera, **el reintento repite sólo una parte de la
operación, y el resultado es peor que no reintentar.**

### 4.2. El decorador no puede reintentar lo que no ve

**Este es el hallazgo que más costó, y es la parte que se olvida.**

Los procedimientos de escritura tenían un único
`DECLARE EXIT HANDLER FOR SQLEXCEPTION`. El deadlock —SQLSTATE `'40001'`,
errno 1213— entraba por ahí como cualquier otro error: `ROLLBACK`,
`p_mensaje = '... por un error interno'`, y **el `CALL` terminaba con éxito**.

Medido, provocando el deadlock a propósito:

```
contador de deadlocks ANTES : 4
victima exit=0                      <- el CALL no fallo
victima STDOUT: NULL | No se pudo registrar la evolucion por un error interno
contador de deadlocks DESPUES: 5    <- el deadlock SI ocurrio
```

**Consecuencia:** por ese camino la aplicación nunca recibía un error 1213, así
que el decorador **no podía dispararse**. El usuario veía "error interno" ante
una condición transitoria que se resolvía sola reintentando — que es
exactamente lo que el decorador existe para evitar. Y el camino afectado era
el escenario del §3: el único deadlock reproducible documentado. **El decorador
estaba puesto justo donde no llegaba.**

**La corrección**, en los tres procedimientos de escritura: un handler
específico declarado **antes** del genérico, que revierte y **reemite**.

```sql
DECLARE EXIT HANDLER FOR SQLSTATE '40001'
BEGIN
  ROLLBACK;
  RESIGNAL;
END;

DECLARE EXIT HANDLER FOR 1205
BEGIN
  ROLLBACK;
  RESIGNAL;
END;
```

Tres detalles que no se deducen leyendo:

- **`RESIGNAL` y no `SIGNAL`.** Reemite la condición **original** con su
  SQLSTATE y su errno intactos, que es lo único que el decorador puede
  reconocer.
- **El 1205 va por número, no por SQLSTATE.** El suyo es `'HY000'`, el
  genérico de casi todos los errores del servidor, así que atajarlo por
  SQLSTATE se llevaría puesto todo lo demás. MySQL admite handlers por errno.
- **La precedencia se midió, no se dedujo.** Con el handler de 1205 ya
  declarado, el `'40001'` sigue llegando como 1213 en los tres procedimientos,
  con el contador de deadlocks subiendo en cada uno.

Verificado en los tres caminos, provocando deadlocks reales — y con el criterio
de [`verificacion.md`](verificacion.md) §1: no alcanza con que la operación
termine bien.

```
                        deadlock nuevo   errno al cliente   reintento   HTTP
p_registrar_evolucion         +1              1213             1        201
p_registrar_sesion            +1              1213             1        201
p_alta_paciente               +1              1213             1        201
```

**Los procedimientos de lectura pura no llevan estos handlers y no los
necesitan:** cero sentencias de escritura, cero transacciones, ninguna lectura
con lock. No pueden ser víctimas de un deadlock.

### 4.3. Un deadlock no se traduce: se propaga

El criterio general del proyecto es que ningún texto crudo de MySQL llega al
cliente y todo error se traduce a un mensaje propio. **El deadlock es una
excepción deliberada.** No es un error para mostrarle a nadie: es una condición
transitoria que se resuelve reintentando, y traducirla a texto convierte algo
recuperable en un fracaso.

Cuando el 1205 sí agota los tres reintentos, la API responde **400** con
`codigo: error_base_de_datos` y su traducción propia —*"La operacion tardo
demasiado en obtener acceso a los datos"*—, distinta de la del 1213. Esa
distinción es lo que permite saber cuál de los dos sobrevivió.

---

## 5. Consecuencias prácticas

- **Los locks introducen espera real.** Se midió una transacción bloqueada 7
  segundos. **Mantener las transacciones cortas** no es higiene: es lo que
  separa el modo 1 (espera que se resuelve) del modo 1 que voltea una baja por
  1205.
- **Una regla que ya tiene la fila padre bloqueada sale gratis.** Cuando hizo
  falta agregar el chequeo de "paciente dado de baja" a los triggers de
  objetivos y de asignaciones, no hizo falta **ningún lock nuevo ni cambiar el
  orden**: las cuatro ramas ya tenían la fila de `pacientes` bloqueada cuando
  la necesitaban. Conviene mirar si el lock ya está antes de pedir otro.
- **Agregar validaciones a un trigger no siempre agrega locks.** La regla del
  objetivo posterior a la sesión no sumó ninguno: las tres columnas nuevas
  salen de los **mismos dos `SELECT`** que ya estaban, con su mismo `FOR SHARE`
  y en el mismo orden.
- **Los pares INSERT/UPDATE se tocan juntos.** Invertir el orden en uno solo de
  los dos triggers de evoluciones crea un deadlock.

---

## 6. Nota sobre la fuente del orden canónico

El orden de la §1 es la versión vigente, con `asignaciones` incluida.

La copia que está dentro de `backend/database/schema.sql` (NOTA DE
CONCURRENCIA) es **anterior a que esa tabla existiera** y nombra cinco tablas
en vez de seis; el propio archivo declara que el canónico vive en el documento
de convenciones del proyecto y no en el schema. La diferencia no es un
desacuerdo sobre el orden —la posición de `asignaciones` está confirmada y los
triggers la respetan— sino una copia que quedó corta.

---

## Documentos relacionados

- [`reglas-de-negocio.md`](reglas-de-negocio.md) — qué valida cada trigger.
- [`verificacion.md`](verificacion.md) — cómo se prueba que un test de
  concurrencia mide algo.
- [`base-de-datos.md`](base-de-datos.md) — operaciones destructivas.

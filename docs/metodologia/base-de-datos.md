# Operaciones sobre bases de datos

Cómo se crea, se respalda y se destruye una base en este proyecto, y por qué
hay tres controles en vez de uno.

---

## 0. El incidente que originó todo esto

El 2026-08-17, durante una tarea de limpieza de bases colgadas, se ejecutó un
`DROP DATABASE` sobre una lista de siete nombres. El primero era
`asisto_demo_prueba`, que **no era scratch**: era el único lugar donde vivían
los datos que había cargado a mano una terapeuta ocupacional externa. Los otros
seis sí eran descartables. La base de desarrollo principal nunca se tocó.

Lo recuperable se recuperó del binlog. Lo que no vuelve es que ya no existe la
base.

**Dónde falló, con precisión, porque el diagnóstico correcto importa más que la
culpa:**

- Antes de borrar se compararon las dos bases y se registró *"schema idéntico
  entre la base real y la de prueba (8 rutinas, 8 triggers, mismos md5)"*. Eso
  es una comparación de **estructura** usada para concluir sobre **contenido**:
  por construcción mira lo único que las dos bases tenían igual.
- **Sí se contaron las filas, y no alcanzó.** 117 segundos antes del `DROP` la
  misma sesión dejó registrado `asisto 16/631/460/47` contra
  `asisto_demo_prueba 17/641/469/53`. **La diferencia estuvo en pantalla y la
  base se borró igual.** El dato ya estaba y no operó.
- El guardarraíl que existía era una excepción por nombre
  (`if ($TestDbName -ieq "asisto") { throw }`). `asisto_demo_prueba` no estaba
  en la excepción, **y no había manera de que estuviera**.

**La conclusión, y es la que ordena todo lo de abajo:** mientras "base de
prueba" sea un **juicio de quien mira** y no una **propiedad registrada**, no
hay chequeo que sirva. Hoy no hay ninguna diferencia estructural entre un
scratch y la única copia de datos de una persona.

---

## 1. La regla que manda sobre las otras dos

> **Ninguna sesión de trabajo ejecuta una operación destructiva sobre una base
> que no creó en esa misma sesión.**

Destructivo es `DROP DATABASE`, `DROP TABLE`, `TRUNCATE`, `DELETE` sin `WHERE`,
y **recargar un seed sobre una base que ya tenía datos**.

Si hace falta borrar algo que no se creó en la sesión: **listar los candidatos,
reportar y frenar.** La decisión es de quien pidió la tarea.

**Un permiso general no alcanza.** *"Borrá las bases de prueba que quedaron
colgadas"* no autoriza nada, porque *"de prueba"* es una clasificación que hace
quien borra — y esa clasificación ya falló una vez, con el nombre a la vista.

Vale igual aunque la tarea parezca autorizarlo, aunque la base se llame como
una de prueba y aunque tenga el mismo esquema que una descartable. Si el pedido
terminaba en *"reportá y esperá"*, eso incluye esto: en aquel caso el pedido
terminaba exactamente así, **y el borrado ocurrió sin reportar y sin esperar.
El control humano existía y se salteó.**

**Las dos contramedidas técnicas de abajo no sustituyen a esta regla.** Sólo
atan a los scripts del repositorio, y aquel borrado fue un `mysql -e` escrito a
mano que no habría pasado por ninguna.

---

## 2. Marca al crear

Una base descartable **se declara descartable dentro de sí misma**, con la
tabla `_base_descartable`. Nada más puede borrarla.

La implementación está en `tests/db/lib/BaseDescartable.ps1`, que es el archivo
que hay que leer si se toca algo de esto.

```sql
CREATE TABLE IF NOT EXISTS `_base_descartable` (
  base       VARCHAR(64)  NOT NULL,
  creada_en  DATETIME     NOT NULL,
  creada_por VARCHAR(255) NOT NULL,
  PRIMARY KEY (base)
);
```

**La marca se estampa al FINAL de la construcción**, después de cargar schema y
seed. Antes no tendría sentido: el schema arranca con `DROP DATABASE` y se
llevaría puesta cualquier marca previa.

### 2.1. Por qué la marca va adentro y no en una lista

Una lista externa —un `.txt`, un array en un script, un prefijo de nombre— es
**exactamente lo que falló**: quien borra tiene que acertar a clasificar, y se
puede equivocar.

**La marca invierte quién decide.** El permiso lo otorga **quien creó la base**,
y viaja pegado a ella. Una base que nadie marcó no se borra, sin importar cómo
se llame ni a qué se parezca.

### 2.2. `Assert-BaseBorrable` es el único permiso de borrado que existe

Lo usan los dos caminos que destruyen: el de construcción de base de pruebas
(que también destruye, porque el schema arranca con `DROP DATABASE`) y el de
desmontaje. La regla completa:

| Situación | Qué pasa |
|---|---|
| La base **no existe** | se crea — nada que destruir, y todavía no puede tener marca |
| Existe **con** marca | la creó este script: se respalda y se rehace |
| Existe **sin** marca | **no es nuestra. No se toca.** |

**No hay excepción por nombre, y su ausencia es deliberada.** Los dos
guardarraíles viejos que rechazaban un literal se **sacaron**. La base de
desarrollo principal hoy se salva por el mismo motivo que cualquier otra base
con datos que no sean de prueba: **porque nadie la marcó**.

Verificado, y el mensaje es parte de la verificación:

```
asisto tiene marca : False
Assert-BaseBorrable -Database 'asisto'
  -> "NO SE BORRA 'asisto': no tiene la tabla '_base_descartable' ...
      Tiene aproximadamente 1463 filas."
```

El mensaje **ni menciona el nombre de la base como motivo**: informa el
volumen de datos. Y distingue el caso de una base de prueba anterior a la marca
—para la que trae la migración de una sola vez— del caso de una base que no hay
que borrar.

**Cómo se verificó sin arriesgar nada:** no se apuntó el script de desmontaje
contra la base real. Si el guardarraíl tuviera un error, esa verificación la
habría destruido. `Assert-BaseBorrable` es exactamente la misma llamada que el
desmontaje hace una línea antes del `DROP`, y es de sólo lectura. **Se verifica
el guardarraíl, no la ruleta.**

Y se simuló el caso que de verdad pasó: una base armada a mano desde un dump
—igual que aquella, que salió del schema a mano y no del script— **no tiene
marca**, y el desmontaje se negó.

### 2.3. No hay puerta de adopción, y es a propósito

Cuando la marca se introdujo, las bases que ya existían no la tenían, así que
los scripts se iban a negar a borrarlas. Se resolvió **recreándolas**, no
marcándolas a mano: su contenido sale entero del schema más el seed, así que no
se pierde nada — y **marcar una base existente pediría una puerta de "adopción"
que es justo el bypass que esta contramedida vino a sacar**.

Por el mismo motivo el respaldo **no tiene opción para saltearse**. Un
`-SinRespaldo` sería la puerta por la que se vuelve a salir.

### 2.4. El catálogo se consulta para preguntar, nunca para elegir

`information_schema.SCHEMATA` se consulta para preguntar por **una base
concreta que el llamador ya nombró**. No se enumera para elegir a quién borrar
— esa es justamente la forma que produjo el incidente, y en todo el repositorio
no existe.

---

## 3. Respaldo antes de destruir

Cualquier operación destructiva sobre una base hace primero un dump completo:
**datos, triggers y rutinas.**

| Opción | Por qué |
|---|---|
| `--routines` | los procedimientos. Sin esto el dump restaura una base que "anda" hasta que alguien llama al primer procedimiento |
| `--triggers` | **los triggers, que es donde viven las reglas de negocio.** Viene por defecto; se escribe igual, porque un dump sin triggers **parece completo** y es el peor de los respaldos |
| `--single-transaction` | todo es InnoDB: snapshot coherente y sin lockear la base |
| `--result-file` | lo escribe el propio `mysqldump`, no el shell — redirigir la salida de un ejecutable nativo puede reescribir los finales de línea y romper el `.sql` |
| *(sin `--databases`)* | así el dump **no lleva `CREATE DATABASE` ni `USE`** y se puede restaurar bajo **cualquier** nombre. Es lo que permite verificarlo sin tocar el original |

**Destino:** `tests/db/_respaldos/`, verificado ignorado por git con un
`git check-ignore` explícito. Un dump de la base de demostración tiene nombres y
diagnósticos: no va al repositorio ni por accidente.

**Retención: los últimos 5 por base.** No es un histórico, es una red para
deshacer el último error.

**Costo, medido:** una corrida completa de la suite de base toma 28 respaldos
(14 módulos × construcción + desmontaje), unos 3,5 s cada uno contando el
arranque del proceso. El tiempo total de la suite subió de **342 s a 440 s** y
los respaldos ocupan **1,42 MB** con la retención puesta. Noventa y ocho
segundos por corrida es un precio que se paga.

---

## 4. Un respaldo se verifica por CONTENIDO, no por tamaño

> **Un dump que nadie restauró es un archivo, no un respaldo.**

El chequeo de tamaño mínimo que hace el script —se aborta el borrado si el dump
quedó por debajo de 1 KB— es una guarda contra el dump vacío, **no** una
verificación. Verificar es otra cosa.

### 4.1. Restaurar y comparar tabla por tabla

El dump se restaura en una base de scratch aparte y se compara contra el
original. La comparación es por **contenido**: `CHECKSUM TABLE` tabla por
tabla, no tamaños ni conteos.

De la última migración aplicada a la base de desarrollo:

```
18/18 tablas con CHECKSUM TABLE identico
 9/9  rutinas
 8/8  triggers
```

Recién con eso se destruyó la base de verificación, y recién entonces se tocó
el original.

### 4.2. Y que lo restaurado FUNCIONE, que es lo que el conteo no prueba

Contar filas y contar triggers no dice que los triggers hagan algo. Después de
restaurar, se **ejercitan las reglas** contra la copia:

```
INSERT de un 5to objetivo activo del paciente 1
  -> ERROR 1644: El paciente ya tiene 4 objetivos activos. Archive uno antes de crear otro
CALL p_registrar_sesion(...) pisando un horario ocupado
  -> 'El terapeuta ya tiene 5 sesion(es) que se superponen con ese horario'
```

Una regla por trigger y una por trigger más procedimiento, **vivas en la
copia**.

Es el mismo criterio de [`verificacion.md`](verificacion.md) §3.1: no medir lo
fácil para afirmar sobre lo que importa.

### 4.3. El origen de la verificación es la base que importa

La verificación se hace sobre el dump de la base **cuya pérdida importaría**,
no sobre una de scratch. `mysqldump` sólo lee, así que nunca se escribe sobre
ella; la restauración va a otro nombre.

---

## 5. Migrar una base con datos

El procedimiento que se usó la última vez, y que conviene repetir:

1. **Respaldo previo**, con verificación por contenido (§4).
2. **DDL no destructivo**, extraído del schema fuente con herramientas y
   **verificado con `diff` contra el archivo fuente antes de ejecutar** — no
   retipeado a mano. La primera vez que se escribió a mano se coló una
   condición inventada que no existía en el original; se descartó justamente al
   comparar contra la fuente antes de aplicar nada.
3. **Verificación posterior**: que la columna esté, que los conteos no se hayan
   movido, y que la distribución de valores sea la esperada.
4. **Chequeo de lectores posicionales**, si la migración cambia el orden de las
   columnas. Insertar una columna `AFTER <otra>` corre las que vienen después
   una posición a la derecha: si algún procedimiento leyera con `SELECT *` o la
   aplicación desempaquetara por posición en vez de por nombre, **se corromperían
   datos en silencio**. Se revisaron los procedimientos que arman filas para
   otros módulos y se confirmó que los dos listan columnas explícitas con alias.
5. **Decidir explícitamente qué pasa con las filas preexistentes** que la regla
   nueva violaría. Ver [`reglas-de-negocio.md`](reglas-de-negocio.md) §5.

---

## 6. Bases de prueba: una por entorno de trabajo

Los nombres de base de prueba eran fijos, así que dos corridas simultáneas de
la misma suite usaban **la misma base**. Eso **invalidó mediciones de las dos
partes** antes de que se detectara: una intermitencia se dio por flaky cuando
en parte era colisión, y un rojo se leyó como hallazgo cuando también podía
serlo.

Hoy el nombre se parametriza por entorno de trabajo mediante una variable de
entorno, y **las suites que destruyen fallan si esa variable no está
definida**, con el comando concreto en el mensaje.

**No avisan: fallan.** Avisar es lo que dejó pasar una sesión entera de
corridas contra la base equivocada. La suite de frontend no entra en esto: no
toca la base ni escribe.

### 6.1. Qué queda vivo después de correr

Una sonda de interfaz construye su base y **nunca la borra** — no hay
desmontaje en su runner. Por eso se acumulan bases `*_ui` después de correr.
No es urgente, porque están marcadas y son descartables, pero explica el
residuo.

Hay además una **contradicción abierta y sin resolver** sobre la fecha de
creación de una de esas bases: tres lecturas distintas de la misma marca. Están
las tres anotadas, ninguna descartada y ninguna promediada. El dato útil para
quien la retome es que `creada_en` se escribe con `REPLACE INTO`, así que un
valor nuevo significa como mínimo que el script de construcción corrió sobre
esa base entre una medición y la otra.

---

## 7. Los límites de cada control, dichos

Están escritos también dentro de `tests/db/lib/BaseDescartable.ps1`, a
propósito, para que no haya que ir a buscarlos.

| Control | Qué cubre | Qué NO cubre |
|---|---|---|
| **La marca** | cualquier borrado hecho por un script del repositorio | **ata sólo a los scripts de este repo.** Un `mysql -e "DROP DATABASE"` escrito a mano no pasa por acá, y la marca no lo habría detenido |
| **El respaldo** | **también al comando que nadie escribió** — es el único que no depende de que quien borra tenga razón | sólo si alguien lo corre antes. **No previene el borrado equivocado: lo vuelve reversible** |
| **La regla humana (§1)** | el caso que de verdad pasó | nada la aplica automáticamente |

**Ninguna de las dos técnicas reemplaza a la regla humana**, y ninguna de las
tres se dimensiona como si tapara lo que tapan las otras.

---

## Documentos relacionados

- [`verificacion.md`](verificacion.md) — control positivo, y "vacío o idéntico
  no es un resultado".
- [`reglas-de-negocio.md`](reglas-de-negocio.md) — qué se pierde cuando un dump
  se restaura sin triggers.
- [`concurrencia.md`](concurrencia.md) — orden de locks.

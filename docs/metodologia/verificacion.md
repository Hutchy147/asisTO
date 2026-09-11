# Método de verificación

Cómo se decide, en este proyecto, que algo está verificado.

Todas las reglas de abajo salen de un caso concreto que ocurrió acá. Van con
ese caso pegado a propósito: una regla de método sin el episodio que la
originó se lee como una opinión, y la primera vez que estorba alguien la
saltea. Con el caso a la vista se entiende qué se pierde al saltearla.

---

## 0. El principio

**Nada se da por verificado porque el código lo diga.** Leer una función no
dice qué hace en ejecución, leer un componente no dice qué se dibuja, y
contar objetos no dice nada del comportamiento de esos objetos.

De ahí salen las cuatro reglas de este documento, que son cuatro formas de
la misma pregunta: *¿el instrumento con el que estoy midiendo puede darme un
resultado distinto del que obtuve?* Si no puede, el resultado no es una
medición.

---

## 1. Falsar en las dos direcciones

**Un test verde no prueba nada hasta que se lo vio en rojo.**

La disciplina es: desactivar lo que el test dice proteger y confirmar que se
pone en rojo. No alcanza con que el caso positivo pase; hay que demostrar que
el caso negativo falla, y que falla **por el motivo que se afirma**.

Este proyecto lleva **cuatro** tests que pasaban sin probar nada. El más caro
fue el de deadlock: pasó en verde **dos veces** antes de medir algo real.

- La primera versión atacaba con `UPDATE` en vez de `SELECT ... FOR UPDATE`.
  Un `UPDATE` toma de paso un lock compartido sobre la fila padre por la FK,
  así que el atacante terminaba respetando el orden canónico sin querer: no
  había ciclo posible y el test daba PASS.
- Corregido eso, InnoDB elegía como víctima al **atacante**, por ser la
  transacción con menos trabajo hecho. La operación bajo prueba terminaba
  bien sin haber reintentado nunca. Se arregló cargando al atacante con ~200
  filas modificadas antes de que pida el primer lock.

El test definitivo no afirma "la operación terminó bien" —que es justamente
lo que tienta escribir y lo que pasa en verde sin probar nada—. Afirma tres
cosas **juntas**, y si falta cualquiera el resto no significa nada:

| # | Qué verifica | Cómo |
|---|---|---|
| 1 | Hubo un deadlock **nuevo** | el contador `lock_deadlocks` de InnoDB subió durante la ventana del ataque |
| 2 | Se **reintentó** | el logger del propio decorador emitió `Deadlock en <función> (intento 1 de 3)` |
| 3 | La operación se completó | y dejó **exactamente una** fila, no dos |

### 1.1. La falsación se aplica con edición exacta

Una falsación se hizo con un reemplazo de texto que **no matcheó** por
finales de línea. El decorador nunca quedó neutralizado, los 14 tests
pasaron, y ese verde se leyó por un momento como "los tests son robustos".
Era lo contrario: la señal de que la falsación no se había aplicado.

**Verificar que el neutralizado quedó puesto antes de correr.** El mismo
defecto apareció una segunda vez, con un `str.replace` que no matcheó y
siguió de largo: durante dos corridas el atacante retenía 2 s mientras el
comentario del archivo decía 8. Se detectó porque el tiempo total de la suite
no había cambiado.

Después de falsar, el archivo se restaura y **se verifica la restauración por
hash**, no de memoria (`SHA-256` antes y después, más `git status` limpio).

### 1.2. Dos rojos con mensajes distintos son dos defectos, no uno

Al cubrir la invariante *"si el sistema aceptó guardar una evolución, esa
evolución tiene que aparecer en el gráfico que la ficha pide por defecto"*,
los dos tests nuevos salieron en rojo. Podían ser el mismo defecto visto dos
veces. **Los mensajes los separaron:**

```
..._sobre_sesion_futura_...              periodo {hoy, hoy}      series 0
                                         'Se encontraron 0 evoluciones en el periodo'
..._sobre_objetivo_creado_despues_...    periodo {hoy-30, hoy}   series 0
                                         'Se encontraron 1 evoluciones en el periodo'
```

En el primero la evolución ni siquiera cae en el período; en el segundo cae,
el procedimiento la cuenta, y aun así no entra en ninguna serie.

Se confirmó simulando **una sola** de las dos correcciones: con la ventana por
defecto ampliada, el primero se pone verde y el segundo sigue rojo. Si los dos
se hubieran puesto verdes, sería un defecto y no dos.

---

## 2. El control positivo es obligatorio

**Antes de concluir a partir de un resultado vacío, probar la herramienta
contra un caso que se sabe positivo. Si no encuentra lo que tiene que
encontrar, lo vacío era la herramienta.**

Al averiguar si existían suites de interfaz que manejaran un navegador, la
búsqueda dio cero. Antes de escribir "no existen" se probó el filtro contra un
caso que sí tenía que encontrar:

- `git ls-files tests/` → **32 archivos**. La lista salió completa, así que la
  consulta funciona.
- `git ls-files --others --exclude-standard tests/` → vacío: tampoco hay nada
  sin trackear.
- Búsqueda de nombres de librerías de navegador en todo el repo → cero. El
  mismo comando con un patrón de nombres de componentes **sí** devuelve
  archivos, o sea que el filtro encuentra cuando hay algo.

Recién con las tres se pudo afirmar que el vacío era del repositorio y no de
la herramienta.

El mismo criterio, aplicado a un guardarraíl: el chequeo de puertos de una
sonda de interfaz se validó levantando **un listener real** en un puerto libre
y confirmando que la sonda se niega y nombra el pid. El primer intento de ese
control positivo **no probó nada**: el proceso intruso nunca llegó a tomar el
puerto, y la sonda pasó porque el puerto estaba realmente libre. Sin haber
mirado si el intruso escuchaba, ese verde se habría leído como "el chequeo
anda".

---

## 3. Vacío o idéntico no es un resultado

Dos cosas que dan igual no prueban que sean iguales: pueden estar midiéndose
por una propiedad que comparten por construcción.

**El caso que más costó:** antes de un borrado se compararon dos bases y se
registró *"schema idéntico entre la base real y la de prueba (8 rutinas, 8
triggers, mismos md5)"*. Eso es una comparación de **estructura** usada para
concluir sobre **contenido**, y por construcción mira lo único que las dos
bases tenían igual. Costó los datos de una persona; el detalle está en
[`base-de-datos.md`](base-de-datos.md).

La lista completa de las veces que esto pasó, que se mantiene a la vista
justamente porque el patrón se repite:

1. El test de deadlock verde sin haber probado nada (§1).
2. `information_schema.PARAMETERS` consultada **sin filtrar por esquema**: esa
   tabla es del servidor entero, no de la base actual. Dos bases tenían el
   mismo procedimiento con 7 parámetros y la consulta trajo las dos mezcladas
   — 14 en vez de 7. Un rojo real, por un error de la consulta.
3. *"Leí el render"* sin abrir el navegador.
4. Siete bases dadas por reconstruibles sin verificarlo.
5. El md5 de las rutinas usado para concluir sobre el contenido.
6. Un extractor que devolvía vacío, y ese vacío se tomó por un hecho.

### 3.1. No medir lo fácil para afirmar sobre lo que importa

Contar objetos no dice nada del comportamiento; leer el código no dice qué se
dibuja.

Un respaldo verificado por **conteo de filas** sigue sin probar que los
triggers restaurados funcionen. Por eso la verificación de un respaldo
restaura el dump y después **ejercita las reglas** contra la copia (ver
[`base-de-datos.md`](base-de-datos.md), §4).

Un gateo de interfaz verificado **leyendo el código** dijo que una capacidad
estaba bien declarada y bien respetada. Medido en el navegador con sesiones
reales, la pantalla que la contiene la abre **otra** capacidad, más estricta:
el botón era inalcanzable aunque todo lo leído fuera correcto. La lectura del
código era cierta y la conclusión era falsa.

### 3.2. Un instrumento que no distingue dos cosas no sirve para separarlas

- Un chequeo de puertos usaba una herramienta que **no ve los listeners
  duplicados**: con dos backends vivos en el mismo puerto informaba **1**
  cuando había **2**. Se reemplazó por una que devuelve la lista completa —y
  la sonda dice cuántos encontró, con qué pid—, no un sí/no.
- Para desempatar cuál de los dos contestaba se descartó usar la cabecera
  `Server:`: los dos declaraban la misma versión de intérprete. Queda escrito
  en el propio archivo para que no se reintroduzca como atajo.
- `Test-Path` devuelve falso tanto cuando la ruta no existe como cuando no se
  la puede mirar. Un chequeo de permisos denegados imprimió *"no existe la
  carpeta"*. Se detectó porque el error estaba impreso al lado.

---

## 4. Un rojo cuyo mensaje no coincide con la hipótesis no la confirma

**Un test en rojo no es una medición: es un aviso de que ALGO anda mal.** Si
el mensaje no dice lo que la hipótesis predice, todavía no se sabe qué se
encontró — y lo más probable es que lo roto sea el instrumento, no el sistema.

**Leer el mensaje, no el veredicto.** En una sola ronda fallaron tres
instrumentos de medición propios. Los tres daban rojo. Ninguno de los tres
decía nada sobre el código:

| Instrumento | Qué estaba roto | Cómo se cazó |
|---|---|---|
| Una mutación de prueba | `"\$pac4"` dentro de comillas dobles: el shell expandió la variable a **vacío** y el reemplazo dejó un id de paciente inexistente | el mensaje de la víctima decía *"El paciente indicado no existe"*, que no era lo que la hipótesis predecía |
| Un contador de ocurrencias | un patrón con `..` donde había tres caracteres: informaba 0 con la mutación aplicada | el conteo contradecía lo que se acababa de escribir en el archivo |
| El resumen de una suite | recortado al invocarla, se comió la línea de resumen del propio runner | faltaba el chequeo `PASS + FAIL + INFO = TOTAL` que esa línea trae |

El tercero tiene una lección aparte: el total se podía reconstruir sumando las
tablas parciales, pero **un número reconstruido a mano no reemplaza al número
que el runner audita**. Se volvió a correr la suite entera.

### 4.1. Antes de reportar un rojo, descartar que sea propio

Una fecha literal `'2026-09-01'` en un test era posterior a la baja el día que
se escribió y hoy es **anterior**. El test no se rompió: **cambió de
significado solo**, de *"una sesión posterior a la baja se rechaza"* a *"una
sesión anterior a la baja se rechaza"*, que es falso y además contradice a otro
grupo de la misma suite. Se leía como un rojo del sistema y la base estaba
aceptando esa sesión **correctamente**.

De ahí sale la regla de fechas del proyecto: **sólo es bomba de tiempo la
fecha que se compara contra HOY.** Una fecha literal cotejada contra un seed
congelado es estable para siempre; si el valor esperado depende de
`CURRENT_DATE`, la fecha del test se calcula desde ese mismo `CURRENT_DATE` y
no se escribe a mano.

---

## 5. El interruptor de falsación vive adentro del test

Una falsación hecha a mano una vez es **una afirmación en un informe**: dice
que el día que se escribió el rojo era alcanzable. No dice nada de hoy.

Un test puede dejar de medir lo que dice medir en cualquier commit posterior
—pasó cuatro veces acá— y desde afuera se ve idéntico: verde.

Dos formas de dejar el control puesto, las dos en uso:

- **Un control permanente dentro de la suite.** El mismo ataque se corre
  contra la función **sin decorar** (`__wrapped__`) y se exige que ahí
  estalle. Si el escenario dejara de producir el error, ese control se cae
  solo y avisa que el test principal está dando PASS por casualidad.
- **Un interruptor de siembra negativa.** La sonda de interfaz siembra el caso
  **sin** el dato bajo prueba con un parámetro, y ahí tiene que dar rojo:

  | Siembra | Resultado | Salida |
  |---|---|---|
  | **con** observación | PASS, exit 0 | *"la observacion guardada en la base aparece en la pantalla"* |
  | **sin** observación | FAIL, exit 1 | *"el texto NO llegó al DOM"* |

  El rojo no es un artefacto de espera, y eso también se puede ver: al fallar
  vuelca lo que la pantalla **sí** muestra, y en la corrida negativa se lee la
  pantalla entera y cargada. Estaba lista, y el texto no estaba.

Con el interruptor adentro, *"¿esto todavía puede enrojecer?"* es **un
comando**, no una investigación. Es lo que separa un número que sólo sube de
un test.

### 5.1. Un test escrito en la dirección del defecto avisa cuando se arregla

Un test puede afirmar el comportamiento **roto** de hoy. Entonces va a fallar
cuando se corrija, y eso está bien: esa falla es la señal. El docstring lo
tiene que decir, porque si no el día que se pone en rojo alguien lo lee como
una regresión.

Funcionó exactamente así: un procedimiento se tragaba el deadlock y el test
fijaba ese hecho. Cuando se aplicó el handler, falló con el mensaje que
llevaba escrito adentro:

```
AssertionError: 1 != 0 : El decorador SI reintento en el camino de
evoluciones. Si esto pasa, el hallazgo esta cerrado.
```

---

## 6. Guardas: un resultado demasiado limpio es señal de banco sucio

Casi todo escenario tiene una forma de "salir bien" **sin haber probado
nada**. Si esa forma existe, hay que cerrarla con una guarda antes de la
primera afirmación sobre el resultado.

En el escenario de baja con deadlock: si el paciente ya estaba dado de baja de
una corrida anterior, la baja sale por el primer `IF`, no toma ningún lock, no
se cruza con nadie, y da 0 reintentos y 0 deadlocks — que es justo lo que uno
quiere ver. Las guardas que lo impiden:

- el paciente se crea en cada preparación y se afirma **activo** antes del
  ataque;
- se exige que la baja haya **arrastrado el objetivo** (si archivó 0, no hizo
  nada);
- se exige **exactamente 1** reintento: con 0, la víctima fue el atacante y el
  test no probó lo suyo.

Y se verificó que la guarda tenga de qué agarrarse: sobre un paciente ya
inactivo la operación **levanta** un error, así que el escenario contaminado
revienta en vez de dar verde.

El caso que originó la regla: un banco disparaba la operación víctima 1500 ms
después de lanzar al atacante, y el arranque en frío del proceso auxiliar
tarda ~2,2 s. Los dos nunca se cruzaban y todo daba verde. **Se detectó
porque el resultado era demasiado limpio:** cero espera, cero contención, cero
todo.

**La corrección es siempre la misma: esperar el lock real, no un tiempo
fijo.** En vez de dormir a ciegas, se lanza un `SELECT ... FOR UPDATE NOWAIT`
que falla con errno 3572 mientras el atacante retenga, y recién ahí se dispara
la víctima.

> Una sonda de sincronización tiene que aceptar **sólo** los errores que
> significan "el lock está tomado" (3572 o 1205). Una versión trataba
> *cualquier* error de la consulta como "listo"; justo antes de sondear se
> vaciaba el pool de conexiones, y la primera consulta contra una conexión
> recién cerrada fallaba por motivos que no tenían nada que ver con ningún
> lock.

---

## 7. La varianza de los tiempos es evidencia; la columna de PASS no

**Un banco que tarda siempre lo mismo es un banco sin carrera.** Diez corridas
en verde dicen "no lo vi"; la dispersión de los tiempos dice si hay una
carrera adentro.

Medido: con sincronización por `SLEEP` los tiempos bailaban y el test que
fallaba cambiaba de corrida en corrida. Con un pestillo real (un lock de
usuario que el atacante espera en vez de dormir) quedaron entre **31,84 y
31,99 s** — 150 ms entre la más rápida y la más lenta. Esa planicie es la
evidencia de que ya no hay nada compitiendo contra un reloj.

**Cómo usarlo:** correr el test N veces y mirar la dispersión, no sólo los
PASS. Si un test que hace siempre el mismo trabajo tarda a veces 2 s y a veces
5, hay una espera que depende de algo que no se controla — y va a fallar el
día que esa espera se estire un poco más.

**Un flake raro es peor que uno frecuente:** aparece justo cuando ya nadie
sospecha del test. Por eso, ante un flake, **la corrección no es subir el
`SLEEP`**: subir un sleep no elimina una carrera, la vuelve rara.

---

## 8. Los resúmenes también se auditan

**Un resumen que miente es peor que no tener resumen.**

En PowerShell 5.1, `($lista | Where-Object { ... }).Count` devuelve **vacío**
cuando hay **exactamente una** coincidencia — no 1, y tampoco 0. Con cero
coincidencias sí devuelve 0, que es lo que hace parecer que la línea funciona.

Una corrida tenía **un** test en rojo y el resumen imprimió:

```
PASS: 74   FAIL:    INFO: 4   TOTAL: 79
```

Peor: la lista de tests fallados no se imprimió, porque `if ($fail -gt 0)` con
`$null` es falso. **El único rastro del rojo era que 74 + 4 no llega a 79.**

La regla, para cualquier conteo de resultados: `@(...)` siempre, y donde se
imprime un resumen, comparar `pass + fail + info` contra el total. Ese chequeo
existe hoy en los runners y es el que hay que mirar.

Es la misma familia que un defecto que infló un TOTAL en 7: una función que
escribía su mensaje de progreso por el canal de salida en vez del de consola,
y ese mensaje se coló en el valor de retorno. **Apareció dos veces en este
repositorio**, en dos archivos distintos.

---

## 9. Una falla con ruido compartido no es un dato hasta reproducirla aislada

Vale en las dos direcciones: una intermitencia propia se dio por flaky cuando
en parte era colisión con otra corrida sobre la misma base, y un rojo ajeno se
leyó como hallazgo cuando también podía serlo.

La contramedida estructural fue separar las bases de prueba por entorno de
trabajo: los nombres eran fijos, así que dos corridas simultáneas de la misma
suite usaban **la misma base**. Hoy las suites que destruyen **fallan** si no
está definida la variable de entorno que las separa, con el comando concreto
en el mensaje. No avisan: avisar es lo que dejó pasar una sesión entera de
corridas contra la base equivocada.

El criterio sigue valiendo para cualquier otra fuente de ruido compartido —un
puerto, un proceso que quedó vivo, un archivo temporal—.

---

## 10. Lo que no se pudo medir se dice así

Cuando una medición no cierra, se anota sin promediarla ni elegir una lectura.
Hay hoy una contradicción abierta sobre la fecha de creación de una base de
prueba con **tres** lecturas distintas de la misma marca; están las tres
escritas, ninguna descartada, y el registro dice explícitamente *"una de las
dos mediciones es falsa y no sé cuál"*.

Es la misma regla que aplican los scripts de arranque: cuando un dato no se
puede averiguar, se imprime el error y no un valor plausible. Un conteo que
sale como `NO SE PUDO AVERIGUAR` molesta una vez; un `0` inventado manda a
trabajar sobre una premisa falsa.

**Y una advertencia que también salió de acá:** una herramienta puede fallar y
llevar a una conclusión falsa sobre el producto. Una pestaña del navegador
dejó de procesar actualizaciones justo después de cargar un texto largo sin
espacios, y la lectura fácil era *"ese texto cuelga la aplicación"*. Se probó
en vez de suponerlo: en una pestaña nueva, contra los mismos datos, andaba
todo. La pestaña vieja estaba colgada por el navegador, no por el código.

---

## Documentos relacionados

- [`concurrencia.md`](concurrencia.md) — orden de locks y reintento.
- [`reglas-de-negocio.md`](reglas-de-negocio.md) — dónde vive cada regla.
- [`base-de-datos.md`](base-de-datos.md) — operaciones destructivas y respaldos.

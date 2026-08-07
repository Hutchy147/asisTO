# tests/db/asignaciones/test_asignaciones_vigencia.ps1
#
# Cobertura de la tabla `asignaciones` y sus dos triggers
# (trg_asignaciones_vigente_insert / _update), que entraron en la migracion
# del 2026-08-07 sin un solo test. Ver ESTADO.md, decision 17 y "Migracion
# unica de schema".
#
# La regla: vigente = fecha_hasta IS NULL, y un terapeuta no puede tener dos
# asignaciones vigentes con el mismo paciente. Vive en los dos triggers, no
# en el backend -- no hay endpoint de asignaciones todavia -- asi que TODO
# se prueba por SQL directo, que es el unico camino que existe hoy.
#
# Los triggers son el CUARTO par INSERT/UPDATE del schema y nacieron
# duplicados. El riesgo conocido es que uno quede desactualizado respecto
# del otro, asi que el bloque 2 no se conforma con que las dos rutas
# rechacen: compara el texto exacto del mensaje y el errno, caracter por
# caracter. Si alguien toca un trigger y no el otro, ese bloque lo agarra
# aunque las dos rutas sigan rechazando.
#
# Uso:
#   .\test_asignaciones_vigencia.ps1 -Database asisto_test_audit

param(
    [string]$Database = "asisto_test_audit"
)

. "$PSScriptRoot\..\lib\TestHelpers.ps1"

$modulo = "asignaciones"
$resultados = @()

# Estado del seed (seed.sql) al empezar:
#   id 1  (ter 1, pac 1)  2026-03-02  NULL        VIGENTE
#   id 2  (ter 2, pac 1)  2026-03-02  2026-05-04  CERRADA
#   id 3  (ter 2, pac 2)  2026-03-16  NULL        VIGENTE
#   id 4  (ter 1, pac 3)  2026-04-06  NULL        VIGENTE
# El seed chico tiene SOLO terapeutas 1 y 2, y pacientes 1, 2 y 3. Usar un
# terapeuta 3 aca no prueba el trigger: muere antes en la FK.

$msgVigencia = "ya tiene una asignacion vigente con ese paciente"
$msgFechas   = "no puede ser anterior a la de inicio"

# Devuelve el mensaje de error sin el prefijo "ERROR nnnn (nnnnn) at line n:"
# y en una sola linea, para poder comparar dos mensajes entre si.
function Get-MensajeLimpio {
    param($Resultado)
    return ((($Resultado.StdErr -replace "`r?`n", " ") `
        -replace "^ERROR \d+ \(\d+\) at line \d+: ", "")).Trim()
}

# Devuelve el errno de MySQL ("1644") o "" si la sentencia no fallo.
function Get-Errno {
    param($Resultado)
    if ($Resultado.StdErr -match "ERROR (\d+)") { return $Matches[1] }
    return ""
}


# =====================================================================
# Bloque 1 — la lista que dejo Terminal 1 (lo que probo a mano)
# =====================================================================

# --- Una segunda vigente del mismo par no entra ------------------------
$resultados += Assert-Fails $modulo "vigencia_segunda_vigente_del_mismo_par_rechazada" $Database `
    "INSERT INTO asignaciones (id_terapeuta,id_paciente,fecha_desde) VALUES (1,1,'2026-06-01');" `
    $msgVigencia

# --- Pero una segunda CERRADA del mismo par si entra --------------------
# Es el caso que distingue "vigente" de "existe": el historico se puede
# apilar todo lo que haga falta, la vigencia es una sola.
$resultados += Assert-Succeeds $modulo "vigencia_segunda_cerrada_del_mismo_par_aceptada" $Database `
    "INSERT INTO asignaciones (id_terapeuta,id_paciente,fecha_desde,fecha_hasta) VALUES (1,1,'2026-01-05','2026-02-05');"

# Se busca por fecha_desde y no por id: el AUTO_INCREMENT se corre con cada
# INSERT rechazado, asi que hardcodear el id lo vuelve fragil.
$idCerradaPar11 = [int](Get-ScalarValue $Database `
    "SELECT id FROM asignaciones WHERE id_terapeuta=1 AND id_paciente=1 AND fecha_desde='2026-01-05';")

# --- Reabrir esa cerrada sobre la vigente: la razon de ser del trigger de
#     UPDATE. Sin el, la regla del INSERT se saltea con un UPDATE. --------
$resultados += Assert-Fails $modulo "vigencia_reabrir_cerrada_sobre_vigente_rechazada" $Database `
    "UPDATE asignaciones SET fecha_hasta=NULL WHERE id=$idCerradaPar11;" `
    $msgVigencia

# --- Mover una vigente sobre otra, por las dos columnas del par ---------
# Por id_paciente: la vigente (1,3) se mueve a (1,1), que ya tiene vigente.
$resultados += Assert-Fails $modulo "vigencia_mover_vigente_sobre_otra_por_paciente_rechazada" $Database `
    "UPDATE asignaciones SET id_paciente=1 WHERE id=4;" `
    $msgVigencia

# Por id_terapeuta hace falta preparar el choque: el paciente 2 solo tiene
# la vigente del terapeuta 2. Este INSERT ademas es el test del limite NO
# decidido (un paciente con dos terapeutas) -- ver bloque 3.
$resultados += Assert-Succeeds $modulo "vigencia_paciente_con_dos_terapeutas_aceptado" $Database `
    "INSERT INTO asignaciones (id_terapeuta,id_paciente,fecha_desde) VALUES (1,2,'2026-06-01');"

$resultados += Assert-Fails $modulo "vigencia_mover_vigente_sobre_otra_por_terapeuta_rechazada" $Database `
    "UPDATE asignaciones SET id_terapeuta=1 WHERE id=3;" `
    $msgVigencia

# --- Fechas invertidas, en las dos rutas --------------------------------
$resultados += Assert-Fails $modulo "fechas_invertidas_en_insert_rechazado" $Database `
    "INSERT INTO asignaciones (id_terapeuta,id_paciente,fecha_desde,fecha_hasta) VALUES (2,3,'2026-05-01','2026-04-01');" `
    $msgFechas

$resultados += Assert-Fails $modulo "fechas_invertidas_en_update_rechazado" $Database `
    "UPDATE asignaciones SET fecha_hasta='2026-01-01' WHERE id=1;" `
    $msgFechas

# --- La fila vigente no choca consigo misma -----------------------------
# Es lo que sostiene el "id <> OLD.id" del trigger de UPDATE. Sin eso,
# guardar una asignacion vigente sin cambiarle nada fallaria.
$resultados += Assert-Succeeds $modulo "vigencia_fila_vigente_no_choca_consigo_misma" $Database `
    "UPDATE asignaciones SET fecha_desde='2026-03-03' WHERE id=1;"


# =====================================================================
# Bloque 2 — INSERT y UPDATE rechazan lo MISMO, con el MISMO mensaje
#
# Verificado aca, no asumido: es la duplicacion que ya marque como riesgo
# en la Entrega 1 para los otros tres pares, y este par nacio duplicado.
# La comparacion es -ceq (sensible a mayusculas) sobre el texto completo:
# una diferencia de una letra o de una tilde lo rompe a proposito.
# =====================================================================

$rVigenciaInsert = Invoke-Sql -Database $Database -Sql `
    "INSERT INTO asignaciones (id_terapeuta,id_paciente,fecha_desde) VALUES (1,1,'2026-06-02');"
$rVigenciaUpdate = Invoke-Sql -Database $Database -Sql `
    "UPDATE asignaciones SET fecha_hasta=NULL WHERE id=$idCerradaPar11;"

$mVigenciaInsert = Get-MensajeLimpio $rVigenciaInsert
$mVigenciaUpdate = Get-MensajeLimpio $rVigenciaUpdate

$resultados += Assert-True $modulo "par_mensaje_de_vigencia_identico_en_insert_y_update" `
    ($mVigenciaInsert -ne "" -and ($mVigenciaInsert -ceq $mVigenciaUpdate)) `
    "Las dos rutas dicen exactamente: '$mVigenciaInsert'" `
    "Los mensajes difieren. INSERT: '$mVigenciaInsert' | UPDATE: '$mVigenciaUpdate'"

$rFechasInsert = Invoke-Sql -Database $Database -Sql `
    "INSERT INTO asignaciones (id_terapeuta,id_paciente,fecha_desde,fecha_hasta) VALUES (2,3,'2026-05-01','2026-04-01');"
$rFechasUpdate = Invoke-Sql -Database $Database -Sql `
    "UPDATE asignaciones SET fecha_hasta='2026-01-01' WHERE id=1;"

$mFechasInsert = Get-MensajeLimpio $rFechasInsert
$mFechasUpdate = Get-MensajeLimpio $rFechasUpdate

$resultados += Assert-True $modulo "par_mensaje_de_fechas_identico_en_insert_y_update" `
    ($mFechasInsert -ne "" -and ($mFechasInsert -ceq $mFechasUpdate)) `
    "Las dos rutas dicen exactamente: '$mFechasInsert'" `
    "Los mensajes difieren. INSERT: '$mFechasInsert' | UPDATE: '$mFechasUpdate'"

# El errno importa aparte del texto: es lo que ve el traductor de errores
# del backend el dia que exista un endpoint de asignaciones. Los cuatro
# rechazos tienen que llegar como 1644 (SIGNAL SQLSTATE '45000'), no como
# un error nativo de MySQL.
$errnos = @(
    (Get-Errno $rVigenciaInsert), (Get-Errno $rVigenciaUpdate),
    (Get-Errno $rFechasInsert),   (Get-Errno $rFechasUpdate)
)
$resultados += Assert-True $modulo "par_los_cuatro_rechazos_llegan_con_errno_1644" `
    (($errnos | Where-Object { $_ -eq "1644" }).Count -eq 4) `
    "Los cuatro rechazos llegan como 1644 (SIGNAL 45000)" `
    "Algun rechazo no es 1644: $($errnos -join ', ')"


# =====================================================================
# Bloque 3 — lo que no estaba en la lista
#
# Terminal 1 pidio explicitamente "buscá el tercero que no vi". Los tres
# candidatos que se me ocurrieron son los multi-fila: una sola sentencia
# que crea dos vigentes del mismo par, donde el trigger corre por fila y
# podria no ver a la fila hermana de la misma sentencia. Los tres
# aguantan; se dejan como regresion porque son la clase de caso que una
# optimizacion futura del trigger rompe sin que nadie lo note.
# =====================================================================

# --- Dos vigentes del mismo par en UN SOLO INSERT multi-fila ------------
$filasAntes = [int](Get-ScalarValue $Database "SELECT COUNT(*) FROM asignaciones;")

$resultados += Assert-Fails $modulo "multifila_insert_de_dos_vigentes_del_par_rechazado" $Database `
    "INSERT INTO asignaciones (id_terapeuta,id_paciente,fecha_desde) VALUES (2,3,'2026-06-01'),(2,3,'2026-06-02');" `
    $msgVigencia

$filasDespues = [int](Get-ScalarValue $Database "SELECT COUNT(*) FROM asignaciones;")
$resultados += Assert-True $modulo "multifila_insert_rechazado_no_deja_la_primera_fila" `
    ($filasDespues -eq $filasAntes) `
    "La sentencia se deshizo entera: $filasAntes filas antes y despues" `
    "Quedaron filas de una sentencia rechazada: antes $filasAntes, despues $filasDespues"

# --- Reabrir DOS cerradas del mismo par en UN SOLO UPDATE multi-fila -----
# El caso simetrico del anterior, y el que mas me interesaba: el trigger de
# UPDATE excluye la propia fila con "id <> OLD.id", asi que la pregunta era
# si dos filas de la misma sentencia se ven entre si. Se ven.
$resultados += Assert-Succeeds $modulo "multifila_preparar_dos_cerradas_del_mismo_par" $Database `
    "INSERT INTO asignaciones (id_terapeuta,id_paciente,fecha_desde,fecha_hasta) VALUES (2,3,'2026-01-01','2026-01-31'),(2,3,'2026-02-01','2026-02-28');"

$resultados += Assert-Fails $modulo "multifila_update_que_reabre_dos_cerradas_rechazado" $Database `
    "UPDATE asignaciones SET fecha_hasta=NULL WHERE id_terapeuta=2 AND id_paciente=3 AND fecha_hasta IS NOT NULL;" `
    $msgVigencia

$vigentesPar23 = [int](Get-ScalarValue $Database `
    "SELECT COUNT(*) FROM asignaciones WHERE id_terapeuta=2 AND id_paciente=3 AND fecha_hasta IS NULL;")
$resultados += Assert-True $modulo "multifila_update_rechazado_no_deja_ninguna_vigente" `
    ($vigentesPar23 -eq 0) `
    "El par (2,3) sigue sin vigentes tras el rechazo" `
    "El UPDATE rechazado dejo $vigentesPar23 vigentes del par (2,3): la regla se violo"

# --- Borde de la comparacion de fechas ----------------------------------
# El trigger usa "<" y no "<=": una asignacion que empieza y termina el
# mismo dia es valida. Es el mismo criterio que el solape de sesiones
# (tocarse no es pisarse), asi que conviene que quede fijado.
$resultados += Assert-Succeeds $modulo "fechas_hasta_igual_a_desde_aceptada" $Database `
    "INSERT INTO asignaciones (id_terapeuta,id_paciente,fecha_desde,fecha_hasta) VALUES (2,3,'2026-04-01','2026-04-01');"

# --- La validacion de fechas NO depende de la vigencia ------------------
# Una fila que sigue cerrada tambien se valida: el chequeo esta antes del
# IF de vigencia en los dos triggers.
$resultados += Assert-Fails $modulo "fechas_invertidas_en_update_de_fila_que_sigue_cerrada" $Database `
    "UPDATE asignaciones SET fecha_desde='2026-12-01' WHERE id=$idCerradaPar11;" `
    $msgFechas

# --- Lo que NO tiene que bloquear ---------------------------------------
# Tan importante como los rechazos: una regla que ademas bloquea lo
# legitimo es un bug con otra forma.

# Reabrir una cerrada cuando el par no tiene ninguna vigente es valido.
# (id 2 es el par (2,1), cerrado en el seed, y (2,1) no tiene vigente.)
$resultados += Assert-Succeeds $modulo "vigencia_reabrir_cerrada_sin_vigente_del_par_aceptada" $Database `
    "UPDATE asignaciones SET fecha_hasta=NULL WHERE id=2;"

# Dos asignaciones CERRADAS que se pisan en el tiempo se aceptan. No es un
# descuido: es el limite conocido de esta version, declarado en el
# comentario del schema y en ESTADO.md. El test lo fija para que, si algun
# dia se decide validar solapamiento, se vea que este caso cambia.
$resultados += Assert-Succeeds $modulo "limite_conocido_dos_cerradas_que_se_pisan_aceptadas" $Database `
    "INSERT INTO asignaciones (id_terapeuta,id_paciente,fecha_desde,fecha_hasta) VALUES (1,3,'2026-01-01','2026-06-30'),(1,3,'2026-03-01','2026-08-31');"

# El flujo normal completo: cerrar la vigente y abrir la siguiente del
# mismo par. Es lo que hace un cambio de terapeuta y no puede estar
# bloqueado por la regla.
$resultados += Assert-Succeeds $modulo "flujo_normal_cerrar_vigente_y_abrir_la_siguiente" $Database `
    "UPDATE asignaciones SET fecha_hasta='2026-07-01' WHERE id=4; INSERT INTO asignaciones (id_terapeuta,id_paciente,fecha_desde) VALUES (1,3,'2026-07-02');"

# --- Las FK, que hoy son lo unico que sostiene los ids ------------------
# Pedido explicito de Terminal 1: id_terapeuta apunta a terapeutas(id)
# desde la correccion del 2026-08-07 y no hay trigger que lo valide.
$resultados += Assert-Fails $modulo "fk_terapeuta_inexistente_rechazado" $Database `
    "INSERT INTO asignaciones (id_terapeuta,id_paciente,fecha_desde) VALUES (999,1,'2026-06-01');" `
    "foreign key constraint fails"

$resultados += Assert-Fails $modulo "fk_paciente_inexistente_rechazado" $Database `
    "INSERT INTO asignaciones (id_terapeuta,id_paciente,fecha_desde) VALUES (1,999,'2026-06-01');" `
    "foreign key constraint fails"

# --- INFO: el errno real de las violaciones de FK -----------------------
# ESTADO.md ("Hallazgo lateral") afirma que en esta instalacion las
# violaciones de FK llegan con errno 1216 y no 1452, y que por eso la
# entrada ERRNO_FK de errors.py nunca se dispara. En esta base no lo puedo
# reproducir: da 1452 en las cuatro tablas que probe, incluida `informes`,
# que es la que ESTADO.md cita. NO lo marco FAIL -- no es una regla de
# negocio ni algo que estos triggers decidan -- pero queda el numero
# medido, porque de el depende si ese hallazgo existe.
$rFkErrno = Invoke-Sql -Database $Database -Sql `
    "INSERT INTO informes (id_paciente,id_terapeuta,periodo) VALUES (999,1,'2026-T3');"
$errnoFk = Get-Errno $rFkErrno
$resultados += New-TestResult $modulo "info_errno_de_violacion_de_fk_observado" "INFO" `
    "informes con id_paciente inexistente devuelve errno $errnoFk (ESTADO.md afirma 1216; medido aca: $errnoFk)"

Write-ResultsTable $resultados
return $resultados

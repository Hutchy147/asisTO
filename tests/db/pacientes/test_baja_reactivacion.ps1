# tests/db/pacientes/test_baja_reactivacion.ps1
#
# Cobertura de p_baja_paciente y p_reactivar_paciente (construccion,
# 2026-08-12), y del respaldo EN LA BASE de la baja logica.
#
# Construccion validó estos procedimientos con 13 casos a mano contra una base
# descartable. Esto los deja corriendo solos, y agrega lo que una validacion a
# mano no cubre: los caminos que NO pasan por el procedimiento.
#
# LA PREGUNTA QUE ORGANIZA EL ARCHIVO. Una baja logica no es "poner un flag":
# es una afirmacion sobre TODAS las escrituras que dependen de ese flag. El
# procedimiento cierra su propio camino (archiva objetivos, cierra
# asignaciones) y `p_registrar_sesion` cierra el suyo (rechaza sesiones nuevas,
# con el chequeo agregado el mismo dia). La pregunta es si los OTROS caminos de
# escritura quedaron igual de cerrados. La leccion que el propio comentario de
# p_registrar_sesion cita —"si vive solo en un camino, no vive"— es el criterio
# con el que se escribieron los grupos 4 y 5.
#
# ESTADO (2026-08-13): el archivo esta entero en verde. Los cinco hallazgos que
# abrio —tres caminos de escritura que la base no cerraba, la carrera del
# chequeo de `activo` y la doble baja— los cerro construccion, y los tests que
# los documentaban pasaron solos a PASS sin tocarlos.
#
# Dos de ellos SI hubo que reescribirlos, y el motivo vale la pena: afirmaban
# una PRECONDICION del defecto ("la baja logra entrar en la ventana") en vez de
# la garantia. Cuando el defecto se arregla, esa precondicion deja de ser
# alcanzable y el test se pone rojo justo cuando el sistema empieza a andar
# bien. Ahora afirman la garantia: la baja no entra mientras la victima
# sostiene el lock. Ver el grupo 5.
#
# Uso:
#   .\test_baja_reactivacion.ps1 -Database asisto_test_audit2_pacientes

param(
    [string]$Database
)

. "$PSScriptRoot\..\lib\TestHelpers.ps1"

# Sin -Database explicito, el nombre sale del rol de la terminal (ASISTO_ROL).
if (-not $PSBoundParameters.ContainsKey('Database')) {
    $Database = Get-NombreBaseDePrueba -Base "asisto_test_audit" `
        -EjemploExplicito '.\test_baja_reactivacion.ps1 -Database mi_base'
}

$modulo = "baja"
$resultados = @()

# --- Utilidades del archivo ---------------------------------------------

function Nuevo-Paciente {
    param([string]$Sufijo)
    $r = Invoke-Sql -Database $Database -Sql @"
CALL p_alta_paciente('Baja','$Sufijo','2015-05-05',NULL,'HC-BAJA-$Sufijo',NULL,@id,@msg);
SELECT @id;
"@
    return Get-IdDeSalida $r "El alta del paciente $Sufijo"
}

# Las dos funciones de abajo leen una fila de N columnas separadas por tab.
# Si el lote de mysql se corto antes del SELECT --un error en el CALL, que
# sale SOLO por stderr-- esa fila no existe y los indices que faltan daban
# $null, y el .Trim() sobre $null se llevaba la suite entera. Ahora el
# mensaje de error viaja en el campo `Mensaje` y los datos que no llegaron
# dicen "(sin dato)": la asercion falla igual, pero falla CON el motivo.
function Llamar-Baja {
    param([int]$IdPaciente)
    $r = Invoke-Sql -Database $Database -Sql @"
CALL p_baja_paciente($IdPaciente, @obj, @asig, @msg);
SELECT IFNULL(@obj,'NULL'), IFNULL(@asig,'NULL'), @msg;
"@
    $ultima = Get-UltimaLineaSql $r
    $campos = @($ultima -split "`t")
    $completa = $campos.Count -ge 3
    return [pscustomobject]@{
        ExitCode     = $r.ExitCode
        Objetivos    = $(if ($completa) { $campos[0].Trim() } else { "(sin dato)" })
        Asignaciones = $(if ($completa) { $campos[1].Trim() } else { "(sin dato)" })
        Mensaje      = $(if ($completa) { $campos[2].Trim() } else { $ultima })
    }
}

function Llamar-Reactivar {
    param([int]$IdPaciente)
    $r = Invoke-Sql -Database $Database -Sql @"
CALL p_reactivar_paciente($IdPaciente, @react, @msg);
SELECT IFNULL(@react,'NULL'), @msg;
"@
    $ultima = Get-UltimaLineaSql $r
    $campos = @($ultima -split "`t")
    $completa = $campos.Count -ge 2
    return [pscustomobject]@{
        ExitCode   = $r.ExitCode
        Reactivado = $(if ($completa) { $campos[0].Trim() } else { "(sin dato)" })
        Mensaje    = $(if ($completa) { $campos[1].Trim() } else { $ultima })
    }
}

# =======================================================================
# GRUPO 1 — la baja hace sus tres escrituras y NADA MAS
# =======================================================================

$pac1 = Nuevo-Paciente "UNO"

# 3 objetivos activos + 1 ya archivado (el archivado NO tiene que contarse
# como "archivado por esta baja").
$null = Invoke-Sql -Database $Database -Sql @"
INSERT INTO objetivos_terapeuticos (id_paciente, descripcion, activo) VALUES
  ($pac1, 'Objetivo activo A', TRUE),
  ($pac1, 'Objetivo activo B', TRUE),
  ($pac1, 'Objetivo activo C', TRUE),
  ($pac1, 'Objetivo ya archivado', FALSE);
INSERT INTO asignaciones (id_terapeuta, id_paciente, fecha_desde, fecha_hasta) VALUES
  (1, $pac1, '2026-03-02', NULL),
  (2, $pac1, '2026-01-05', '2026-02-05');
INSERT INTO sesiones (id_terapeuta, id_paciente, fecha, hora_inicio, hora_fin, estado) VALUES
  (1, $pac1, '2026-06-01', '08:00:00', '09:00:00', 'completa'),
  (1, $pac1, '2026-06-08', '08:00:00', '09:00:00', 'completa');
"@

$idSesionEvol = [int](Get-ScalarValue $Database "SELECT id FROM sesiones WHERE id_paciente=$pac1 ORDER BY id LIMIT 1;")
$idObjEvol = [int](Get-ScalarValue $Database "SELECT id FROM objetivos_terapeuticos WHERE id_paciente=$pac1 AND activo=TRUE ORDER BY id LIMIT 1;")
$null = Invoke-Sql -Database $Database -Sql `
    "INSERT INTO evoluciones (id_sesion, id_objetivo, valor) VALUES ($idSesionEvol, $idObjEvol, 4);"

$sesionesAntes = [int](Get-ScalarValue $Database "SELECT COUNT(*) FROM sesiones WHERE id_paciente=$pac1;")
$evolucionesAntes = [int](Get-ScalarValue $Database @"
SELECT COUNT(*) FROM evoluciones e JOIN sesiones s ON s.id = e.id_sesion WHERE s.id_paciente=$pac1;
"@)

$baja1 = Llamar-Baja $pac1

$resultados += Assert-True $modulo "baja_devuelve_los_dos_contadores" `
    ($baja1.Objetivos -eq "3" -and $baja1.Asignaciones -eq "1") `
    "Informo 3 objetivos archivados y 1 asignacion cerrada" `
    "Contadores inesperados: objetivos=$($baja1.Objetivos) asignaciones=$($baja1.Asignaciones) (se esperaba 3 y 1). El objetivo ya archivado y la asignacion ya cerrada NO tienen que contarse."

$estado1 = Get-ScalarValue $Database @"
SELECT CONCAT(activo, '|', IFNULL(fecha_baja,'NULL'), '|', IF(fecha_baja = CURRENT_DATE,'hoy','otra'))
  FROM pacientes WHERE id = $pac1;
"@
$resultados += Assert-True $modulo "baja_marca_inactivo_con_fecha_de_hoy" `
    ($estado1 -like "0|*|hoy") `
    "activo=0 y fecha_baja=CURRENT_DATE" `
    "Estado inesperado del paciente tras la baja (activo|fecha_baja|es_hoy): $estado1"

$activosDespues = [int](Get-ScalarValue $Database `
    "SELECT COUNT(*) FROM objetivos_terapeuticos WHERE id_paciente=$pac1 AND activo=TRUE;")
$resultados += Assert-True $modulo "baja_no_deja_ningun_objetivo_activo" ($activosDespues -eq 0) `
    "No quedo ningun objetivo activo" `
    "Quedaron $activosDespues objetivos activos sobre un paciente dado de baja"

# El trigger de objetivos es el que escribe fecha_archivado: si la baja
# archivara con un UPDATE que lo esquive, esto lo agarra.
$sinFecha = [int](Get-ScalarValue $Database @"
SELECT COUNT(*) FROM objetivos_terapeuticos
 WHERE id_paciente=$pac1 AND activo=FALSE AND fecha_archivado IS NULL;
"@)
$resultados += Assert-True $modulo "baja_deja_fecha_archivado_en_los_que_archivo" ($sinFecha -eq 1) `
    "Los 3 archivados por la baja tienen fecha_archivado; el unico sin fecha es el que ya estaba archivado de antes" `
    "Objetivos archivados sin fecha_archivado: $sinFecha (se esperaba 1, el preexistente)"

$vigentes = [int](Get-ScalarValue $Database `
    "SELECT COUNT(*) FROM asignaciones WHERE id_paciente=$pac1 AND fecha_hasta IS NULL;")
$resultados += Assert-True $modulo "baja_no_deja_asignaciones_vigentes" ($vigentes -eq 0) `
    "No quedo ninguna asignacion vigente" `
    "Quedaron $vigentes asignaciones vigentes sobre un paciente dado de baja"

$cerradaVieja = Get-ScalarValue $Database `
    "SELECT fecha_hasta FROM asignaciones WHERE id_paciente=$pac1 AND id_terapeuta=2;"
$resultados += Assert-True $modulo "baja_no_repisa_una_asignacion_ya_cerrada" ($cerradaVieja -eq "2026-02-05") `
    "La asignacion que ya estaba cerrada conservo su fecha_hasta" `
    "La asignacion ya cerrada quedo con fecha_hasta=$cerradaVieja (se esperaba 2026-02-05)"

$sesionesDespues = [int](Get-ScalarValue $Database "SELECT COUNT(*) FROM sesiones WHERE id_paciente=$pac1;")
$evolucionesDespues = [int](Get-ScalarValue $Database @"
SELECT COUNT(*) FROM evoluciones e JOIN sesiones s ON s.id = e.id_sesion WHERE s.id_paciente=$pac1;
"@)
$resultados += Assert-True $modulo "baja_no_toca_sesiones_ni_evoluciones" `
    ($sesionesDespues -eq $sesionesAntes -and $evolucionesDespues -eq $evolucionesAntes) `
    "Sesiones y evoluciones intactas ($sesionesDespues y $evolucionesDespues)" `
    "La baja modifico hechos ya ocurridos: sesiones $sesionesAntes->$sesionesDespues, evoluciones $evolucionesAntes->$evolucionesDespues"

$baja1bis = Llamar-Baja $pac1
$resultados += Assert-True $modulo "baja_repetida_es_rechazada_con_contadores_nulos" `
    ($baja1bis.Mensaje -match "ya estaba dado de baja" -and $baja1bis.Objetivos -eq "NULL") `
    "Rechazada: $($baja1bis.Mensaje)" `
    "Se esperaba rechazo con contadores NULL y llego: contadores=$($baja1bis.Objetivos)/$($baja1bis.Asignaciones) mensaje='$($baja1bis.Mensaje)'"

$bajaFantasma = Llamar-Baja 999999
$resultados += Assert-True $modulo "baja_de_paciente_inexistente_es_rechazada" `
    ($bajaFantasma.Mensaje -match "no existe" -and $bajaFantasma.Objetivos -eq "NULL") `
    "Rechazada: $($bajaFantasma.Mensaje)" `
    "Se esperaba 'no existe' con contadores NULL y llego: $($bajaFantasma.Objetivos) / '$($bajaFantasma.Mensaje)'"

# =======================================================================
# GRUPO 2 — la asignacion que todavia no empezo (el GREATEST)
#
# Es el caso que el propio comentario del procedimiento dice defender: sin
# GREATEST, cerrar con CURRENT_DATE dejaria fecha_hasta < fecha_desde y
# trg_asignaciones_vigente_update rechazaria con 1644 la baja ENTERA.
# =======================================================================

$pac2 = Nuevo-Paciente "DOS"
$null = Invoke-Sql -Database $Database -Sql @"
INSERT INTO asignaciones (id_terapeuta, id_paciente, fecha_desde, fecha_hasta)
  VALUES (1, $pac2, DATE_ADD(CURRENT_DATE, INTERVAL 30 DAY), NULL);
"@

$baja2 = Llamar-Baja $pac2
$resultados += Assert-True $modulo "baja_con_asignacion_futura_no_falla" `
    ($baja2.Mensaje -match "correctamente") `
    "La baja se completo con una asignacion que todavia no empezaba" `
    "La baja fallo por una asignacion futura: '$($baja2.Mensaje)'"

$cierreFuturo = Get-ScalarValue $Database @"
SELECT IF(fecha_hasta = fecha_desde, 'en_su_inicio', CONCAT('desde=', fecha_desde, ' hasta=', IFNULL(fecha_hasta,'NULL')))
  FROM asignaciones WHERE id_paciente = $pac2;
"@
$resultados += Assert-True $modulo "baja_cierra_la_asignacion_futura_en_su_inicio" `
    ($cierreFuturo -eq "en_su_inicio") `
    "La asignacion futura quedo cerrada el dia en que iba a empezar" `
    "La asignacion futura quedo: $cierreFuturo"

# =======================================================================
# GRUPO 3 — reactivacion: deshace la baja y NADA MAS
# =======================================================================

$react1 = Llamar-Reactivar $pac1
$resultados += Assert-True $modulo "reactivar_devuelve_1_y_limpia_fecha_baja" `
    ($react1.Reactivado -eq "1" -and
     (Get-ScalarValue $Database "SELECT CONCAT(activo,'|',IFNULL(fecha_baja,'NULL')) FROM pacientes WHERE id=$pac1;") -eq "1|NULL") `
    "activo=1 y fecha_baja=NULL, con p_reactivado=1" `
    "Reactivacion inesperada: p_reactivado=$($react1.Reactivado), mensaje='$($react1.Mensaje)'"

$activosTrasReactivar = [int](Get-ScalarValue $Database `
    "SELECT COUNT(*) FROM objetivos_terapeuticos WHERE id_paciente=$pac1 AND activo=TRUE;")
$resultados += Assert-True $modulo "reactivar_no_desarchiva_objetivos" ($activosTrasReactivar -eq 0) `
    "Los objetivos siguen archivados: los elige la terapeuta al retomar" `
    "La reactivacion desarchivo $activosTrasReactivar objetivos, y es una decision explicita que NO debe hacerlo"

$vigentesTrasReactivar = [int](Get-ScalarValue $Database `
    "SELECT COUNT(*) FROM asignaciones WHERE id_paciente=$pac1 AND fecha_hasta IS NULL;")
$resultados += Assert-True $modulo "reactivar_no_reabre_asignaciones" ($vigentesTrasReactivar -eq 0) `
    "Las asignaciones siguen cerradas" `
    "La reactivacion reabrio $vigentesTrasReactivar asignaciones, y es una decision explicita que NO debe hacerlo"

$react1bis = Llamar-Reactivar $pac1
$resultados += Assert-True $modulo "reactivar_paciente_activo_es_rechazado" `
    ($react1bis.Mensaje -match "ya estaba activo" -and $react1bis.Reactivado -eq "NULL") `
    "Rechazada: $($react1bis.Mensaje)" `
    "Se esperaba rechazo con p_reactivado NULL y llego: $($react1bis.Reactivado) / '$($react1bis.Mensaje)'"

$reactFantasma = Llamar-Reactivar 999999
$resultados += Assert-True $modulo "reactivar_paciente_inexistente_es_rechazado" `
    ($reactFantasma.Mensaje -match "no existe" -and $reactFantasma.Reactivado -eq "NULL") `
    "Rechazada: $($reactFantasma.Mensaje)" `
    "Se esperaba 'no existe' con p_reactivado NULL y llego: $($reactFantasma.Reactivado) / '$($reactFantasma.Mensaje)'"

# =======================================================================
# GRUPO 4 — la baja, ¿esta respaldada en la BASE o solo en Python?
#
# Todo lo de aca se ejecuta por SQL directo / CALL, sin pasar por Flask. Es
# el mismo metodo con el que se auditaron las reglas 1 a 6, y el mismo
# criterio que construccion aplico al agregar el chequeo de activo en
# p_registrar_sesion.
# =======================================================================

$pac3 = Nuevo-Paciente "TRES"
$null = Invoke-Sql -Database $Database -Sql `
    "INSERT INTO objetivos_terapeuticos (id_paciente, descripcion, activo) VALUES ($pac3, 'Objetivo del tres', TRUE);"
$baja3 = Llamar-Baja $pac3

# 4.1 — sesiones: cerrado por construccion el 2026-08-12
#
# LA FECHA VA RELATIVA A `fecha_baja`, NO ESCRITA A MANO, y esto costo un rojo.
# Hasta el 2026-09-08 aca decia '2026-09-01'. Cuando se escribio, el 12-ago, esa
# fecha era POSTERIOR a la baja (que es CURRENT_DATE) y el caso probaba lo que
# dice su nombre. Con el correr del calendario la misma constante quedo ANTERIOR
# a la baja, y entonces la regla `p_fecha > v_fecha_baja` la acepta -- con toda
# la razon: es una sesion retroactiva legitima, que es justo lo que el grupo 7
# afirma que TIENE que entrar.
#
# O sea que el test no se rompio: CAMBIO DE SIGNIFICADO SOLO, de "una sesion
# posterior a la baja se rechaza" a "una sesion anterior a la baja se rechaza",
# que es falso y ademas contradice al grupo 7. Se leia como un rojo del sistema
# y era una bomba de tiempo del test. Misma forma que los tres hermanos del
# grupo 7: se lee `fecha_baja` de la base y se calcula desde ahi.
#
# Los 20 dias conservan la distancia original. No se usa +1 dia a proposito:
# ese es el borde exacto y es trabajo del grupo 7, que lo prueba junto con el
# dia anterior y el dia exacto porque son los tres que distinguen `>` de `>=`.
# Aca la pregunta es otra -- si el camino de escritura esta cerrado -- y conviene
# que la fecha sea inequivocamente posterior, para que un rojo de este caso
# signifique "la base dejo pasar la sesion" y no "el borde se corrio un dia".
$fechaBaja3 = Get-ScalarValue $Database "SELECT fecha_baja FROM pacientes WHERE id = $pac3;"
$sesionSobreBaja = Invoke-Sql -Database $Database -Sql @"
CALL p_registrar_sesion(1, $pac3, DATE_ADD('$fechaBaja3', INTERVAL 20 DAY), '08:00:00', '09:00:00', 'incompleta', NULL, NULL, @id, @msg);
SELECT IFNULL(@id,'NULL'), @msg;
"@
# ESTA ES LA LINEA QUE TIRO EL RUNNER ENTERO EL 2026-09-11. El CALL tenia la
# aridad vieja, mysql corto el lote antes del SELECT, el stdout quedo vacio,
# `Select-Object -Last 1` dio $null y el `.Trim()` de abajo reviento con
# InvokeMethodOnNull. Con $ErrorActionPreference = "Stop" eso no fue un rojo:
# fue el fin de la corrida, con dos modulos sin ejecutar y sin RESUMEN.
$ultimaSesion = Get-UltimaLineaSql $sesionSobreBaja
$resultados += Assert-True $modulo "sesion_nueva_sobre_paciente_de_baja_es_rechazada" `
    ($ultimaSesion -match "dado de baja") `
    "p_registrar_sesion rechaza: $ultimaSesion" `
    "p_registrar_sesion NO rechazo la sesion sobre un paciente de baja: $ultimaSesion"

$sesionesDelTres = [int](Get-ScalarValue $Database "SELECT COUNT(*) FROM sesiones WHERE id_paciente=$pac3;")
$resultados += Assert-True $modulo "sesion_rechazada_no_inserta_nada" ($sesionesDelTres -eq 0) `
    "No quedo ninguna sesion" `
    "Quedaron $sesionesDelTres sesiones de un paciente dado de baja"

# 4.2 — objetivos: mismo escenario, otro camino de escritura
$objetivoSobreBaja = Invoke-Sql -Database $Database -Sql `
    "INSERT INTO objetivos_terapeuticos (id_paciente, descripcion, activo) VALUES ($pac3, 'Objetivo creado despues de la baja', TRUE);"
$resultados += Assert-True $modulo "objetivo_nuevo_sobre_paciente_de_baja_es_rechazado" `
    ($objetivoSobreBaja.ExitCode -ne 0) `
    "La base rechaza crear un objetivo sobre un paciente dado de baja" `
    "ACEPTADO: la base deja crear un objetivo ACTIVO sobre un paciente dado de baja. Solo lo frena obtener_paciente() en Python, o sea un unico camino. Es la misma clase de hueco que se cerro el mismo dia en p_registrar_sesion."

# 4.3 — desarchivar un objetivo de un paciente que esta de baja
$idArchivadoDelTres = Get-ScalarValue $Database `
    "SELECT id FROM objetivos_terapeuticos WHERE id_paciente=$pac3 AND activo=FALSE ORDER BY id LIMIT 1;"
$desarchivar = Invoke-Sql -Database $Database -Sql `
    "UPDATE objetivos_terapeuticos SET activo = TRUE WHERE id = $idArchivadoDelTres;"
$resultados += Assert-True $modulo "desarchivar_objetivo_de_paciente_de_baja_es_rechazado" `
    ($desarchivar.ExitCode -ne 0) `
    "La base rechaza reactivar un objetivo de un paciente dado de baja" `
    "ACEPTADO: se puede desarchivar un objetivo de un paciente dado de baja, con lo cual la baja deja de ser cierta (queda inactivo con un objetivo activo)."

# 4.4 — asignaciones: la baja las cierra, pero ¿alguien impide abrir otra?
$asignacionSobreBaja = Invoke-Sql -Database $Database -Sql `
    "INSERT INTO asignaciones (id_terapeuta, id_paciente, fecha_desde, fecha_hasta) VALUES (2, $pac3, CURRENT_DATE, NULL);"
$resultados += Assert-True $modulo "asignacion_nueva_sobre_paciente_de_baja_es_rechazada" `
    ($asignacionSobreBaja.ExitCode -ne 0) `
    "La base rechaza abrir una asignacion sobre un paciente dado de baja" `
    "ACEPTADO: se puede abrir una asignacion vigente sobre un paciente dado de baja. Todavia no hay endpoint de asignaciones, asi que es el momento barato de decidirlo."

# =======================================================================
# GRUPO 5 — la baja no puede colarse entre el chequeo y el INSERT
#
# HISTORIA, porque explica que afirma este grupo. Cuando se escribio,
# p_registrar_sesion leia `MAX(activo)` con un SELECT comun, fuera de toda
# transaccion, y recien despues abria la transaccion. Entre esas dos cosas
# habia una ventana y la baja entraba: quedaba una sesion registrada sobre un
# paciente ya dado de baja. Era la misma carrera de las reglas 2, 3 y 4 de
# evoluciones.
#
# El arreglo (2026-08-12) fue revalidar bajo `pacientes FOR SHARE` DENTRO de la
# transaccion, y antes del FOR UPDATE de `terapeutas` para no invertir el
# orden de locks. Con eso la precondicion de esta carrera dejo de ser
# alcanzable: la victima sostiene el lock compartido mientras espera, y la baja
# tiene que esperarla.
#
# Por eso el grupo se reescribio el 2026-08-13 y ahora afirma la GARANTIA en
# vez de la precondicion vieja: mientras la victima sostiene el lock, la baja
# no se aplica; y al final las dos operaciones quedan serializadas. Un test que
# siguiera exigiendo "la baja entro en la ventana" se pondria rojo justamente
# cuando el sistema empieza a funcionar bien.
#
# COMO SE HACE DETERMINISTA. La ventana real dura microsegundos, asi que se
# ensancha con un tercer actor: un atacante que retiene el lock exclusivo de
# `terapeutas`, que es justo lo primero que p_registrar_sesion pide DESPUES de
# haber leido `activo`. La victima queda esperando ahi, con el chequeo ya
# pasado, y en esa espera entra la baja.
#
# LAS TRES GUARDAS SON LO QUE EVITA UN VERDE FALSO. Si el atacante no llego a
# tomar el lock, si la victima no llego a esperar, o si la baja no entro ANTES
# de que la victima avanzara, entonces no hubo carrera y el resultado final no
# significa nada: en esos casos falla la guarda correspondiente y se ve por que.
# =======================================================================

$SEGUNDOS_DE_RETENCION = 15

$jobScript = {
    param($MysqlExe, $LoginPath, $Database, $Sql)
    $tmpSql = [System.IO.Path]::GetTempFileName()
    $tmpOut = [System.IO.Path]::GetTempFileName()
    $tmpErr = [System.IO.Path]::GetTempFileName()
    Set-Content -Path $tmpSql -Value $Sql -Encoding utf8
    Start-Process -FilePath $MysqlExe -ArgumentList @("--login-path=$LoginPath", $Database) `
        -RedirectStandardInput $tmpSql -RedirectStandardOutput $tmpOut -RedirectStandardError $tmpErr `
        -NoNewWindow -Wait
    $out = Get-Content $tmpOut -Raw -ErrorAction SilentlyContinue
    Remove-Item $tmpSql, $tmpOut, $tmpErr -ErrorAction SilentlyContinue
    return $out
}

# Espera activa, nunca un sleep fijo: ver el mismo patron y su porque en
# tests/db/concurrencia/test_race_reglas_2_3_4_evoluciones.ps1.
function Esperar-Condicion {
    param([string]$Sql, [int]$SegundosMaximo = 12)
    $reloj = [Diagnostics.Stopwatch]::StartNew()
    while ($reloj.Elapsed.TotalSeconds -lt $SegundosMaximo) {
        if ([int](Get-ScalarValue -Database $Database -Sql $Sql) -gt 0) { return $true }
    }
    return $false
}

$pac4 = Nuevo-Paciente "CUATRO"

$jobAtacante = Start-Job -ScriptBlock $jobScript -ArgumentList $script:MysqlExe, $script:LoginPath, $Database, @"
START TRANSACTION;
SELECT id FROM terapeutas WHERE id = 1 FOR UPDATE;
SELECT SLEEP($SEGUNDOS_DE_RETENCION);
COMMIT;
"@

$armado = Esperar-Condicion @"
SELECT COUNT(*) FROM performance_schema.data_locks
 WHERE OBJECT_NAME = 'terapeutas' AND LOCK_TYPE = 'RECORD' AND LOCK_MODE LIKE '%X%';
"@
$resultados += Assert-True $modulo "carrera_el_atacante_retiene_el_lock" $armado `
    "El atacante tomo el lock exclusivo de terapeutas" `
    "El atacante nunca tomo el lock: no hubo carrera y nada de lo que sigue significa algo"

$jobVictima = Start-Job -ScriptBlock $jobScript -ArgumentList $script:MysqlExe, $script:LoginPath, $Database, @"
CALL p_registrar_sesion(1, $pac4, '2026-09-15', '10:00:00', '11:00:00', 'incompleta', NULL, NULL, @id, @msg);
SELECT IFNULL(@id,'NULL'), @msg;
"@

# La victima ya paso el chequeo de `activo` y esta esperando el lock.
$esperando = Esperar-Condicion @"
SELECT COUNT(*) FROM information_schema.innodb_trx WHERE trx_state = 'LOCK WAIT';
"@
$resultados += Assert-True $modulo "carrera_la_victima_quedo_esperando_el_lock" $esperando `
    "La victima paso el chequeo de activo y quedo esperando el lock de terapeutas" `
    "La victima nunca llego a esperar el lock: la ventana no se abrio y el resultado no significa nada"

# La baja se lanza como JOB, y ese cambio es la noticia. Antes se llamaba
# derecho, porque entraba: el chequeo de `activo` se hacia sin lock y afuera de
# la transaccion, asi que la baja se colaba entre el chequeo y el INSERT.
#
# Desde que p_registrar_sesion revalida bajo `pacientes FOR SHARE` DENTRO de la
# transaccion, esa ventana no existe: la victima sostiene el lock compartido
# mientras espera, y el FOR UPDATE de la baja tiene que esperarla. Llamarla
# derecho colgaria el test hasta que la victima termine.
#
# Lo que se afirma abajo ya no es "la baja entro" —esa precondicion dejo de ser
# alcanzable, que es exactamente el arreglo— sino la GARANTIA nueva: mientras
# la victima sostiene el lock, la baja NO puede aplicarse.
$jobBaja = Start-Job -ScriptBlock $jobScript -ArgumentList $script:MysqlExe, $script:LoginPath, $Database, @"
CALL p_baja_paciente($pac4, @obj, @asig, @msg);
SELECT IFNULL(@obj,'NULL'), IFNULL(@asig,'NULL'), @msg;
"@

# Dos transacciones esperando: la victima por `terapeutas` (la retiene el
# atacante) y la baja por `pacientes` (lo retiene la victima). Esa segunda
# espera ES la garantia; si no aparece, la baja se estaria colando.
$lasDosEsperando = Esperar-Condicion @"
SELECT COUNT(*) - 1 FROM information_schema.innodb_trx WHERE trx_state = 'LOCK WAIT';
"@

$sigueActivo = [int](Get-ScalarValue $Database "SELECT activo FROM pacientes WHERE id = $pac4;")
$resultados += Assert-True $modulo "carrera_la_baja_no_entra_mientras_la_victima_sostiene_el_lock" `
    ($lasDosEsperando -and $sigueActivo -eq 1) `
    "La baja quedo esperando el lock que sostiene la victima y el paciente sigue activo: la ventana entre el chequeo y el INSERT ya no existe" `
    "La baja no quedo bloqueada por la victima (dos esperas detectadas=$lasDosEsperando, paciente activo=$sigueActivo). Si la baja se aplico mientras la victima estaba detenida DESPUES de su chequeo, la ventana volvio a abrirse."

Wait-Job $jobAtacante | Out-Null; Receive-Job $jobAtacante | Out-Null; Remove-Job $jobAtacante
$salidaVictima = Receive-Job (Wait-Job $jobVictima); Remove-Job $jobVictima
$salidaBaja = Receive-Job (Wait-Job $jobBaja); Remove-Job $jobBaja

$finVictima = Get-UltimaLinea $salidaVictima
$finBaja = Get-UltimaLinea $salidaBaja

# El estado final NO se mide contando "sesiones sobre un paciente inactivo":
# esa cuenta da 1 tambien cuando todo funciono bien, porque la sesion se
# registro con el paciente todavia activo y la baja llego despues. Es el mismo
# error de forma que tenia la asercion de la regla 4. Lo que se afirma es la
# SERIALIZACION: las dos operaciones ocurrieron una despues de la otra y las
# dos vieron un estado coherente.
$estadoFinal = Get-ScalarValue $Database @"
SELECT CONCAT_WS('|', (SELECT activo FROM pacientes WHERE id = $pac4),
                      (SELECT COUNT(*) FROM sesiones WHERE id_paciente = $pac4));
"@
$resultados += Assert-True $modulo "carrera_las_dos_operaciones_quedan_serializadas" `
    ($finVictima -notmatch "dado de baja" -and $finBaja -match "correctamente" -and $estadoFinal -eq "0|1") `
    "La sesion se registro con el paciente activo y la baja se aplico despues: sin estado intermedio (paciente|sesiones = $estadoFinal)" `
    "Las dos operaciones no quedaron serializadas. Victima: '$finVictima' | Baja: '$finBaja' | estado final (activo|sesiones): $estadoFinal"

# =======================================================================
# GRUPO 6 — la misma forma, adentro de p_baja_paciente
#
# `SELECT COUNT(*), MAX(activo) INTO v_existe, v_activo` tambien corre ANTES
# del START TRANSACTION y no se vuelve a mirar despues del FOR UPDATE. O sea
# que la decision "este paciente estaba activo" se toma con un dato que puede
# haber cambiado para cuando se escribe.
#
# Consecuencia: dos bajas simultaneas se dan las dos por buenas. La segunda
# pisa `fecha_baja` y devuelve 0/0, con el mensaje de exito. No corrompe datos
# —es idempotente— pero el endpoint le contesta 200 "Paciente dado de baja
# correctamente, 0 objetivos archivados" a una operacion que no hizo nada,
# cuando el propio procedimiento tiene un camino para decir "ya estaba dado de
# baja". Se mide igual que la anterior, con las mismas guardas.
# =======================================================================

$pac5 = Nuevo-Paciente "CINCO"
$null = Invoke-Sql -Database $Database -Sql `
    "INSERT INTO objetivos_terapeuticos (id_paciente, descripcion, activo) VALUES ($pac5, 'Objetivo del cinco', TRUE);"

$jobRetieneP = Start-Job -ScriptBlock $jobScript -ArgumentList $script:MysqlExe, $script:LoginPath, $Database, @"
START TRANSACTION;
SELECT id FROM pacientes WHERE id = $pac5 FOR UPDATE;
SELECT SLEEP($SEGUNDOS_DE_RETENCION);
COMMIT;
"@

$armadoP = Esperar-Condicion @"
SELECT COUNT(*) FROM performance_schema.data_locks
 WHERE OBJECT_NAME = 'pacientes' AND LOCK_TYPE = 'RECORD' AND LOCK_MODE LIKE '%X%';
"@

$sqlBaja = @"
CALL p_baja_paciente($pac5, @obj, @asig, @msg);
SELECT IFNULL(@obj,'NULL'), IFNULL(@asig,'NULL'), @msg;
"@
$jobBajaA = Start-Job -ScriptBlock $jobScript -ArgumentList $script:MysqlExe, $script:LoginPath, $Database, $sqlBaja
$jobBajaB = Start-Job -ScriptBlock $jobScript -ArgumentList $script:MysqlExe, $script:LoginPath, $Database, $sqlBaja

# Las DOS tienen que estar esperando: es lo que prueba que las dos ya leyeron
# activo=TRUE antes de que ninguna escribiera.
$lasDosEsperan = Esperar-Condicion @"
SELECT COUNT(*) - 1 FROM information_schema.innodb_trx WHERE trx_state = 'LOCK WAIT';
"@
$resultados += Assert-True $modulo "carrera_baja_las_dos_leyeron_antes_de_escribir" `
    ($armadoP -and $lasDosEsperan) `
    "Las dos bajas pasaron su chequeo de activo y quedaron esperando el lock del paciente" `
    "No se logro dejar a las dos bajas esperando (lock del atacante=$armadoP): sin eso el resultado de abajo no prueba nada"

Wait-Job $jobRetieneP | Out-Null; Receive-Job $jobRetieneP | Out-Null; Remove-Job $jobRetieneP
$salidaA = Receive-Job (Wait-Job $jobBajaA); Remove-Job $jobBajaA
$salidaB = Receive-Job (Wait-Job $jobBajaB); Remove-Job $jobBajaB

# La `Ultima-Linea` local se fue: hacia lo mismo que Get-UltimaLinea de
# TestHelpers.ps1, pero sin la guarda contra la salida vacia.
$finA = Get-UltimaLinea $salidaA
$finB = Get-UltimaLinea $salidaB

# Una de las dos tiene que haber sido rechazada con "ya estaba dado de baja".
$unaRechazada = ($finA -match "ya estaba dado de baja") -or ($finB -match "ya estaba dado de baja")
$resultados += Assert-True $modulo "carrera_baja_la_segunda_es_rechazada" $unaRechazada `
    "La segunda baja fue rechazada con 'ya estaba dado de baja'" `
    "Las dos bajas se dieron por buenas. A: '$finA' | B: '$finB'. La segunda pisa fecha_baja y devuelve contadores en 0 con mensaje de exito, porque la decision se tomo con la lectura previa al START TRANSACTION y no se revalido bajo el FOR UPDATE."

# =======================================================================
# GRUPO 7 — sesiones retroactivas sobre un paciente dado de baja
#
# Regla nueva (construccion, commit b34954d): el corte NO es el estado del
# paciente sino la FECHA de la sesion contra `fecha_baja`. Una sesion que
# ocurrio antes de la baja se puede cargar despues; una posterior a la baja no,
# porque no ocurrio.
#
# El caso real es la terapeuta que atendio el viernes y carga el lunes. Antes
# la unica salida era reactivar, cargar y volver a dar de baja, y eso pisaba
# `fecha_baja`: corregir un olvido administrativo terminaba falseando la fecha
# del alta medica.
#
# LOS TRES BORDES SE PRUEBAN JUNTOS A PROPOSITO. La condicion es
# `p_fecha > v_fecha_baja`, o sea que el dia exacto de la baja ENTRA. Un `>=`
# por error correria el limite un dia y ninguno de los otros dos casos lo
# notaria: el de un dia antes seguiria pasando y el de un dia despues seguiria
# fallando. El borde exacto es el unico que distingue las dos versiones.
# =======================================================================

$pac6 = Nuevo-Paciente "SEIS"
$null = Llamar-Baja $pac6
$fechaBaja = Get-ScalarValue $Database "SELECT fecha_baja FROM pacientes WHERE id = $pac6;"

function Probar-SesionRetroactiva {
    param([string]$Test, [string]$ExpresionFecha, [bool]$DebeAceptarse, [string]$Porque)
    $r = Invoke-Sql -Database $Database -Sql @"
SET @f = $ExpresionFecha;
CALL p_registrar_sesion(1, $pac6, @f, '08:00:00', '09:00:00', 'completa', NULL, NULL, @id, @msg);
SELECT IFNULL(@id,'NULL'), @msg, @f;
"@
    $ultima = Get-UltimaLineaSql $r
    $seAcepto = ($ultima -notmatch "^NULL")
    if ($DebeAceptarse) {
        return Assert-True $modulo $Test $seAcepto `
            "Aceptada, como corresponde ($Porque). Respuesta: $ultima" `
            "RECHAZADA una sesion que tenia que entrar ($Porque). Respuesta: $ultima"
    }
    return Assert-True $modulo $Test (-not $seAcepto -and $ultima -match "hasta el dia de la baja") `
        "Rechazada con el mensaje correcto ($Porque). Respuesta: $ultima" `
        "ACEPTADA una sesion que no tenia que entrar ($Porque). Respuesta: $ultima"
}

$resultados += Probar-SesionRetroactiva "retroactiva_un_dia_antes_de_la_baja_se_acepta" `
    "DATE_SUB('$fechaBaja', INTERVAL 1 DAY)" $true "ocurrio antes de la baja"

$resultados += Probar-SesionRetroactiva "retroactiva_el_dia_exacto_de_la_baja_se_acepta" `
    "'$fechaBaja'" $true "el corte es p_fecha mayor a fecha_baja, asi que el dia de la baja entra"

$resultados += Probar-SesionRetroactiva "retroactiva_un_dia_despues_de_la_baja_se_rechaza" `
    "DATE_ADD('$fechaBaja', INTERVAL 1 DAY)" $false "es posterior a la baja: esa sesion no ocurrio"

$sesionesDelSeis = [int](Get-ScalarValue $Database "SELECT COUNT(*) FROM sesiones WHERE id_paciente = $pac6;")
$resultados += Assert-True $modulo "retroactiva_la_rechazada_no_dejo_fila" ($sesionesDelSeis -eq 2) `
    "Quedaron las 2 sesiones aceptadas y ninguna de la rechazada" `
    "Quedaron $sesionesDelSeis sesiones y tenian que quedar 2: la rechazada dejo fila"

# --- La carrera de siempre, ahora sobre la regla de fecha ----------------
#
# Con la sesion fechada DESPUES de la baja que esta por ocurrir, si la baja se
# colara entre el chequeo y el INSERT quedaria registrada una sesion que la
# regla nueva prohibe. La garantia es la misma que en el grupo 5, y se afirma
# igual: la baja no entra mientras la victima sostiene el lock.

$pac7 = Nuevo-Paciente "SIETE"

$jobAtacante7 = Start-Job -ScriptBlock $jobScript -ArgumentList $script:MysqlExe, $script:LoginPath, $Database, @"
START TRANSACTION;
SELECT id FROM terapeutas WHERE id = 1 FOR UPDATE;
SELECT SLEEP($SEGUNDOS_DE_RETENCION);
COMMIT;
"@
$armado7 = Esperar-Condicion @"
SELECT COUNT(*) FROM performance_schema.data_locks
 WHERE OBJECT_NAME = 'terapeutas' AND LOCK_TYPE = 'RECORD' AND LOCK_MODE LIKE '%X%';
"@

# Fecha futura: hoy el paciente esta activo y la sesion es legitima; despues de
# la baja, la misma fecha seria posterior a fecha_baja y estaria prohibida.
$jobVictima7 = Start-Job -ScriptBlock $jobScript -ArgumentList $script:MysqlExe, $script:LoginPath, $Database, @"
CALL p_registrar_sesion(1, $pac7, DATE_ADD(CURRENT_DATE, INTERVAL 10 DAY), '12:00:00', '13:00:00', 'incompleta', NULL, NULL, @id, @msg);
SELECT IFNULL(@id,'NULL'), @msg;
"@
$esperando7 = Esperar-Condicion @"
SELECT COUNT(*) FROM information_schema.innodb_trx WHERE trx_state = 'LOCK WAIT';
"@

$jobBaja7 = Start-Job -ScriptBlock $jobScript -ArgumentList $script:MysqlExe, $script:LoginPath, $Database, @"
CALL p_baja_paciente($pac7, @obj, @asig, @msg);
SELECT IFNULL(@obj,'NULL'), IFNULL(@asig,'NULL'), @msg;
"@
$lasDosEsperando7 = Esperar-Condicion @"
SELECT COUNT(*) - 1 FROM information_schema.innodb_trx WHERE trx_state = 'LOCK WAIT';
"@
$sigueActivo7 = [int](Get-ScalarValue $Database "SELECT activo FROM pacientes WHERE id = $pac7;")

$resultados += Assert-True $modulo "retroactiva_carrera_la_baja_espera_a_la_sesion_en_vuelo" `
    ($armado7 -and $esperando7 -and $lasDosEsperando7 -and $sigueActivo7 -eq 1) `
    "Con una sesion en vuelo, la baja queda esperando y el paciente sigue activo" `
    "No se logro dejar la baja esperando detras de la sesion (atacante=$armado7, victima esperando=$esperando7, dos esperas=$lasDosEsperando7, activo=$sigueActivo7)"

Wait-Job $jobAtacante7 | Out-Null; Receive-Job $jobAtacante7 | Out-Null; Remove-Job $jobAtacante7
$finVictima7 = Get-UltimaLinea (Receive-Job (Wait-Job $jobVictima7))
Remove-Job $jobVictima7
$finBaja7 = Get-UltimaLinea (Receive-Job (Wait-Job $jobBaja7))
Remove-Job $jobBaja7

# La sesion quedo con fecha POSTERIOR a fecha_baja, y esta bien: se decidio
# cuando el paciente estaba activo. Lo que no puede pasar es que se haya
# decidido DESPUES de la baja. Por eso se afirma el orden, no el estado.
$resultados += Assert-True $modulo "retroactiva_carrera_la_sesion_se_decidio_antes_de_la_baja" `
    ($finVictima7 -notmatch "^NULL" -and $finBaja7 -match "correctamente") `
    "La sesion se registro con el paciente activo y la baja se aplico despues. Victima: $finVictima7" `
    "Orden inesperado. Victima: '$finVictima7' | Baja: '$finBaja7'"

Write-ResultsTable $resultados
return $resultados

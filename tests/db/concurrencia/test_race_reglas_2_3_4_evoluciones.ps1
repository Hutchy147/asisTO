# tests/db/concurrencia/test_race_reglas_2_3_4_evoluciones.ps1
#
# HALLAZGO CRITICO (ronda 2 de auditoria): la correccion de concurrencia
# aplicada a la regla 1 (objetivos activos) y la regla 6 (solape de
# sesiones) -- lock FOR UPDATE sobre la fila padre + FOR SHARE en el
# conteo -- NO se aplico a trg_evoluciones_validar_insert/_update. Esos
# triggers siguen leyendo sesiones.estado y objetivos_terapeuticos.activo
# / id_paciente con un SELECT comun, sin ningun lock. Es la MISMA clase de
# carrera que ya se habia encontrado y cerrado en otro lado, sin cerrar
# aca.
#
# Se confirmaron los tres casos con conexiones reales (ver AUDITORIA.md
# para el detalle completo de cada uno):
#
#   - Regla 4: mientras se archiva un objetivo, se puede cargar una
#     evolucion nueva sobre el (todavia lo ve activo), o sea que se crea una
#     evolucion que el trigger tenia que haber rechazado.
#   - Regla 2: mientras se marca una sesion como ausencia, se puede
#     cargar una evolucion nueva sobre ella (todavia la ve sin marcar).
#     Termina en ausencia Y con una evolucion cargada.
#   - Regla 3: mientras se mueve un objetivo a otro paciente, se puede
#     cargar una evolucion nueva sobre el desde una sesion del paciente
#     ORIGINAL (todavia ve el paciente viejo). Termina con el objetivo en
#     el paciente nuevo y la evolucion apuntando a una sesion del paciente
#     viejo.
#
# ESTADO ACTUAL (actualizado el 2026-08-12; el parrafo anterior decia que se
# esperaba que los tres FALLARAN, y quedo viejo). La correccion se aplico:
# los dos SELECT del trigger llevan FOR SHARE, y los tres casos PASAN. Lo que
# afirman ahora es que la regla aguanta la carrera, no que se rompe.
#
# Cada caso lleva ademas su propia asercion "el_ataque_quedo_armado": si la
# conexion A no llego a tomar el lock, el caso se reporta en rojo por eso y no
# por su estado final. Sin ese control, este archivo ya dio un FAIL que no era
# del producto -- ver Esperar-LockExclusivo, mas abajo.
#
# Uso:
#   .\test_race_reglas_2_3_4_evoluciones.ps1 -Database asisto_test_audit

param(
    [string]$Database
)

. "$PSScriptRoot\..\lib\TestHelpers.ps1"


# Sin -Database explicito, el nombre sale del rol de la terminal
# (ASISTO_ROL). Con el nombre fijo de antes, dos terminales corriendo
# esto a la vez usaban la misma base y se la destruian entre si.
if (-not $PSBoundParameters.ContainsKey('Database')) {
    $Database = Get-NombreBaseDePrueba -Base "asisto_test_audit" `
        -EjemploExplicito '.\test_race_reglas_2_3_4_evoluciones.ps1 -Database mi_base'
}

$modulo = "concurrencia"
$resultados = @()

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

function Iniciar-ConexionQueMantieneAbierta {
    param([string]$Database, [string]$SqlConSleep)
    Start-Job -ScriptBlock $jobScript -ArgumentList $script:MysqlExe, $script:LoginPath, $Database, $SqlConSleep
}

# Espera a que la conexion A tenga tomado DE VERDAD el lock exclusivo sobre la
# tabla que esta modificando, en vez de dormir un tiempo fijo y confiar.
#
# POR QUE EXISTE (2026-08-12). Los tres casos arrancaban la conexion A con
# Start-Job y despues hacian "Start-Sleep -Seconds 1". Ese segundo no alcanza:
# el PRIMER Start-Job de la sesion paga el arranque en frio del runspace de
# PowerShell mas la conexion a MySQL. Medido en esta maquina, el lock recien
# aparece a los 3,17 s. Con lo cual la conexion B disparaba unos dos segundos
# ANTES de que hubiera algo con que competir: insertaba contra un objetivo
# todavia activo (legitimo), y A lo archivaba despues. El estado final quedaba
# igual que el del bug -- una evolucion sobre un objetivo archivado -- y el
# caso 1 daba FAIL sin que hubiera ninguna carrera. Los casos 2 y 3 pasaban
# porque para entonces el job ya estaba caliente y arrancaba a tiempo.
#
# Verificado con esta espera: la conexion B es rechazada con
# "ERROR 1644 (45000) ... No se puede cargar evolucion sobre un objetivo
# archivado". El trigger nunca estuvo mal; estaba mal el banco.
#
# Es el criterio 1 de AUDITORIA.md aplicado a este archivo: un banco que
# depende de que un proceso arranque en menos de un segundo no esta midiendo
# concurrencia, esta midiendo la carga de la maquina.
#
# Necesita privilegio PROCESS para leer performance_schema.data_locks. Estas
# suites se conectan con --login-path=asisto, que lo tiene; `asisto_app` NO
# (da 1227), asi que esto no se puede mover tal cual a un test que corra con
# el usuario de la app.
function Esperar-LockExclusivo {
    param(
        [Parameter(Mandatory)] [string]$Database,
        [Parameter(Mandatory)] [string]$Tabla,
        [int]$SegundosMaximo = 20
    )
    $reloj = [Diagnostics.Stopwatch]::StartNew()
    while ($reloj.Elapsed.TotalSeconds -lt $SegundosMaximo) {
        $n = Get-ScalarValue -Database $Database -Sql @"
SELECT COUNT(*) FROM performance_schema.data_locks
 WHERE OBJECT_NAME = '$Tabla' AND LOCK_TYPE = 'RECORD' AND LOCK_MODE LIKE '%X%';
"@
        if ([int]$n -gt 0) { return $true }
    }
    return $false
}

# --- Caso 1: regla 4 -- archivar un objetivo mientras se carga una
#     evolucion nueva sobre el ---------------------------------------
$idPaciente1 = ($(Invoke-Sql -Database $Database -Sql @"
CALL p_alta_paciente('Race','Evol4','2015-01-01',NULL,'HC-RACE-EVOL4', NULL, @id, @msg);
SELECT @id;
"@).StdOut -split "`r?`n" | Where-Object { $_.Trim() -ne "" } | Select-Object -Last 1).Trim()

$null = Invoke-Sql -Database $Database -Sql @"
INSERT INTO objetivos_terapeuticos (id_paciente, descripcion, activo) VALUES ($idPaciente1, 'Objetivo race regla4', TRUE);
INSERT INTO sesiones (id_terapeuta, id_paciente, fecha, hora_inicio, hora_fin, estado) VALUES (1, $idPaciente1, '2026-07-01', '07:00:00', '07:30:00', 'completa');
"@
$idObjetivo4 = [int](Get-ScalarValue $Database "SELECT id FROM objetivos_terapeuticos WHERE id_paciente=$idPaciente1 AND descripcion='Objetivo race regla4';")
$idSesion4 = [int](Get-ScalarValue $Database "SELECT id FROM sesiones WHERE id_paciente=$idPaciente1 AND fecha='2026-07-01';")

$jobA1 = Iniciar-ConexionQueMantieneAbierta $Database @"
START TRANSACTION;
UPDATE objetivos_terapeuticos SET activo = FALSE WHERE id = $idObjetivo4;
SELECT SLEEP(4);
COMMIT;
"@
$armado1 = Esperar-LockExclusivo -Database $Database -Tabla 'objetivos_terapeuticos'
$resultados += Assert-True $modulo "race_regla4_el_ataque_quedo_armado" $armado1 `
    "La conexion A tomo el lock exclusivo antes de disparar la conexion B" `
    "La conexion A nunca tomo el lock: lo que siga NO es una carrera y su resultado no significa nada"
$rB1 = Invoke-Sql -Database $Database -Sql `
    "INSERT INTO evoluciones (id_sesion, id_objetivo, valor) VALUES ($idSesion4, $idObjetivo4, 3);"
Wait-Job $jobA1 | Out-Null; Receive-Job $jobA1 | Out-Null; Remove-Job $jobA1

# LO QUE SE AFIRMA ACA CAMBIO EL 2026-08-13, y el cambio es conceptual, no
# tecnico. Antes esto contaba "evoluciones que quedaron sobre un objetivo
# archivado" y exigia cero. Esa nunca fue la regla:
#
#   - Archivar a mano un objetivo QUE YA TIENE evoluciones esta permitido y
#     produce ese mismo estado. Verificado: el UPDATE devuelve 0.
#   - La baja de paciente lo produce a proposito, y es el motivo por el que
#     archiva: congelar el texto contra el que se puntuaron esas evoluciones.
#   - El seed lo trae desde que siembra un paciente dado de baja con historia.
#
# La regla 4 del CLAUDE.md dice otra cosa: no se puede CARGAR una evolucion
# sobre un objetivo archivado. Es una regla sobre la escritura nueva, no sobre
# el estado final. Por eso ahora se afirma que la conexion B fue RECHAZADA.
#
# POR QUE LOS CASOS 2 Y 3 SI PUEDEN MIRAR EL ESTADO FINAL: en esos dos la
# transicion inversa tambien esta cerrada —marcar como ausencia una sesion con
# evoluciones da 1644, y mover a otro paciente un objetivo con evoluciones
# tambien—, asi que ahi el estado prohibido es inalcanzable por cualquier
# camino. En la regla 4 esa puerta esta abierta a proposito. Esa asimetria es
# justamente lo que hacia falsa la asercion vieja.
$evolucionesDelObjetivo4 = [int](Get-ScalarValue $Database `
    "SELECT COUNT(*) FROM evoluciones WHERE id_objetivo = $idObjetivo4;")
$resultados += Assert-True $modulo "race_regla4_la_evolucion_nueva_es_rechazada" `
    ($rB1.ExitCode -ne 0 -and $rB1.StdErr -match "objetivo archivado" -and $evolucionesDelObjetivo4 -eq 0) `
    "La evolucion nueva fue rechazada por la regla 4 y no se escribio ninguna fila" `
    "La conexion B logro CREAR una evolucion sobre un objetivo que ya estaba archivado (exitcode $($rB1.ExitCode), evoluciones sobre el objetivo: $evolucionesDelObjetivo4, error: $($rB1.StdErr.Trim())). El objetivo no tenia ninguna evolucion antes de la carrera, asi que esta fila es nueva."

# --- Caso 2: regla 2 -- marcar una sesion como ausencia mientras se
#     carga una evolucion nueva sobre ella ----------------------------
$null = Invoke-Sql -Database $Database -Sql @"
INSERT INTO sesiones (id_terapeuta, id_paciente, fecha, hora_inicio, hora_fin, estado) VALUES (1, 1, '2026-07-02', '07:00:00', '07:30:00', 'completa');
"@
$idSesion2 = [int](Get-ScalarValue $Database "SELECT id FROM sesiones WHERE id_paciente=1 AND fecha='2026-07-02';")

$jobA2 = Iniciar-ConexionQueMantieneAbierta $Database @"
START TRANSACTION;
UPDATE sesiones SET estado = 'ausencia' WHERE id = $idSesion2;
SELECT SLEEP(4);
COMMIT;
"@
$armado2 = Esperar-LockExclusivo -Database $Database -Tabla 'sesiones'
$resultados += Assert-True $modulo "race_regla2_el_ataque_quedo_armado" $armado2 `
    "La conexion A tomo el lock exclusivo antes de disparar la conexion B" `
    "La conexion A nunca tomo el lock: lo que siga NO es una carrera y su resultado no significa nada"
$rB2 = Invoke-Sql -Database $Database -Sql `
    "INSERT INTO evoluciones (id_sesion, id_objetivo, valor) VALUES ($idSesion2, 1, 3);"
Wait-Job $jobA2 | Out-Null; Receive-Job $jobA2 | Out-Null; Remove-Job $jobA2

$evolucionSobreAusencia = [int](Get-ScalarValue $Database @"
SELECT COUNT(*) FROM evoluciones e JOIN sesiones s ON s.id = e.id_sesion
 WHERE e.id_sesion = $idSesion2 AND s.estado = 'ausencia';
"@)
$resultados += Assert-True $modulo "race_regla2_evolucion_no_queda_sobre_ausencia" ($evolucionSobreAusencia -eq 0) `
    "No quedo ninguna evolucion sobre la sesion que termino en ausencia" `
    "Quedo una evolucion cargada sobre una sesion que termino en ausencia: la regla 2 fue violada por la carrera de concurrencia (conexion B insertar: exitcode $($rB2.ExitCode))"

# --- Caso 3: regla 3 -- mover un objetivo a otro paciente mientras se
#     carga una evolucion nueva sobre el desde una sesion del paciente
#     ORIGINAL ---------------------------------------------------------
$null = Invoke-Sql -Database $Database -Sql @"
INSERT INTO objetivos_terapeuticos (id_paciente, descripcion, activo) VALUES (1, 'Objetivo race regla3', TRUE);
INSERT INTO sesiones (id_terapeuta, id_paciente, fecha, hora_inicio, hora_fin, estado) VALUES (1, 1, '2026-07-03', '07:00:00', '07:30:00', 'completa');
"@
$idObjetivo3 = [int](Get-ScalarValue $Database "SELECT id FROM objetivos_terapeuticos WHERE id_paciente=1 AND descripcion='Objetivo race regla3';")
$idSesion3 = [int](Get-ScalarValue $Database "SELECT id FROM sesiones WHERE id_paciente=1 AND fecha='2026-07-03';")

$jobA3 = Iniciar-ConexionQueMantieneAbierta $Database @"
START TRANSACTION;
UPDATE objetivos_terapeuticos SET id_paciente = 2 WHERE id = $idObjetivo3;
SELECT SLEEP(4);
COMMIT;
"@
$armado3 = Esperar-LockExclusivo -Database $Database -Tabla 'objetivos_terapeuticos'
$resultados += Assert-True $modulo "race_regla3_el_ataque_quedo_armado" $armado3 `
    "La conexion A tomo el lock exclusivo antes de disparar la conexion B" `
    "La conexion A nunca tomo el lock: lo que siga NO es una carrera y su resultado no significa nada"
$rB3 = Invoke-Sql -Database $Database -Sql `
    "INSERT INTO evoluciones (id_sesion, id_objetivo, valor) VALUES ($idSesion3, $idObjetivo3, 3);"
Wait-Job $jobA3 | Out-Null; Receive-Job $jobA3 | Out-Null; Remove-Job $jobA3

$evolucionInconsistente3 = [int](Get-ScalarValue $Database @"
SELECT COUNT(*) FROM evoluciones e
  JOIN sesiones s ON s.id = e.id_sesion
  JOIN objetivos_terapeuticos o ON o.id = e.id_objetivo
 WHERE e.id_objetivo = $idObjetivo3 AND o.id_paciente <> s.id_paciente;
"@)
$resultados += Assert-True $modulo "race_regla3_evolucion_no_queda_inconsistente" ($evolucionInconsistente3 -eq 0) `
    "Ninguna evolucion quedo con el objetivo y la sesion en pacientes distintos" `
    "Quedo una evolucion cuyo objetivo y sesion terminaron en pacientes distintos: la regla 3 fue violada por la carrera de concurrencia (conexion B insertar: exitcode $($rB3.ExitCode))"

Write-ResultsTable $resultados
return $resultados

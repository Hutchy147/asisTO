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
#     evolucion nueva sobre el (todavia lo ve activo). Termina archivado
#     Y con una evolucion encima.
#   - Regla 2: mientras se marca una sesion como ausencia, se puede
#     cargar una evolucion nueva sobre ella (todavia la ve sin marcar).
#     Termina en ausencia Y con una evolucion cargada.
#   - Regla 3: mientras se mueve un objetivo a otro paciente, se puede
#     cargar una evolucion nueva sobre el desde una sesion del paciente
#     ORIGINAL (todavia ve el paciente viejo). Termina con el objetivo en
#     el paciente nuevo y la evolucion apuntando a una sesion del paciente
#     viejo.
#
# HOY: se espera que los tres terminen en el estado prohibido (bug
# confirmado). La correccion (agregar FOR UPDATE sobre la fila de
# sesiones/objetivos_terapeuticos que lee el trigger de evoluciones, ANTES
# de leer su estado) deberia hacer que los tres pasen a PASS.
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
    $Database = Get-NombreBaseDePrueba -Base "asisto_test_audit"
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
Start-Sleep -Seconds 1
$rB1 = Invoke-Sql -Database $Database -Sql `
    "INSERT INTO evoluciones (id_sesion, id_objetivo, valor) VALUES ($idSesion4, $idObjetivo4, 3);"
Wait-Job $jobA1 | Out-Null; Receive-Job $jobA1 | Out-Null; Remove-Job $jobA1

$evolucionSobreArchivado = [int](Get-ScalarValue $Database @"
SELECT COUNT(*) FROM evoluciones e JOIN objetivos_terapeuticos o ON o.id = e.id_objetivo
 WHERE e.id_objetivo = $idObjetivo4 AND o.activo = FALSE;
"@)
$resultados += Assert-True $modulo "race_regla4_evolucion_no_queda_sobre_archivado" ($evolucionSobreArchivado -eq 0) `
    "No quedo ninguna evolucion sobre el objetivo ya archivado" `
    "Quedo una evolucion cargada sobre un objetivo que termino archivado: la regla 4 fue violada por la carrera de concurrencia (conexion B insertar: exitcode $($rB1.ExitCode))"

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
Start-Sleep -Seconds 1
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
Start-Sleep -Seconds 1
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

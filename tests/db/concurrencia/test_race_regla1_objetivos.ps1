# tests/db/concurrencia/test_race_regla1_objetivos.ps1
#
# HALLAZGO CRITICO: trg_objetivos_limite_activos_insert cuenta los
# activos y despues inserta, sin ningun lock explicito. Un SELECT COUNT
# dentro de una transaccion no ve las filas sin confirmar de otra
# transaccion (MVCC), asi que dos transacciones que se solapan pueden
# contar 3 cada una y terminar en 5 objetivos activos.
#
# Este test fuerza la ventana de carrera con una transaccion que se
# mantiene abierta unos segundos ANTES de confirmar (simulando la
# latencia normal de un backend real: otras consultas, validaciones,
# round-trips) y comprueba si la segunda transaccion, que arranca
# mientras la primera todavia no confirmo, tambien logra insertar.
#
# HOY: se espera que el resultado final tenga 5 activos (bug confirmado).
# Despues de una correccion (lock explicito, SELECT ... FOR UPDATE,
# o una constraint distinta), deberia quedar en 4 y este test pasa a PASS.
#
# Uso:
#   .\test_race_regla1_objetivos.ps1 -Database asisto_test_audit

param(
    [string]$Database
)

. "$PSScriptRoot\..\lib\TestHelpers.ps1"


# Sin -Database explicito, el nombre sale del rol de la terminal
# (ASISTO_ROL). Con el nombre fijo de antes, dos terminales corriendo
# esto a la vez usaban la misma base y se la destruian entre si.
if (-not $PSBoundParameters.ContainsKey('Database')) {
    $Database = Get-NombreBaseDePrueba -Base "asisto_test_audit" `
        -EjemploExplicito '.\test_race_regla1_objetivos.ps1 -Database mi_base'
}

$modulo = "concurrencia"
$resultados = @()

# Paciente descartable propio del test, para no depender de los ids del
# seed ni de que otros modulos hayan tocado antes los mismos pacientes.
$r = Invoke-Sql -Database $Database -Sql @"
CALL p_alta_paciente('Race','Objetivos','2015-01-01',NULL,'HC-RACE-OBJ', NULL, @id, @msg);
SELECT @id;
"@
$idPaciente = ($r.StdOut -split "`r?`n" | Where-Object { $_.Trim() -ne "" } | Select-Object -Last 1).Trim()

if (-not $idPaciente -or $idPaciente -eq "NULL") {
    $resultados += New-TestResult $modulo "race_regla1_setup" "FAIL" "No se pudo crear el paciente de prueba: $($r.StdErr)"
    Write-ResultsTable $resultados
    return $resultados
}

# Linea base segura: exactamente 3 activos. Con 3 activos, SOLO una de
# las dos conexiones concurrentes deberia poder llegar al 4to; si ambas
# lo logran, terminamos en 5 y la regla 1 quedo violada.
$null = Invoke-Sql -Database $Database -Sql @"
INSERT INTO objetivos_terapeuticos (id_paciente, descripcion, activo) VALUES ($idPaciente, 'Base A', TRUE);
INSERT INTO objetivos_terapeuticos (id_paciente, descripcion, activo) VALUES ($idPaciente, 'Base B', TRUE);
INSERT INTO objetivos_terapeuticos (id_paciente, descripcion, activo) VALUES ($idPaciente, 'Base C', TRUE);
"@

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

$sqlA = @"
START TRANSACTION;
INSERT INTO objetivos_terapeuticos (id_paciente, descripcion, activo) VALUES ($idPaciente, 'HOLD-A (4to)', TRUE);
SELECT SLEEP(4);
COMMIT;
"@
$sqlB = @"
START TRANSACTION;
INSERT INTO objetivos_terapeuticos (id_paciente, descripcion, activo) VALUES ($idPaciente, 'HOLD-B (deberia ser el 5to y rechazarse)', TRUE);
COMMIT;
"@

$job = Start-Job -ScriptBlock $jobScript -ArgumentList $script:MysqlExe, $script:LoginPath, $Database, $sqlA
Start-Sleep -Seconds 1
$rB = Invoke-Sql -Database $Database -Sql $sqlB
Wait-Job $job | Out-Null
Receive-Job $job | Out-Null
Remove-Job $job

$activosFinal = [int](Get-ScalarValue $Database `
    "SELECT COUNT(*) FROM objetivos_terapeuticos WHERE id_paciente = $idPaciente AND activo = TRUE;")

$resultados += Assert-True $modulo "race_regla1_no_supera_4_activos" ($activosFinal -le 4) `
    "Quedaron $activosFinal activos (correcto, <= 4)" `
    "Quedaron $activosFinal activos: la regla de maximo 4 fue violada por la carrera de concurrencia"

$resultados += New-TestResult $modulo "race_regla1_conexion_b_resultado" "INFO" `
    "Mensaje de la conexion B (la que arranco despues, con A sin confirmar): $($rB.StdOut -replace '[\r\n]+',' ')"

Write-ResultsTable $resultados
return $resultados

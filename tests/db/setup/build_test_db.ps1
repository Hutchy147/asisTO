# tests/db/setup/build_test_db.ps1
#
# Crea una base descartable a partir de backend/database/schema.sql y
# seed.sql, sustituyendo el nombre "asisto" por el que se pase. Nunca
# toca la base real. Se puede correr las veces que haga falta: el propio
# schema.sql empieza con DROP DATABASE IF EXISTS.
#
# Uso:
#   .\build_test_db.ps1
#   .\build_test_db.ps1 -TestDbName asisto_test_otro

param(
    [string]$TestDbName
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\..\lib\TestHelpers.ps1"

# Sin -TestDbName explicito, el nombre sale del rol de la terminal. Ver
# Get-NombreBaseDePrueba: nombres fijos = dos terminales pisandose.
if (-not $PSBoundParameters.ContainsKey('TestDbName')) {
    $TestDbName = Get-NombreBaseDePrueba -Base "asisto_test_audit"
}

if ($TestDbName -ieq "asisto") {
    throw "No se permite usar 'asisto' como base de pruebas: es la base real de Terminal 1."
}

$repoRoot = (Resolve-Path "$PSScriptRoot\..\..\..").Path
$schemaPath = Join-Path $repoRoot "backend\database\schema.sql"
$seedPath = Join-Path $repoRoot "backend\database\seed.sql"

if (-not (Test-Path $schemaPath)) { throw "No se encontro $schemaPath" }
if (-not (Test-Path $seedPath)) { throw "No se encontro $seedPath" }

$schema = Get-Content $schemaPath -Raw
$schema = $schema -replace 'DROP DATABASE IF EXISTS asisto;', "DROP DATABASE IF EXISTS $TestDbName;"
$schema = $schema -replace 'CREATE DATABASE asisto\b', "CREATE DATABASE $TestDbName"
$schema = $schema -replace '(?m)^USE asisto;', "USE $TestDbName;"

$seed = Get-Content $seedPath -Raw
$seed = $seed -replace '(?m)^USE asisto;', "USE $TestDbName;"

$tmpSchema = [System.IO.Path]::GetTempFileName()
$tmpSeed = [System.IO.Path]::GetTempFileName()
try {
    Set-Content -Path $tmpSchema -Value $schema -Encoding utf8
    Set-Content -Path $tmpSeed -Value $seed -Encoding utf8

    $r1 = Invoke-Sql -Sql (Get-Content $tmpSchema -Raw)
    if ($r1.ExitCode -ne 0) { throw "Error creando schema en $TestDbName : $($r1.StdErr)" }

    $r2 = Invoke-Sql -Database $TestDbName -Sql (Get-Content $tmpSeed -Raw)
    if ($r2.ExitCode -ne 0) { throw "Error cargando seed en $TestDbName : $($r2.StdErr)" }
} finally {
    Remove-Item $tmpSchema, $tmpSeed -ErrorAction SilentlyContinue
}

Write-Output "Base de pruebas '$TestDbName' creada a partir de schema.sql + seed.sql."

# tests/backend/run_backend_tests.ps1
#
# Corre los tests de seguridad del backend (JWT, RBAC, canal lateral de
# login, manejo de errores) contra una base de pruebas descartable propia,
# nunca contra "asisto".
#
# Se autocontiene: arma el schema+seed, otorga al usuario de MySQL de la
# app (DB_USER de backend/.env) permisos sobre esa base especifica -- el
# GRANT que existe sobre "asisto" no alcanza a una base con otro nombre --
# y aplica hashes bcrypt reales antes de correr. El GRANT es idempotente
# (correrlo de nuevo no rompe nada) y queda acotado a la base de pruebas,
# nunca a "asisto.*" ni a "*.*".
#
# Uso:
#   .\run_backend_tests.ps1
#   .\run_backend_tests.ps1 -TestDbName otro_nombre -KeepDb

param(
    [string]$TestDbName,
    [switch]$KeepDb,
    [switch]$SinReconstruirBase
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\..\db\lib\TestHelpers.ps1"

# Sin -TestDbName explicito, el nombre sale del rol de la terminal.
#
# POR QUE. Este runner arranca con build_test_db.ps1 (que hace DROP
# DATABASE) y termina con teardown_test_db.ps1 (que vuelve a borrar). Con un
# nombre fijo, dos terminales corriendo la suite a la vez se destruyen la
# base entre si a mitad de camino. Sintoma real: "Unknown database
# 'asisto_test_backend'" en medio de una corrida que habia arrancado bien.
if (-not $PSBoundParameters.ContainsKey('TestDbName')) {
    $TestDbName = Get-NombreBaseDePrueba -Base "asisto_test_backend" `
        -EjemploExplicito '.\run_backend_tests.ps1 -TestDbName mi_base'
}
Write-Output "Base de pruebas de esta terminal: $TestDbName"

$repoRoot = (Resolve-Path "$PSScriptRoot\..\..").Path
$backendDir = Join-Path $repoRoot "backend"
$python = Join-Path $backendDir "venv\Scripts\python.exe"
$envPath = Join-Path $backendDir ".env"

if (-not (Test-Path $python)) {
    throw "No se encontro $python. Este runner necesita el venv del backend ya armado."
}
if (-not (Test-Path $envPath)) {
    throw "No se encontro $envPath. Este runner necesita backend/.env ya armado (ver README)."
}

function Obtener-ValorEnv {
    param([string]$Clave)
    $linea = Get-Content $envPath | Where-Object { $_ -match "^\s*$Clave\s*=" } | Select-Object -First 1
    if (-not $linea) { return $null }
    return ($linea -split '=', 2)[1].Trim()
}

$dbUserApp = Obtener-ValorEnv "DB_USER"
if (-not $dbUserApp) { $dbUserApp = "root" }

if (-not $SinReconstruirBase) {
    & "$PSScriptRoot\..\db\setup\build_test_db.ps1" -TestDbName $TestDbName

    if ($dbUserApp -ne "root") {
        # El GRANT sobre "asisto" (decision 8 de ESTADO.md) no cubre una
        # base con otro nombre. Sin esto, generar_hashes.py y los tests
        # fallarian con "access denied" para $dbUserApp contra $TestDbName.
        # TestHelpers ya viene dot-sourceado desde arriba.
        $rGrant = Invoke-Sql -Sql @"
GRANT SELECT, INSERT, UPDATE, DELETE, EXECUTE ON ``$TestDbName``.* TO '$dbUserApp'@'localhost';
FLUSH PRIVILEGES;
"@
        if ($rGrant.ExitCode -ne 0) {
            throw "No se pudo otorgar permisos a '$dbUserApp' sobre $TestDbName : $($rGrant.StdErr)"
        }
    }

    Write-Output "Aplicando hashes bcrypt reales sobre $TestDbName ..."
    Push-Location $backendDir
    try {
        $env:DB_NAME = $TestDbName
        # Start-Process por la misma razon que en la corrida de unittest:
        # cualquier warning que el proceso escriba por stderr (p.ej. de
        # SQLAlchemy) mataria el script entero con $ErrorActionPreference=Stop.
        $procHashes = Start-Process -FilePath $python -ArgumentList @("scripts\generar_hashes.py", "--aplicar") `
            -NoNewWindow -Wait -PassThru
        if ($procHashes.ExitCode -ne 0) {
            throw "generar_hashes.py --aplicar fallo (codigo $($procHashes.ExitCode))"
        }
    } finally {
        Remove-Item Env:\DB_NAME -ErrorAction SilentlyContinue
        Pop-Location
    }
}

Write-Output ""
Write-Output "=== Corriendo tests/backend con DB_NAME=$TestDbName ==="
Write-Output ""

Push-Location $PSScriptRoot
try {
    $env:DB_NAME = $TestDbName
    # Start-Process, no "& $python ...": con $ErrorActionPreference = "Stop"
    # activo, PowerShell 5.1 envuelve cada linea de stderr de un ejecutable
    # nativo en un ErrorRecord y la promueve a error terminante -- mata el
    # script entero en la PRIMERA linea de progreso de "unittest -v" (que
    # escribe su salida por stderr). Start-Process no pasa por ese
    # mecanismo: el proceso hijo hereda la consola y escribe directo.
    $proceso = Start-Process -FilePath $python -ArgumentList @("-m", "unittest", "discover", "-s", ".", "-p", "test_*.py", "-v") `
        -NoNewWindow -Wait -PassThru
    $codigoSalida = $proceso.ExitCode
} finally {
    Remove-Item Env:\DB_NAME -ErrorAction SilentlyContinue
    Pop-Location
}

if (-not $KeepDb) {
    & "$PSScriptRoot\..\db\setup\teardown_test_db.ps1" -TestDbName $TestDbName
}

if ($codigoSalida -ne 0) {
    Write-Output ""
    Write-Output "Hubo tests en FAIL. Ver el detalle arriba y AUDITORIA.md para el hallazgo correspondiente."
}

exit $codigoSalida

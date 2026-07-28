# tests/db/setup/teardown_test_db.ps1
#
# Borra la base de pruebas descartable. Nunca acepta "asisto" como destino.
#
# Uso:
#   .\teardown_test_db.ps1
#   .\teardown_test_db.ps1 -TestDbName asisto_test_otro

param(
    [string]$TestDbName = "asisto_test_audit"
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\..\lib\TestHelpers.ps1"

if ($TestDbName -ieq "asisto") {
    throw "No se permite borrar 'asisto'."
}

$r = Invoke-Sql -Sql "DROP DATABASE IF EXISTS $TestDbName;"
if ($r.ExitCode -ne 0) { throw "Error al borrar $TestDbName : $($r.StdErr)" }

Write-Output "Base de pruebas '$TestDbName' eliminada."

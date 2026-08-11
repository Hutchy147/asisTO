# tests/db/setup/teardown_test_db.ps1
#
# Borra la base de pruebas descartable. Nunca acepta "asisto" como destino.
#
# Uso:
#   .\teardown_test_db.ps1
#   .\teardown_test_db.ps1 -TestDbName asisto_test_otro

param(
    [string]$TestDbName
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\..\lib\TestHelpers.ps1"

# Mismo criterio que build_test_db.ps1: sin nombre explicito, el del rol.
# Aca importa el doble -- borrar la base del rol de al lado es justamente el
# accidente que se esta corrigiendo.
if (-not $PSBoundParameters.ContainsKey('TestDbName')) {
    $TestDbName = Get-NombreBaseDePrueba -Base "asisto_test_audit" `
        -EjemploExplicito '.\teardown_test_db.ps1 -TestDbName mi_base'
}

if ($TestDbName -ieq "asisto") {
    throw "No se permite borrar 'asisto'."
}

$r = Invoke-Sql -Sql "DROP DATABASE IF EXISTS $TestDbName;"
if ($r.ExitCode -ne 0) { throw "Error al borrar $TestDbName : $($r.StdErr)" }

Write-Output "Base de pruebas '$TestDbName' eliminada."

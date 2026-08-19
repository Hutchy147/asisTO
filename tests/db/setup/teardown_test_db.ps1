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
. "$PSScriptRoot\..\lib\BaseDescartable.ps1"

# Mismo criterio que build_test_db.ps1: sin nombre explicito, el del rol.
# Aca importa el doble -- borrar la base del rol de al lado es justamente el
# accidente que se esta corrigiendo.
if (-not $PSBoundParameters.ContainsKey('TestDbName')) {
    $TestDbName = Get-NombreBaseDePrueba -Base "asisto_test_audit" `
        -EjemploExplicito '.\teardown_test_db.ps1 -TestDbName mi_base'
}

# EL PERMISO DE BORRADO SALE DE LA MARCA, NO DEL NOMBRE.
#
# Hasta el 2026-08-19 aca habia un `if ($TestDbName -ieq "asisto") { throw }`.
# Se saco: esa forma -- una excepcion hardcodeada con un nombre adentro -- es
# la que fallo el 2026-08-17, porque `asisto_demo_prueba` no estaba en la
# excepcion y no habia manera de que lo estuviera. `asisto` sigue protegida,
# pero ahora por el mismo motivo que cualquier otra base que no sea de prueba:
# porque nadie la marco como descartable.
Assert-BaseBorrable -Database $TestDbName

# Y aunque este marcada, se respalda antes. Es lo unico que no depende de que
# quien borra haya clasificado bien.
$null = Invoke-RespaldoDeBase -Database $TestDbName -Motivo "teardown_test_db.ps1"

$r = Invoke-Sql -Sql "DROP DATABASE IF EXISTS $TestDbName;"
if ($r.ExitCode -ne 0) { throw "Error al borrar $TestDbName : $($r.StdErr)" }

Write-Output "Base de pruebas '$TestDbName' eliminada."

# tests/db/run_all.ps1
#
# Corre todos los modulos de test, cada uno contra su PROPIA base de
# pruebas descartable recien creada desde backend/database/schema.sql +
# seed.sql. Nunca toca "asisto". Pensado para volver a correrse tal cual
# despues de que Terminal 1 aplique las correcciones de AUDITORIA.md: los
# tests que hoy fallan a proposito (documentando un hallazgo) deberian
# pasar a PASS.
#
# Cada modulo usa su propia base (no una compartida) a proposito: varios
# modulos de "bordes" y "concurrencia" CREAN deliberadamente violaciones
# de las reglas de negocio para probar que existen. Si compartieran base
# con "seed", sus violaciones de prueba contaminarian los chequeos de
# coherencia del seed y se verian como si fueran del seed original,
# cuando en realidad las causo otro modulo. Aislar por base evita ese
# falso positivo sin importar el orden en que se corran los modulos.
#
# Uso:
#   .\run_all.ps1
#   .\run_all.ps1 -TestDbPrefix otro_prefijo -KeepDb
#
# -KeepDb deja las bases de pruebas creadas al terminar (por defecto se
# borran). Util para inspeccionar a mano el resultado de una corrida.

param(
    [string]$TestDbPrefix = "asisto_test_audit",
    [switch]$KeepDb
)

$ErrorActionPreference = "Stop"

$modulos = @(
    @{ Nombre = "reglas_negocio"; Script = "$PSScriptRoot\reglas_negocio\test_reglas_1_a_6.ps1" },
    @{ Nombre = "bordes";         Script = "$PSScriptRoot\bordes\test_update_delete_gaps.ps1" },
    @{ Nombre = "errores";        Script = "$PSScriptRoot\errores\test_mensajes_error.ps1" },
    @{ Nombre = "rrhh";           Script = "$PSScriptRoot\rrhh\test_contenido_clinico.ps1" },
    @{ Nombre = "seed";           Script = "$PSScriptRoot\seed\test_seed_coherencia.ps1" },
    @{ Nombre = "concurrencia_r1"; Script = "$PSScriptRoot\concurrencia\test_race_regla1_objetivos.ps1" },
    @{ Nombre = "concurrencia_r6"; Script = "$PSScriptRoot\concurrencia\test_race_regla6_sesiones.ps1" },
    @{ Nombre = "concurrencia_evol"; Script = "$PSScriptRoot\concurrencia\test_race_reglas_2_3_4_evoluciones.ps1" },
    @{ Nombre = "regla19";        Script = "$PSScriptRoot\bordes\test_regla19_objetivo_archivado_inmutable.ps1" },
    @{ Nombre = "autorizacion";   Script = "$PSScriptRoot\autorizacion\test_evolucion_autoria_respaldada_en_bd.ps1" },
    @{ Nombre = "asignaciones";   Script = "$PSScriptRoot\asignaciones\test_asignaciones_vigencia.ps1" }
)

$todos = @()
foreach ($m in $modulos) {
    $dbModulo = "${TestDbPrefix}_$($m.Nombre)"
    Write-Output ""
    Write-Output "=== $($m.Script) (base: $dbModulo) ==="
    & "$PSScriptRoot\setup\build_test_db.ps1" -TestDbName $dbModulo
    $todos += & $m.Script -Database $dbModulo
    if (-not $KeepDb) {
        & "$PSScriptRoot\setup\teardown_test_db.ps1" -TestDbName $dbModulo
    }
}

Write-Output ""
Write-Output "================ RESUMEN ================"
$todos | Format-Table -AutoSize -Property Modulo, Test, Resultado | Out-String -Width 200 | Write-Output

$pass = ($todos | Where-Object { $_.Resultado -eq "PASS" }).Count
$fail = ($todos | Where-Object { $_.Resultado -eq "FAIL" }).Count
$info = ($todos | Where-Object { $_.Resultado -eq "INFO" }).Count
Write-Output "PASS: $pass   FAIL: $fail   INFO: $info   TOTAL: $($todos.Count)"

if ($fail -gt 0) {
    Write-Output ""
    Write-Output "Tests en FAIL (ver AUDITORIA.md para el detalle de cada hallazgo):"
    $todos | Where-Object { $_.Resultado -eq "FAIL" } | ForEach-Object {
        Write-Output "  - [$($_.Modulo)] $($_.Test)"
    }
}

return $todos

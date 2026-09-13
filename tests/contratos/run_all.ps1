# tests/contratos/run_all.ps1
#
# Corre las suites de contratos y junta los resultados.
#
# POR QUE EXISTE, y es la misma razon que tests/frontend/run_all.ps1:
# hasta el 2026-09-13 esta carpeta tenia UN solo archivo, asi que "correr
# tests/contratos" y "correr ese archivo" eran lo mismo y nadie noto que no
# habia runner. Con el segundo archivo eso deja de ser cierto: sin esto, el
# que corra "la suite de contratos" de memoria va a correr el que ya conocia
# y el nuevo se vuelve un archivo que nadie sabe que existe. Es textualmente
# el problema que la sonda de UI vino a arreglar del otro lado.
#
# LA REGLA, igual que en frontend:
#
#   SI UNA SUITE NO PUDO CORRER, ESTO NO TERMINA EN VERDE.
#
# Un "se salteo" indistinguible de un "paso" es el defecto original de los
# 188 de UI. Lo que no corre sale como NO CORRIO, cuenta como fallo para el
# codigo de salida, y se nombra.
#
# ESTA SUITE NO NECESITA NADA: ni MySQL, ni navegador, ni ASISTO_ROL, ni
# backend/.env. Compara archivos fuente entre si. Es la unica de las cuatro
# que corre en cualquier maquina reciente clonada, y conviene que siga
# siendolo: no agregar aca nada que necesite una base.
#
# Uso:
#   .\run_all.ps1

$ErrorActionPreference = "Continue"

$resultados = @()
function Anotar {
    param([string]$Suite, [string]$Resultado, [string]$Detalle)
    $script:resultados += [pscustomobject]@{
        Suite = $Suite; Resultado = $Resultado; Detalle = $Detalle
    }
}

$cronometro = [System.Diagnostics.Stopwatch]::StartNew()

foreach ($suite in @(
    @{ Nombre = "largo_descripcion_objetivo"; Script = "$PSScriptRoot\test_largo_descripcion_objetivo.ps1" },
    @{ Nombre = "aridad_procedimientos";      Script = "$PSScriptRoot\test_aridad_procedimientos.ps1" }
)) {
    Write-Host ""
    Write-Host "=== $($suite.Nombre) ===" -ForegroundColor Cyan
    try {
        # Las dos suites IMPRIMEN su tabla con Write-Host y DEVUELVEN los
        # objetos. Se cuentan los OBJETOS y no se parsea la linea "PASS: n":
        # creerle a un resumen impreso es lo que dejo pasar el "74 PASS con
        # el FAIL en blanco" del 2026-08-12.
        $devueltos = @(& $suite.Script)
        $conResultado = @($devueltos | Where-Object { $_.PSObject.Properties.Name -contains 'Resultado' })
        if ($conResultado.Count -eq 0) {
            Anotar $suite.Nombre "NO CORRIO" "La suite no devolvio ningun resultado. Correla suelta para ver por que."
            continue
        }
        $p = @($conResultado | Where-Object { $_.Resultado -eq 'PASS' }).Count
        $f = @($conResultado | Where-Object { $_.Resultado -eq 'FAIL' }).Count
        $i = @($conResultado | Where-Object { $_.Resultado -eq 'INFO' }).Count
        $detalle = "PASS $p / FAIL $f / INFO $i (de $($conResultado.Count) resultados)"
        # Red por si un objeto trae un Resultado que no es ninguno de los
        # tres: sin esto se perderia sin que nadie lo note.
        if (($p + $f + $i) -ne $conResultado.Count) {
            Anotar $suite.Nombre "NO CORRIO" "$detalle -- hay resultados sin clasificar."
        } elseif ($f -eq 0) {
            Anotar $suite.Nombre "PASS" $detalle
        } else {
            Anotar $suite.Nombre "FAIL" $detalle
        }
    } catch {
        Anotar $suite.Nombre "NO CORRIO" $_.Exception.Message
    }
}

$cronometro.Stop()

Write-Host ""
Write-Host "================ RESUMEN tests/contratos ================"
$resultados | Format-Table -AutoSize -Property Suite, Resultado, Detalle | Out-String -Width 200 | Write-Host

# El @() no es cosmetico: en PowerShell 5.1, .Count sobre UNA sola
# coincidencia devuelve vacio. Criterio 6 de AUDITORIA.md.
$pass     = @($resultados | Where-Object { $_.Resultado -eq "PASS" }).Count
$fail     = @($resultados | Where-Object { $_.Resultado -eq "FAIL" }).Count
$noCorrio = @($resultados | Where-Object { $_.Resultado -eq "NO CORRIO" }).Count

Write-Host ("PASS: $pass   FAIL: $fail   NO CORRIO: $noCorrio   TOTAL: $($resultados.Count)   " +
            "({0:N1} s)" -f $cronometro.Elapsed.TotalSeconds)

if ($noCorrio -gt 0) {
    Write-Host ""
    Write-Host "ATENCION: $noCorrio suite(s) NO CORRIERON. Esto NO es verde." -ForegroundColor Yellow
    $resultados | Where-Object { $_.Resultado -eq "NO CORRIO" } | ForEach-Object {
        Write-Host "  - $($_.Suite): $($_.Detalle)" -ForegroundColor Yellow
    }
}

# Un fallo y un 'no corrio' salen los dos por codigo distinto de cero. La
# diferencia se lee en el resumen; para un CI, las dos cosas son rojo.
if ($fail -gt 0 -or $noCorrio -gt 0) { exit 1 }
exit 0

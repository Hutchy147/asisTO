# tests/frontend/run_all.ps1
#
# Corre las tres suites de frontend y junta los resultados.
#
# POR QUE EXISTE. Hasta el 2026-08-21 los archivos de esta carpeta se corrian
# sueltos, de memoria. Un test que no se corre solo termina siendo un archivo
# que nadie sabe que existe, que es la mitad del problema que la sonda de UI
# vino a arreglar: los "188 PASS de UI sobre Chrome real" no eran una suite,
# eran chequeos sueltos contados en prosa que nadie podia volver a correr.
#
# LO MAS IMPORTANTE DE ESTE ARCHIVO, y es una regla y no un detalle:
#
#   SI UNA SUITE NO PUDO CORRER, ESTO NO TERMINA EN VERDE.
#
# Un "se salteo" que no se distingue de un "paso" es exactamente el defecto de
# los 188. Cuando algo no corre, sale como NO CORRIO, cuenta como fallo para el
# codigo de salida, y el mensaje dice que hacer. Nunca se suma a los PASS ni se
# omite en silencio.
#
# Uso:
#   .\run_all.ps1
#   .\run_all.ps1 -SinNavegador     # saltea la sonda de UI A PROPOSITO, y lo
#                                   # dice; sigue sin poder terminar en verde.

param(
    [switch]$SinNavegador,
    [int]$PuertoVite = 5178,
    [int]$PuertoApi  = 5058
)

$ErrorActionPreference = "Continue"

$resultados = @()
function Anotar {
    param([string]$Suite, [string]$Resultado, [string]$Detalle)
    $script:resultados += [pscustomobject]@{
        Suite = $Suite; Resultado = $Resultado; Detalle = $Detalle
    }
}

$cronometro = [System.Diagnostics.Stopwatch]::StartNew()

# --- Los dos barridos estaticos -----------------------------------------
# No necesitan base, ni navegador, ni ASISTO_ROL: escanean frontend/src.
foreach ($estatico in @(
    @{ Nombre = "codigo_sin_camino"; Script = "$PSScriptRoot\test_codigo_sin_camino.ps1" },
    @{ Nombre = "texto_libre";       Script = "$PSScriptRoot\test_texto_libre_en_campos.ps1" }
)) {
    Write-Host ""
    Write-Host "=== $($estatico.Nombre) ===" -ForegroundColor Cyan
    try {
        # Las dos suites IMPRIMEN su tabla con Write-Host y DEVUELVEN los
        # objetos de resultado. Write-Host no pasa por el pipeline, asi que
        # esto captura solo los objetos y la tabla se ve igual en consola.
        #
        # Se cuentan los OBJETOS y no se parsea la linea "PASS: n FAIL: n":
        # contar el texto que la suite imprime es creerle su propio resumen, y
        # este proyecto ya tuvo un resumen que mentia -- 74 PASS con un FAIL
        # en blanco. Los objetos son el dato; la linea es la presentacion.
        $devueltos = @(& $estatico.Script)
        $conResultado = @($devueltos | Where-Object { $_.PSObject.Properties.Name -contains 'Resultado' })
        if ($conResultado.Count -eq 0) {
            Anotar $estatico.Nombre "NO CORRIO" "La suite no devolvio ningun resultado. Corrrela suelta para ver por que."
            continue
        }
        $p = @($conResultado | Where-Object { $_.Resultado -eq 'PASS' }).Count
        $f = @($conResultado | Where-Object { $_.Resultado -eq 'FAIL' }).Count
        $i = @($conResultado | Where-Object { $_.Resultado -eq 'INFO' }).Count
        $detalle = "PASS $p / FAIL $f / INFO $i (de $($conResultado.Count) resultados)"
        # Red por si un objeto trae un Resultado que no es ninguno de los tres:
        # sin esto se perderia sin que nadie lo note.
        if (($p + $f + $i) -ne $conResultado.Count) {
            Anotar $estatico.Nombre "NO CORRIO" "$detalle -- hay resultados sin clasificar."
        } elseif ($f -eq 0) {
            Anotar $estatico.Nombre "PASS" $detalle
        } else {
            Anotar $estatico.Nombre "FAIL" $detalle
        }
    } catch {
        Anotar $estatico.Nombre "NO CORRIO" $_.Exception.Message
    }
}

# --- La sonda de UI en Chrome real --------------------------------------
Write-Host ""
Write-Host "=== observacion_en_pantalla (Chrome real) ===" -ForegroundColor Cyan
if ($SinNavegador) {
    # Saltear a pedido sigue sin ser verde. Es una eleccion de quien corre, no
    # una suite que paso.
    Anotar "observacion_en_pantalla" "NO CORRIO" `
        "Salteada a proposito con -SinNavegador. La cobertura de UI de esta corrida es CERO."
} else {
    try {
        & "$PSScriptRoot\test_observacion_en_pantalla.ps1" -PuertoVite $PuertoVite -PuertoApi $PuertoApi
        if ($LASTEXITCODE -eq 0) {
            Anotar "observacion_en_pantalla" "PASS" "2 afirmaciones: observacion de la evolucion y notas de la sesion."
        } else {
            Anotar "observacion_en_pantalla" "FAIL" "Al menos una de las 2 afirmaciones fallo (cual, arriba)."
        }
    } catch {
        # Todo lo que impide correrla cae aca: puertos ocupados, falta
        # backend/.env, MySQL apagado, pnpm install sin hacer. Ninguno de esos
        # puede pasar por verde.
        Anotar "observacion_en_pantalla" "NO CORRIO" $_.Exception.Message
    }
}

$cronometro.Stop()

# --- Resumen -------------------------------------------------------------
Write-Host ""
Write-Host "================ RESUMEN tests/frontend ================"
$resultados | Format-Table -AutoSize -Property Suite, Resultado, Detalle | Out-String -Width 200 | Write-Host

# El @() no es cosmetico: en PowerShell 5.1, .Count sobre UNA sola coincidencia
# devuelve vacio. Ver el criterio 6 de AUDITORIA.md, que salio de un rojo que
# se escondio exactamente asi.
$pass     = @($resultados | Where-Object { $_.Resultado -eq "PASS" }).Count
$fail     = @($resultados | Where-Object { $_.Resultado -eq "FAIL" }).Count
$noCorrio = @($resultados | Where-Object { $_.Resultado -eq "NO CORRIO" }).Count

Write-Host ("PASS: $pass   FAIL: $fail   NO CORRIO: $noCorrio   TOTAL: $($resultados.Count)   " +
            "({0:N0} s)" -f $cronometro.Elapsed.TotalSeconds)

if ($noCorrio -gt 0) {
    Write-Host ""
    Write-Host "ATENCION: $noCorrio suite(s) NO CORRIERON. Esto NO es verde." -ForegroundColor Yellow
    $resultados | Where-Object { $_.Resultado -eq "NO CORRIO" } | ForEach-Object {
        Write-Host "  - $($_.Suite): $($_.Detalle)" -ForegroundColor Yellow
    }
    Write-Host ""
    Write-Host "  La sonda de UI necesita, en este orden:" -ForegroundColor Yellow
    Write-Host "    1. pnpm install en tests/frontend (una sola vez)"
    Write-Host "    2. MySQL levantado y backend/.env armado"
    Write-Host "    3. los puertos $PuertoVite y $PuertoApi libres (se cambian con -PuertoVite / -PuertoApi)"
}

# Un fallo y un 'no corrio' salen los dos por codigo distinto de cero. La
# diferencia se lee en el resumen; para un CI, las dos cosas son rojo.
if ($fail -gt 0 -or $noCorrio -gt 0) { exit 1 }
exit 0

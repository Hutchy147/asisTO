# tests/db/errores/test_mensajes_error.ps1
#
# El CLAUDE.md pide procedimientos con OUT p_mensaje para el resultado, y
# la consigna de auditoria pide mensajes legibles que no filtren
# estructura interna (nombres de tabla, de constraint, de la base).
#
# p_registrar_evolucion hace esto bien: los triggers validan la
# existencia de la sesion/objetivo ANTES de que la FK pueda disparar, asi
# que el mensaje siempre es el texto en castellano del SIGNAL.
#
# p_alta_paciente y p_registrar_sesion NO validan la existencia de sus
# columnas FK (id_usuario, id_terapeuta, id_paciente) antes del INSERT:
# si la referencia no existe, el error crudo de MySQL (con nombre de
# tabla, constraint y hasta el nombre de la base) llega tal cual al
# llamador, concatenado despues de "Error al ...: ".
#
# Hay algo peor todavia, encontrado corriendo este mismo test: ese
# mensaje concatenado puede SUPERAR el VARCHAR(255) de p_mensaje. Cuando
# eso pasa, el propio EXIT HANDLER revienta con un segundo error (Data
# too long for column 'p_mensaje') que NADIE captura: el CALL entero
# termina en un error crudo de MySQL sin capturar, en vez de devolver el
# OUT p_mensaje esperado. Contra la base real "asisto" el mensaje de
# p_alta_paciente mide 249/255 y el de p_registrar_sesion 246/255: pasa
# hoy, pero por un margen de 6 y 9 caracteres, dependiendo pura y
# exclusivamente de la longitud del nombre de la base y del nombre de la
# constraint que la FK viole. Contra esta base de pruebas (nombre mas
# largo) el desborde SI ocurre, lo que sirve para probarlo en los hechos.
#
# Estos tests documentan el comportamiento DESEADO (mensaje legible, sin
# estructura interna, y que nunca rompa el contrato OUT p_mensaje) y hoy
# reportan FAIL a proposito donde corresponde.
#
# Uso:
#   .\test_mensajes_error.ps1 -Database asisto_test_audit

param(
    [string]$Database
)

. "$PSScriptRoot\..\lib\TestHelpers.ps1"


# Sin -Database explicito, el nombre sale del rol de la terminal
# (ASISTO_ROL). Con el nombre fijo de antes, dos terminales corriendo
# esto a la vez usaban la misma base y se la destruian entre si.
if (-not $PSBoundParameters.ContainsKey('Database')) {
    $Database = Get-NombreBaseDePrueba -Base "asisto_test_audit" `
        -EjemploExplicito '.\test_mensajes_error.ps1 -Database mi_base'
}

$modulo = "errores"
$resultados = @()

# Palabras que un mensaje de error NUNCA deberia contener si esta bien
# traducido: son vocabulario interno de MySQL/InnoDB, no del dominio.
$marcasFuga = @("CONSTRAINT", "FOREIGN KEY", "foreign key constraint", "fk_", $Database)

function Get-ResultadoProcedimiento {
    param([string]$Database, [string]$Sql)
    $r = Invoke-Sql -Database $Database -Sql $Sql
    if ($r.ExitCode -ne 0) {
        return [pscustomobject]@{ Crasheo = $true; Mensaje = $r.StdErr.Trim() }
    }
    $lineas = $r.StdOut -split "`r?`n" | Where-Object { $_.Trim() -ne "" }
    return [pscustomobject]@{ Crasheo = $false; Mensaje = ($lineas | Select-Object -Last 1) }
}

# Verifica DOS cosas a la vez: que la llamada no haya reventado con un
# error sin capturar (peor caso), y que si devolvio un mensaje, ese
# mensaje no filtre estructura interna.
function Test-MensajeSanoYSinFuga {
    param([string]$Modulo, [string]$Test, $Resultado)
    if ($Resultado.Crasheo) {
        return New-TestResult $Modulo $Test "FAIL" `
            "La llamada termino en un error SIN CAPTURAR (el contrato OUT p_mensaje se rompio): $($Resultado.Mensaje)"
    }
    foreach ($marca in $marcasFuga) {
        if ($Resultado.Mensaje -match [regex]::Escape($marca)) {
            return New-TestResult $Modulo $Test "FAIL" `
                "El mensaje filtra estructura interna ('$marca'): $($Resultado.Mensaje)"
        }
    }
    return New-TestResult $Modulo $Test "PASS" "Mensaje legible, sin estructura interna: $($Resultado.Mensaje)"
}

# --- p_alta_paciente con id_usuario que no existe ----------------------
$res1 = Get-ResultadoProcedimiento $Database `
    "CALL p_alta_paciente('Test','Fuga','2020-01-01',NULL,'HC-FUGA-001', 999999, @id, @msg); SELECT @msg;"
$resultados += Test-MensajeSanoYSinFuga $modulo "alta_paciente_id_usuario_inexistente" $res1

# --- p_registrar_sesion con terapeuta/paciente que no existen ----------
$res2 = Get-ResultadoProcedimiento $Database `
    "CALL p_registrar_sesion(999999, 999999, '2026-09-05', '09:00:00', '10:00:00', 'incompleta', NULL, @id, @msg); SELECT @msg;"
$resultados += Test-MensajeSanoYSinFuga $modulo "registrar_sesion_fk_inexistente" $res2

# --- p_alta_paciente, nro_historia duplicado por el camino normal ------
# (sin carrera: alta secuencial. La carrera esta cubierta en
# concurrencia/, y ahi el mensaje SI es el crudo de MySQL cuando la
# UNIQUE es la que atrapa el duplicado en vez del chequeo amigable.)
$null = Invoke-Sql -Database $Database -Sql `
    "CALL p_alta_paciente('Test','Dup','2020-01-01',NULL,'HC-FUGA-002', NULL, @id, @msg);"
$res3 = Get-ResultadoProcedimiento $Database `
    "CALL p_alta_paciente('Test','Dup2','2020-01-01',NULL,'HC-FUGA-002', NULL, @id, @msg); SELECT @msg;"
$resultados += Test-MensajeSanoYSinFuga $modulo "alta_paciente_historia_duplicada_camino_normal" $res3

# --- Regresion: p_registrar_evolucion con sesion inexistente (ya OK) ---
# p_registrar_evolucion tiene 7 parametros desde que se cerro M1 (se
# agrego p_id_terapeuta, ver tests/db/autorizacion/). La sesion no
# existe, asi que v_ter_sesion queda NULL y el chequeo de autoria ni
# corre (esta condicionado a "IF v_ter_sesion IS NOT NULL"): el valor de
# p_id_terapeuta que se mande aca no cambia lo que se esta probando, que
# es el mensaje de sesion inexistente.
$res4 = Get-ResultadoProcedimiento $Database `
    "CALL p_registrar_evolucion(999999, 1, 3, NULL, 1, @id, @msg); SELECT @msg;"
$resultados += Test-MensajeSanoYSinFuga $modulo "registrar_evolucion_sesion_inexistente" $res4

Write-ResultsTable $resultados
return $resultados

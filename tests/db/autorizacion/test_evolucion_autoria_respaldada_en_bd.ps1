# tests/db/autorizacion/test_evolucion_autoria_respaldada_en_bd.ps1
#
# CERRADO — hallazgo M1 de AUDITORIA.md.
#
# Este archivo se llamaba test_evolucion_autoria_NO_respaldada_en_bd.ps1
# y documentaba que p_registrar_evolucion no tenia ningun concepto de
# autoria. Terminal 1 le agrego el parametro p_id_terapeuta: el
# procedimiento ahora exige declarar quien registra y rechaza que no
# coincida con sesiones.id_terapeuta. Se renombra y se reescribe en
# positivo en vez de dejarlo afirmando un estado que ya no es cierto.
#
# LO QUE ESTO NO CIERRA, documentado en el propio schema.sql y NO es un
# hallazgo nuevo: un INSERT directo contra `evoluciones`, bypaseando el
# procedimiento, sigue sin ningun control de autoria — un trigger no
# tiene forma de saber quien esta logueado. Lo que se gana es que
# CUALQUIER camino que use el procedimiento esta obligado a declarar el
# autor, en vez de poder omitirlo. El ultimo test de este archivo
# confirma que ese residuo sigue ahi a proposito, para que no se lea como
# sorpresa ni como regresion el dia que alguien lo encuentre.
#
# Uso:
#   .\test_evolucion_autoria_respaldada_en_bd.ps1 -Database asisto_test_audit

param(
    [string]$Database = "asisto_test_audit"
)

. "$PSScriptRoot\..\lib\TestHelpers.ps1"

$modulo = "autorizacion"
$resultados = @()

function Invocar-RegistrarEvolucion {
    param([string]$Database, $IdSesion, $IdObjetivo, $Valor, $IdTerapeuta)
    $terapeutaSql = if ($null -eq $IdTerapeuta) { "NULL" } else { "$IdTerapeuta" }
    $r = Invoke-Sql -Database $Database -Sql @"
CALL p_registrar_evolucion($IdSesion, $IdObjetivo, $Valor, NULL, $terapeutaSql, @id, @msg);
SELECT @id, @msg;
"@
    $lineas = $r.StdOut -split "`r?`n" | Where-Object { $_.Trim() -ne "" }
    [pscustomobject]@{
        ExitCode = $r.ExitCode
        StdErr   = $r.StdErr
        Ultima   = ($lineas | Select-Object -Last 1)
    }
}

# --- La firma exige el parametro: 7 parametros, uno con "terapeuta" ----
# SPECIFIC_SCHEMA es obligatorio aca: information_schema.PARAMETERS es
# GLOBAL al servidor, no a la base actual. Sin este filtro, si en algun
# momento hay mas de una base con un procedimiento p_registrar_evolucion
# (por ejemplo "asisto" real + esta base de pruebas, ambas corriendo al
# mismo tiempo en el servidor), la consulta trae los parametros de las
# dos mezclados y duplica el conteo. Paso exactamente por esto corriendo
# el test: dio 14 parametros en vez de 7 porque "asisto" tambien tenia el
# procedimiento actualizado en ese momento.
$parametros = Get-ScalarValue $Database @"
SELECT GROUP_CONCAT(PARAMETER_NAME ORDER BY ORDINAL_POSITION SEPARATOR ',')
  FROM information_schema.PARAMETERS
 WHERE SPECIFIC_SCHEMA = '$Database'
   AND SPECIFIC_NAME = 'p_registrar_evolucion' AND ROUTINE_TYPE = 'PROCEDURE';
"@
$cantidadParametros = ($parametros -split ',').Count
$resultados += Assert-True $modulo "procedimiento_exige_parametro_de_terapeuta" `
    ($parametros -match 'p_id_terapeuta' -and $cantidadParametros -eq 7) `
    "Parametros ($cantidadParametros): $parametros" `
    "Parametros ($cantidadParametros): $parametros -- se esperaba p_id_terapeuta entre 7 parametros"

# Sesion 1 del seed es del terapeuta 1 (Laura), paciente 1. Objetivo 2 es
# activo, del paciente 1, y sesion 1 no tiene evolucion cargada sobre el
# todavia (la del seed es sobre el objetivo 1).

# --- Rechaza terapeuta que no coincide con el de la sesion -------------
$rMismatch = Invocar-RegistrarEvolucion -Database $Database -IdSesion 1 -IdObjetivo 2 -Valor 3 -IdTerapeuta 2
$resultados += Assert-True $modulo "rechaza_terapeuta_que_no_coincide_con_la_sesion" `
    ($rMismatch.ExitCode -eq 0 -and $rMismatch.Ultima -match 'Solo el terapeuta que atendio la sesion') `
    "Mensaje: $($rMismatch.Ultima)" `
    "No se rechazo como se esperaba. ExitCode=$($rMismatch.ExitCode) StdErr=$($rMismatch.StdErr) Ultima=$($rMismatch.Ultima)"

# --- Rechaza NULL: no declarar el autor no puede funcionar como permiso ---
# Es EL caso que importa: si NULL pasara, cualquier llamador que omita el
# parametro (en vez de mandar uno invalido) quedaria sin control.
$rNull = Invocar-RegistrarEvolucion -Database $Database -IdSesion 1 -IdObjetivo 2 -Valor 3 -IdTerapeuta $null
$resultados += Assert-True $modulo "rechaza_terapeuta_null" `
    ($rNull.ExitCode -eq 0 -and $rNull.Ultima -match 'Solo el terapeuta que atendio la sesion') `
    "Mensaje: $($rNull.Ultima)" `
    "NULL no fue rechazado: esto significa que omitir el autor equivale a un permiso. ExitCode=$($rNull.ExitCode) Ultima=$($rNull.Ultima)"

# Confirmar que ninguno de los dos intentos anteriores inserto nada
$totalTrasRechazos = [int](Get-ScalarValue $Database `
    "SELECT COUNT(*) FROM evoluciones WHERE id_sesion = 1 AND id_objetivo = 2;")
$resultados += Assert-True $modulo "rechazos_no_insertan_nada" ($totalTrasRechazos -eq 0) `
    "No se inserto ninguna evolucion tras los dos rechazos" `
    "Se encontraron $totalTrasRechazos evoluciones: un rechazo dejo algo insertado"

# --- Con el terapeuta correcto, se registra -----------------------------
$rOk = Invocar-RegistrarEvolucion -Database $Database -IdSesion 1 -IdObjetivo 2 -Valor 3 -IdTerapeuta 1
$resultados += Assert-True $modulo "acepta_terapeuta_correcto" `
    ($rOk.ExitCode -eq 0 -and $rOk.Ultima -match 'registrada correctamente') `
    "Mensaje: $($rOk.Ultima)" `
    "Con el terapeuta correcto deberia registrarse. ExitCode=$($rOk.ExitCode) Ultima=$($rOk.Ultima)"

$totalTrasOk = [int](Get-ScalarValue $Database `
    "SELECT COUNT(*) FROM evoluciones WHERE id_sesion = 1 AND id_objetivo = 2 AND valor = 3;")
$resultados += Assert-True $modulo "acepta_terapeuta_correcto_inserta_una_fila" ($totalTrasOk -eq 1) `
    "Se inserto exactamente 1 fila" "Se encontraron $totalTrasOk filas, se esperaba 1"

# --- Residuo documentado: un INSERT directo sigue sin control de autoria ---
# NO es un hallazgo nuevo ni una regresion: esta explicitamente fuera del
# alcance de M1 (lo dice el propio comentario del procedimiento en
# schema.sql). Se deja como test para que quede confirmado, no supuesto.
$null = Invoke-Sql -Database $Database -Sql "DELETE FROM evoluciones WHERE id_sesion = 1 AND id_objetivo = 2;"
$resultados += Assert-Succeeds $modulo "insert_directo_sigue_sin_control_de_autoria_residuo_documentado" $Database `
    "INSERT INTO evoluciones (id_sesion, id_objetivo, valor) VALUES (1, 2, 4);"

Write-ResultsTable $resultados
return $resultados

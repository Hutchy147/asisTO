# tests/db/autorizacion/test_evolucion_autoria_no_respaldada_en_bd.ps1
#
# HALLAZGO ESTRUCTURAL (no es un bug de las 6 reglas de negocio, es una
# caracteristica arquitectonica a tener presente): la decision 16 de
# ESTADO.md dice "solo el terapeuta que atendio la sesion puede cargarle
# evolucion", y esa regla SI se cumple -- pero unicamente en
# evoluciones_service.registrar_evolucion() (Python). p_registrar_evolucion,
# el procedimiento que hace el INSERT real, no tiene NINGUN parametro de
# terapeuta ni chequea autoria de ninguna forma.
#
# Es lo opuesto de como estan armadas las 6 reglas de negocio (que viven en
# triggers, no en el codigo de aplicacion, precisamente para que ningun
# camino de escritura las eluda -- ver C1/C3/A1 de rondas anteriores). Acá
# es al revés: la ÚNICA barrera es el código Python.
#
# Este test NO dice que este mal la decision de negocio (esta confirmada
# por planeamiento y no se toca). Documenta que, a diferencia de las 6
# reglas, esta no tiene respaldo en la base: si en el futuro algun otro
# camino llama a p_registrar_evolucion sin pasar por el servicio de Python
# (un script, una migracion, un endpoint nuevo que llame al procedimiento
# directo), la restriccion de autoria no se aplica y nadie se entera.
#
# HOY: no es explotable via HTTP -- el unico camino de la aplicacion hacia
# el procedimiento es evoluciones_service.registrar_evolucion(), que si
# valida. Este test prueba el camino directo (SQL crudo) para dejar
# constancia de que, a nivel de base, no hay ninguna barrera.
#
# Uso:
#   .\test_evolucion_autoria_no_respaldada_en_bd.ps1 -Database asisto_test_audit

param(
    [string]$Database = "asisto_test_audit"
)

. "$PSScriptRoot\..\lib\TestHelpers.ps1"

$modulo = "autorizacion"
$resultados = @()

# Sesion 1 del seed es del terapeuta 1 (Laura), paciente 1. Cargar una
# evolucion nueva via el procedimiento, sin pasar ningun dato de "quien
# la carga" -- el procedimiento no tiene forma de pedirlo.
$r = Invoke-Sql -Database $Database -Sql @"
CALL p_registrar_evolucion(1, 3, 4, 'Cargada via SQL directo -- sin ningun concepto de autoria', @id, @msg);
SELECT @id, @msg;
"@
$exitoso = $r.ExitCode -eq 0 -and $r.StdOut -match 'registrada correctamente'

$resultados += Assert-True $modulo "procedimiento_no_tiene_parametro_de_terapeuta" $exitoso `
    "p_registrar_evolucion acepto la carga sin ningun dato de autoria (documentado, no es un fallo del schema)" `
    "p_registrar_evolucion rechazo la carga: revisar si se agrego un chequeo de autoria (actualizar este test y AUDITORIA.md si es asi)"

# Confirmacion cruzada: la firma del procedimiento no tiene ningun
# parametro con "terapeuta" en el nombre.
$parametros = Get-ScalarValue $Database @"
SELECT GROUP_CONCAT(PARAMETER_NAME SEPARATOR ',')
  FROM information_schema.PARAMETERS
 WHERE SPECIFIC_NAME = 'p_registrar_evolucion' AND ROUTINE_TYPE = 'PROCEDURE';
"@
$resultados += Assert-True $modulo "firma_del_procedimiento_sin_parametro_de_autoria" `
    ($parametros -notmatch 'terapeuta') `
    "Parametros: $parametros (ninguno referido al terapeuta que carga)" `
    "Parametros: $parametros -- aparecio un parametro de terapeuta, actualizar este hallazgo"

Write-ResultsTable $resultados
return $resultados

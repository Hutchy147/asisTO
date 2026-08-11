# tests/db/reglas_negocio/test_reglas_1_a_6.ps1
#
# Regresion de las 6 reglas de negocio del CLAUDE.md por el camino
# "directo": lo que la Terminal 1 ya declaro verificado. Sirve para
# confirmar que una correccion futura no rompio el camino feliz ni los
# rechazos basicos. Los casos que eluden estas reglas por un camino
# distinto al INSERT directo estan en tests/db/bordes/.
#
# Uso (contra la base de pruebas creada por build_test_db.ps1):
#   .\test_reglas_1_a_6.ps1 -Database asisto_test_audit

param(
    [string]$Database
)

. "$PSScriptRoot\..\lib\TestHelpers.ps1"


# Sin -Database explicito, el nombre sale del rol de la terminal
# (ASISTO_ROL). Con el nombre fijo de antes, dos terminales corriendo
# esto a la vez usaban la misma base y se la destruian entre si.
if (-not $PSBoundParameters.ContainsKey('Database')) {
    $Database = Get-NombreBaseDePrueba -Base "asisto_test_audit"
}

$modulo = "reglas_negocio"
$resultados = @()

# --- Regla 1: maximo 4 objetivos activos por paciente -----------------
# Paciente 1 ya tiene 3 activos (1,2,3) + 1 archivado (4) en el seed.
$resultados += Assert-Succeeds $modulo "regla1_4to_objetivo_activo_ok" $Database `
    "INSERT INTO objetivos_terapeuticos (id_paciente, descripcion, activo) VALUES (1, 'TEST regla1 4to', TRUE);"

$resultados += Assert-Fails $modulo "regla1_5to_objetivo_rechazado" $Database `
    "INSERT INTO objetivos_terapeuticos (id_paciente, descripcion, activo) VALUES (1, 'TEST regla1 5to', TRUE);" `
    "El paciente ya tiene 4 objetivos activos"

# Reactivar un archivado cuando ya hay 4 activos tambien debe rechazarse
$resultados += Assert-Fails $modulo "regla1_reactivar_con_4_activos_rechazado" $Database `
    "UPDATE objetivos_terapeuticos SET activo = TRUE WHERE id_paciente = 1 AND descripcion = 'Vestirse de forma autonoma';" `
    "El paciente ya tiene 4 objetivos activos"

# --- Regla 2: sin evolucion sobre sesion en ausencia -------------------
# Sesion 4 (paciente 1) esta marcada 'ausencia' en el seed.
$resultados += Assert-Fails $modulo "regla2_evolucion_sobre_ausencia_rechazada" $Database `
    "INSERT INTO evoluciones (id_sesion, id_objetivo, valor) VALUES (4, 1, 3);" `
    "la sesion esta marcada como ausencia"

# --- Regla 3: el objetivo evaluado debe ser del paciente de la sesion --
# Sesion 1 es del paciente 1; objetivo 5 es del paciente 2.
$resultados += Assert-Fails $modulo "regla3_objetivo_de_otro_paciente_rechazado" $Database `
    "INSERT INTO evoluciones (id_sesion, id_objetivo, valor) VALUES (1, 5, 3);" `
    "no pertenece al paciente de esta sesion"

# --- Regla 4: sin evolucion sobre objetivo archivado -------------------
# Objetivo 4 (paciente 1) esta archivado en el seed.
$resultados += Assert-Fails $modulo "regla4_evolucion_sobre_archivado_rechazada" $Database `
    "INSERT INTO evoluciones (id_sesion, id_objetivo, valor) VALUES (1, 4, 3);" `
    "sobre un objetivo archivado"

# --- Regla 5: el login del paciente es opcional ------------------------
$sinLogin = Get-ScalarValue $Database "SELECT COUNT(*) FROM pacientes WHERE id_usuario IS NULL;"
$resultados += Assert-True $modulo "regla5_pacientes_sin_login_existen" ([int]$sinLogin -ge 1) `
    "Hay $sinLogin pacientes sin login" "No hay ningun paciente sin login en el seed"

$resultados += Assert-Succeeds $modulo "regla5_alta_paciente_sin_login_ok" $Database `
    "CALL p_alta_paciente('Test','SinLogin','2020-01-01',NULL,'HC-TEST-REGLA5', NULL, @id, @msg); SELECT @id, @msg;"

# --- Regla 6: sin sesiones solapadas del mismo terapeuta ---------------
# Terapeuta 1 tiene sesion 09:00-10:00 el 2026-06-02 (id 1). 09:00-11:00 la toca.
$resultados += Assert-Succeeds $modulo "regla6_horario_sin_solape_ok" $Database `
    "CALL p_registrar_sesion(1, 1, '2026-06-02', '10:00:00', '11:00:00', 'incompleta', NULL, @id, @msg); SELECT @id, @msg;"

$r = Invoke-Sql -Database $Database -Sql `
    "CALL p_registrar_sesion(1, 1, '2026-06-02', '09:30:00', '10:30:00', 'incompleta', NULL, @id, @msg); SELECT @id, @msg;"
$lineasSolapa = $r.StdOut -split "`r?`n" | Where-Object { $_.Trim() -ne "" }
$solapaMsg = $lineasSolapa | Select-Object -Last 1
$resultados += Assert-True $modulo "regla6_horario_solapado_rechazado" `
    ($r.ExitCode -eq 0 -and $solapaMsg -match "se superponen") `
    "Mensaje: $solapaMsg" "No se rechazo el solape o el mensaje cambio: $solapaMsg"

Write-ResultsTable $resultados
return $resultados

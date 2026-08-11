# tests/db/bordes/test_regla19_objetivo_archivado_inmutable.ps1
#
# Regresion de la decision 19 de ESTADO.md: la descripcion de un objetivo
# ARCHIVADO es inmutable (hay evoluciones historicas puntuando contra ese
# texto). La regla vive en trg_objetivos_limite_activos_update, no en el
# endpoint -- exactamente el criterio de C1/C3/A1: una regla que solo se
# aplica en un camino de escritura se elude por cualquier otro.
#
# Estos tests confirman que la regla se cumple por el camino DIRECTO (SQL
# crudo, sin pasar por el backend), que es justamente lo que la ubicacion
# en el trigger promete. Se espera PASS hoy: ya esta implementada.
#
# Uso:
#   .\test_regla19_objetivo_archivado_inmutable.ps1 -Database asisto_test_audit

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

$modulo = "bordes"
$resultados = @()

# Objetivo 4 del seed esta archivado (paciente 1).
$resultados += Assert-Fails $modulo "regla19_update_descripcion_objetivo_archivado_directo" $Database `
    "UPDATE objetivos_terapeuticos SET descripcion = 'Intento de reescritura directa' WHERE id = 4;" `
    "archivado"

# Reactivar Y reescribir en la MISMA sentencia tambien se rechaza: el
# objetivo todavia estaba archivado cuando se evaluo el cambio.
$resultados += Assert-Fails $modulo "regla19_reactivar_y_reescribir_en_la_misma_sentencia" $Database `
    "UPDATE objetivos_terapeuticos SET activo = TRUE, descripcion = 'Reactivado y reescrito a la vez' WHERE id = 4;" `
    "archivado"

# Regresion: mandar la MISMA descripcion que ya tenia un archivado no
# dispara el rechazo (no hay cambio real). No debe fallar.
$resultados += Assert-Succeeds $modulo "regla19_misma_descripcion_sobre_archivado_no_falla" $Database `
    "UPDATE objetivos_terapeuticos SET descripcion = 'Vestirse de forma autonoma' WHERE id = 4;"

# Regresion: la descripcion de un objetivo ACTIVO sigue siendo editable.
$null = Invoke-Sql -Database $Database -Sql `
    "INSERT INTO objetivos_terapeuticos (id_paciente, descripcion, activo) VALUES (3, 'TEST regla19 activo editable', TRUE);"
$idNuevo = [int](Get-ScalarValue $Database `
    "SELECT id FROM objetivos_terapeuticos WHERE id_paciente=3 AND descripcion='TEST regla19 activo editable';")
$resultados += Assert-Succeeds $modulo "regla19_objetivo_activo_sigue_editable" $Database `
    "UPDATE objetivos_terapeuticos SET descripcion = 'TEST regla19 activo editado' WHERE id = $idNuevo;"

Write-ResultsTable $resultados
return $resultados

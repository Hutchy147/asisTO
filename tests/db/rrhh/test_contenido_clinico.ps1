# tests/db/rrhh/test_contenido_clinico.ps1
#
# El CLAUDE.md pone un limite duro: RRHH verifica asistencias, no lee
# contenido clinico (evoluciones, notas de sesion, informes). Este
# modulo confirma que los dos objetos pensados para RRHH
# (p_reporte_sesiones_periodo y v_resumen_sesiones) no devuelven ese
# contenido, ni por columna ni "de colado" en el texto de otra columna.
#
# Lo que este modulo NO puede probar por SQL: hoy no existe ningun
# usuario de MySQL distinto de root, o sea que el limite de RRHH depende
# ENTERAMENTE de que el codigo Flask (que todavia no existe) llame
# siempre a los objetos correctos segun el rol. Eso queda documentado en
# AUDITORIA.md como hallazgo arquitectonico, no como test automatizable.
#
# Uso:
#   .\test_contenido_clinico.ps1 -Database asisto_test_audit

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

$modulo = "rrhh"
$resultados = @()

# --- p_reporte_sesiones_periodo: columnas esperadas --------------------
$rProc = Invoke-Sql -Database $Database -Sql `
    "CALL p_reporte_sesiones_periodo('2026-01-01','2026-12-31', NULL, @msg);"
$columnasProc = ($rProc.StdOut -split "`r?`n" | Select-Object -First 1)
$prohibidasProc = @("notas", "observaciones", "descripcion", "contenido", "valor")
$fugaProc = $null
foreach ($p in $prohibidasProc) {
    if ($columnasProc -match [regex]::Escape($p)) { $fugaProc = $p; break }
}
$resultados += Assert-True $modulo "reporte_sesiones_periodo_sin_columnas_clinicas" (-not $fugaProc) `
    "Columnas: $columnasProc" "La columna '$fugaProc' aparece en p_reporte_sesiones_periodo: $columnasProc"

# Verificacion de contenido, no solo de columnas: que ningun texto de
# notas/observaciones del seed aparezca "de colado" en la salida.
$notasSeedConocidas = @(
    "Buena disposicion. Trabajamos con masa y pinzas de ropa",
    "Se retiro 20 minutos antes por malestar",
    "La familia aviso el mismo dia"
)
$fugaTexto = $null
foreach ($n in $notasSeedConocidas) {
    if ($rProc.StdOut -match [regex]::Escape($n)) { $fugaTexto = $n; break }
}
$resultados += Assert-True $modulo "reporte_sesiones_periodo_sin_texto_de_notas" (-not $fugaTexto) `
    "Ninguna nota de sesion aparece en la salida" "Aparecio una nota de sesion en la salida: '$fugaTexto'"

# --- v_resumen_sesiones: columnas esperadas -----------------------------
$colsResumen = Get-ScalarValue $Database @"
SELECT GROUP_CONCAT(COLUMN_NAME ORDER BY ORDINAL_POSITION SEPARATOR ',')
  FROM information_schema.columns
 WHERE table_schema = '$Database' AND table_name = 'v_resumen_sesiones';
"@
$prohibidasResumen = @("notas", "observaciones", "descripcion", "contenido", "valor")
$fugaResumen = $null
foreach ($p in $prohibidasResumen) {
    if ($colsResumen -match [regex]::Escape($p)) { $fugaResumen = $p; break }
}
$resultados += Assert-True $modulo "v_resumen_sesiones_sin_columnas_clinicas" (-not $fugaResumen) `
    "Columnas: $colsResumen" "La columna '$fugaResumen' aparece en v_resumen_sesiones: $colsResumen"

# --- Informativo: no hay usuarios de MySQL separados por rol -----------
$usuariosMysql = Get-ScalarValue $Database `
    "SELECT COUNT(*) FROM mysql.user WHERE user NOT LIKE 'mysql.%' AND user <> 'root';"
$resultados += New-TestResult $modulo "usuarios_mysql_separados_por_rol" "INFO" `
    "Usuarios de MySQL (fuera de root/sistema): $usuariosMysql. " + `
    "El limite de RRHH hoy depende 100% del codigo Flask, no hay barrera de base de datos. Ver AUDITORIA.md."

Write-ResultsTable $resultados
return $resultados

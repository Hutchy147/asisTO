# tests/db/seed/test_seed_coherencia.ps1
#
# Confirma que seed.sql es coherente con el schema y con las reglas de
# negocio, y que no depende de la suerte del orden de insercion (se
# banca ids explicitos + TRUNCATE, se puede recargar las veces que haga
# falta sobre el mismo schema sin arrancar de cero).
#
# Uso:
#   .\test_seed_coherencia.ps1 -Database asisto_test_audit

param(
    [string]$Database
)

. "$PSScriptRoot\..\lib\TestHelpers.ps1"


# Sin -Database explicito, el nombre sale del rol de la terminal
# (ASISTO_ROL). Con el nombre fijo de antes, dos terminales corriendo
# esto a la vez usaban la misma base y se la destruian entre si.
if (-not $PSBoundParameters.ContainsKey('Database')) {
    $Database = Get-NombreBaseDePrueba -Base "asisto_test_audit" `
        -EjemploExplicito '.\test_seed_coherencia.ps1 -Database mi_base'
}

$modulo = "seed"
$resultados = @()

# --- Conteos documentados en ESTADO.md ----------------------------------
$conteos = Get-ScalarValue $Database @"
SELECT CONCAT_WS(',',
  (SELECT COUNT(*) FROM usuarios),
  (SELECT COUNT(*) FROM pacientes),
  (SELECT COUNT(*) FROM pacientes WHERE id_usuario IS NULL),
  (SELECT COUNT(*) FROM objetivos_terapeuticos),
  (SELECT COUNT(*) FROM objetivos_terapeuticos WHERE activo = TRUE),
  (SELECT COUNT(*) FROM sesiones),
  (SELECT COUNT(*) FROM evoluciones)
);
"@
$esperado = "6,3,2,7,6,10,11"
$resultados += Assert-True $modulo "conteos_iniciales_coinciden_con_estado_md" ($conteos -eq $esperado) `
    "Conteos: $conteos" "Conteos no coinciden. Esperado $esperado, obtenido $conteos"

# --- Ningun paciente arranca con mas de 4 objetivos activos -------------
$exceso = Get-ScalarValue $Database @"
SELECT COUNT(*) FROM (
  SELECT id_paciente, COUNT(*) AS activos
    FROM objetivos_terapeuticos
   WHERE activo = TRUE
   GROUP BY id_paciente
  HAVING COUNT(*) > 4
) t;
"@
$resultados += Assert-True $modulo "seed_ningun_paciente_supera_4_activos" ([int]$exceso -eq 0) `
    "Ningun paciente supera el limite" "$exceso paciente(s) del seed ya arrancan con mas de 4 objetivos activos"

# --- Ninguna sesion en ausencia tiene evolucion cargada -----------------
$ausenciasConEvolucion = Get-ScalarValue $Database @"
SELECT COUNT(*) FROM sesiones s
  JOIN evoluciones e ON e.id_sesion = s.id
 WHERE s.estado = 'ausencia';
"@
$resultados += Assert-True $modulo "seed_ausencias_sin_evolucion" ([int]$ausenciasConEvolucion -eq 0) `
    "Ninguna ausencia tiene evolucion" "$ausenciasConEvolucion sesion(es) de ausencia tienen evolucion cargada en el seed"

# --- Toda evolucion respeta que el objetivo sea del paciente de la sesion,
#     y que el objetivo este activo (coherencia interna del seed con las
#     reglas 3 y 4, antes de que cualquier UPDATE posterior las rompa) ---
$inconsistencias = Get-ScalarValue $Database @"
SELECT COUNT(*) FROM evoluciones e
  JOIN sesiones s ON s.id = e.id_sesion
  JOIN objetivos_terapeuticos o ON o.id = e.id_objetivo
 WHERE o.id_paciente <> s.id_paciente OR o.activo = FALSE;
"@
$resultados += Assert-True $modulo "seed_evoluciones_consistentes_con_reglas_3_y_4" ([int]$inconsistencias -eq 0) `
    "Todas las evoluciones son consistentes" "$inconsistencias evolucion(es) del seed ya violan la regla 3 o 4 desde el arranque"

# --- El seed se puede recargar (TRUNCATE + reinsert) sin depender del
#     AUTO_INCREMENT ni del orden de una corrida anterior ----------------
$repoRoot = (Resolve-Path "$PSScriptRoot\..\..\..").Path
$seedPath = Join-Path $repoRoot "backend\database\seed.sql"
$seedSql = (Get-Content $seedPath -Raw) -replace '(?m)^USE asisto;', "USE $Database;"
$rReload1 = Invoke-Sql -Database $Database -Sql $seedSql
$rReload2 = Invoke-Sql -Database $Database -Sql $seedSql
$conteosTrasRecarga = Get-ScalarValue $Database @"
SELECT CONCAT_WS(',',
  (SELECT COUNT(*) FROM usuarios),
  (SELECT COUNT(*) FROM pacientes),
  (SELECT COUNT(*) FROM objetivos_terapeuticos),
  (SELECT COUNT(*) FROM sesiones),
  (SELECT COUNT(*) FROM evoluciones)
);
"@
$resultados += Assert-True $modulo "seed_recargable_dos_veces_seguidas_sin_error" `
    ($rReload1.ExitCode -eq 0 -and $rReload2.ExitCode -eq 0 -and $conteosTrasRecarga -eq "6,3,7,10,11") `
    "Conteos estables tras recargar dos veces: $conteosTrasRecarga" `
    "Recargar el seed dos veces seguidas fallo o cambio los conteos: $conteosTrasRecarga. Error1: $($rReload1.StdErr.Trim()) Error2: $($rReload2.StdErr.Trim())"

# --- Nota informativa: la asignacion CERRADA del seed (terapeuta 2 con el
#     paciente 1, 2026-03-02 a 2026-05-04) representa el caso "el paciente
#     paso de una terapeuta a otra", pero ese periodo no tiene ninguna
#     sesion cargada del terapeuta 2 con ese paciente. No es un error
#     tecnico, pero vale dejarlo anotado para quien lea el seed como demo.
#
#     El texto anterior de esta nota hablaba de `duplas_terapeuticas`.
#     Esa tabla se elimino en la migracion del 2026-08-07 (decision 17 de
#     ESTADO.md): modelaba dos terapeutas sobre un paciente, que es el caso
#     INTERDISCIPLINARIO, no una dupla. La consulta no cambio -- siempre
#     fue contra `sesiones` -- pero nombraba una tabla que ya no existe.
#     -------------------------------------------------------------------
$sesionesTerapeuta2ConPaciente1 = Get-ScalarValue $Database `
    "SELECT COUNT(*) FROM sesiones WHERE id_terapeuta = 2 AND id_paciente = 1;"
$resultados += New-TestResult $modulo "nota_asignacion_cerrada_sin_sesiones_de_ese_periodo" "INFO" `
    "Sesiones del terapeuta 2 con el paciente 1: $sesionesTerapeuta2ConPaciente1 (la asignacion cerrada existe en asignaciones pero ese periodo no se refleja en sesiones)"

# --- Nota informativa: una dupla, con la definicion correcta (UNA
#     terapeuta con DOS niños), son dos sesiones que comparten
#     sesiones.id_dupla. Hoy nadie escribe esa columna: es preparacion de
#     la Entrega 4 y en el seed esta NULL en todas las filas. Se mide para
#     que el dia que el seed siembre una dupla, el numero cambie y se vea.
$sesionesConDupla = Get-ScalarValue $Database `
    "SELECT COUNT(*) FROM sesiones WHERE id_dupla IS NOT NULL;"
$resultados += New-TestResult $modulo "nota_ninguna_sesion_del_seed_tiene_id_dupla" "INFO" `
    "Sesiones con id_dupla no nulo: $sesionesConDupla (la columna existe desde el 2026-08-07 y todavia no la escribe nadie)"

Write-ResultsTable $resultados
return $resultados

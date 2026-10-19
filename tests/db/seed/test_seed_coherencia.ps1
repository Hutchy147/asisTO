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
# Actualizado el 2026-08-13, despues de que el seed sumara un paciente dado de
# baja con historia completa (commit d7a0f25). Era "6,3,2,7,6,10,11".
# Los conteos se midieron sobre una base recien construida, no sobre una donde
# ya habia corrido otro modulo: con `run_all.ps1` cada modulo tiene su propia
# base, pero corriendo dos modulos a mano contra la misma base estos numeros
# dan cualquier cosa.
$esperado = "7,4,3,9,6,13,15"
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

# --- Toda evolucion tiene su objetivo y su sesion en el MISMO paciente
#     (regla 3). Esta si es una invariante del estado final: mover a otro
#     paciente un objetivo que ya tiene evoluciones tambien esta prohibido,
#     asi que el estado no se puede alcanzar por ningun camino.
#
#     LA CONDICION `o.activo = FALSE` SE SACO DE ESTA CONSULTA el 2026-08-13.
#     Estaba mal desde el principio y el seed nuevo la puso en evidencia: una
#     evolucion sobre un objetivo ARCHIVADO no viola la regla 4. La regla 4
#     prohibe CARGAR una evolucion nueva sobre un objetivo archivado, no que
#     exista una evolucion vieja debajo de uno que se archivo despues.
#     Archivar un objetivo con evoluciones esta permitido —verificado— y es
#     exactamente lo que hace la baja de paciente: congela el texto contra el
#     que se puntuaron esas evoluciones. Ver AUDITORIA.md, 2026-08-13.
$inconsistencias = Get-ScalarValue $Database @"
SELECT COUNT(*) FROM evoluciones e
  JOIN sesiones s ON s.id = e.id_sesion
  JOIN objetivos_terapeuticos o ON o.id = e.id_objetivo
 WHERE o.id_paciente <> s.id_paciente;
"@
$resultados += Assert-True $modulo "seed_evoluciones_consistentes_con_la_regla_3" ([int]$inconsistencias -eq 0) `
    "Toda evolucion tiene objetivo y sesion del mismo paciente" `
    "$inconsistencias evolucion(es) del seed tienen el objetivo y la sesion en pacientes distintos (regla 3) desde el arranque"

# --- Las evoluciones que quedaron bajo un objetivo archivado NO son un error:
#     son el rastro del paciente dado de baja que el seed siembra desde el
#     commit d7a0f25. Se cuentan para que el dia que ese numero cambie sin que
#     nadie haya tocado el seed, se vea. La regla de verdad —no se pueden
#     cargar evoluciones NUEVAS sobre un objetivo archivado— la prueban
#     regla4_evolucion_sobre_archivado_rechazada (reglas_negocio) y
#     evolucion_update_hacia_objetivo_archivado (bordes), en los dos caminos
#     de escritura.
$bajoArchivado = Get-ScalarValue $Database @"
SELECT COUNT(*) FROM evoluciones e
  JOIN objetivos_terapeuticos o ON o.id = e.id_objetivo
 WHERE o.activo = FALSE;
"@
$resultados += New-TestResult $modulo "nota_evoluciones_bajo_objetivo_archivado" "INFO" `
    "Evoluciones que quedaron bajo un objetivo archivado: $bajoArchivado (legitimo: son las del paciente dado de baja, cuyos objetivos archivo la baja despues de cargarlas)"

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
    ($rReload1.ExitCode -eq 0 -and $rReload2.ExitCode -eq 0 -and $conteosTrasRecarga -eq "7,4,9,13,15") `
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

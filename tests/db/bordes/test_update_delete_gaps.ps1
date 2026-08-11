# tests/db/bordes/test_update_delete_gaps.ps1
#
# Casos donde una regla de negocio se valida en el INSERT pero no en el
# UPDATE ni en el DELETE, o donde la unica validacion vive en un
# procedimiento y no en la tabla. Varios de estos tests codifican el
# COMPORTAMIENTO DESEADO (lo que deberia pasar), no el actual: hoy
# reportan FAIL a proposito, documentando un hallazgo de AUDITORIA.md.
# Cuando se aplique la correccion correspondiente, deberian pasar a PASS
# sin tocar el test.
#
# Ver AUDITORIA.md para el detalle de cada hallazgo. Resumen de que test
# corresponde a que hallazgo esta al final de este archivo.
#
# Uso:
#   .\test_update_delete_gaps.ps1 -Database asisto_test_audit

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

# ------------------------------------------------------------------
# HALLAZGO: no hay trigger BEFORE UPDATE en evoluciones. Un UPDATE de
# id_objetivo puede dejar la evolucion apuntando a un objetivo archivado
# o de otro paciente. (Problema conocido #1 de ESTADO.md, decidido
# cerrar; este test confirma el hueco y sirve de regresion post-fix.)
# ------------------------------------------------------------------
$resultados += Assert-Fails $modulo "evolucion_update_hacia_objetivo_archivado" $Database `
    "UPDATE evoluciones SET id_objetivo = 4 WHERE id = 5;" `
    "archivado"

$resultados += Assert-Fails $modulo "evolucion_update_hacia_objetivo_de_otro_paciente" $Database `
    "UPDATE evoluciones SET id_objetivo = 1 WHERE id = 5;" `
    "no pertenece al paciente"

# ------------------------------------------------------------------
# HALLAZGO: mover un objetivo a otro paciente via UPDATE id_paciente dura
# solo cuenta el limite de 4 activos del paciente destino; no revisa que
# las evoluciones YA CARGADAS sobre ese objetivo sigan perteneciendo al
# paciente correcto. Deja evoluciones cuyo objetivo.id_paciente no
# coincide con sesion.id_paciente, violando la regla 3 retroactivamente.
# ------------------------------------------------------------------
$resultados += Assert-Fails $modulo "objetivo_update_id_paciente_con_evoluciones_previas" $Database `
    "UPDATE objetivos_terapeuticos SET id_paciente = 2 WHERE id = 1;" `
    "tiene evoluciones registradas"

# ------------------------------------------------------------------
# HALLAZGO: no hay ningun trigger en sesiones. Marcar una sesion con
# evolucion cargada como 'ausencia' via UPDATE no se revisa contra la
# regla 2, y deja una evolucion sobre una sesion en ausencia.
# ------------------------------------------------------------------
$resultados += Assert-Fails $modulo "sesion_update_estado_a_ausencia_con_evolucion_cargada" $Database `
    "UPDATE sesiones SET estado = 'ausencia' WHERE id = 9;" `
    "tiene evoluciones cargadas"

# ------------------------------------------------------------------
# HALLAZGO: la regla 6 (sin solape del terapeuta) vive SOLO en
# p_registrar_sesion. No hay trigger que la haga cumplir a nivel de
# tabla, asi que cualquier INSERT o UPDATE directo sobre sesiones la
# elude sin ningun error, sin necesidad de concurrencia.
# ------------------------------------------------------------------
# Terapeuta 1 ya tiene la sesion 1 (2026-06-02 09:00-10:00, seed).
$resultados += Assert-Fails $modulo "sesion_insert_directo_bypassa_solape" $Database `
    "INSERT INTO sesiones (id_terapeuta, id_paciente, fecha, hora_inicio, hora_fin, estado) VALUES (1, 3, '2026-06-02', '09:30:00', '10:15:00', 'incompleta');" `
    "se superponen"

$resultados += Assert-Fails $modulo "sesion_update_directo_bypassa_solape" $Database `
    "UPDATE sesiones SET fecha = '2026-06-02', hora_inicio = '09:30:00', hora_fin = '10:15:00' WHERE id = 2;" `
    "se superponen"

# ------------------------------------------------------------------
# Regresion: DELETE de un objetivo/sesion con evoluciones asociadas debe
# seguir bloqueado por las FK con ON DELETE RESTRICT (esto ya funciona
# bien: sirve para detectar si una correccion futura lo rompe).
# ------------------------------------------------------------------
$resultados += Assert-Fails $modulo "delete_objetivo_con_evoluciones_bloqueado" $Database `
    "DELETE FROM objetivos_terapeuticos WHERE id = 7;" `
    "foreign key constraint fails"

$resultados += Assert-Fails $modulo "delete_sesion_con_evoluciones_bloqueado" $Database `
    "DELETE FROM sesiones WHERE id = 8;" `
    "foreign key constraint fails"

# ------------------------------------------------------------------
# Regresion: el CHECK de evoluciones.valor tambien corre en UPDATE (no
# solo en INSERT). Esto YA funciona bien en MySQL 8.0.16+.
# ------------------------------------------------------------------
$resultados += Assert-Fails $modulo "evolucion_update_valor_fuera_de_rango_bloqueado" $Database `
    "UPDATE evoluciones SET valor = 9 WHERE id = 1;" `
    "chk_evoluciones_valor"

# ------------------------------------------------------------------
# Regresion: archivar y recrear un objetivo DOS ciclos completos
# seguidos (el seed solo prueba un ciclo). Ya confirmado que funciona.
# ------------------------------------------------------------------
$null = Invoke-Sql -Database $Database -Sql `
    "INSERT INTO objetivos_terapeuticos (id_paciente, descripcion, activo) VALUES (3, 'TEST ciclo repetido', TRUE);"
$null = Invoke-Sql -Database $Database -Sql `
    "UPDATE objetivos_terapeuticos SET activo = FALSE WHERE id_paciente = 3 AND descripcion = 'TEST ciclo repetido';"
$resultados += Assert-Succeeds $modulo "objetivo_recrear_ciclo_1" $Database `
    "INSERT INTO objetivos_terapeuticos (id_paciente, descripcion, activo) VALUES (3, 'TEST ciclo repetido', TRUE);"
$null = Invoke-Sql -Database $Database -Sql `
    "UPDATE objetivos_terapeuticos SET activo = FALSE WHERE id_paciente = 3 AND descripcion = 'TEST ciclo repetido' AND activo = TRUE;"
$resultados += Assert-Succeeds $modulo "objetivo_recrear_ciclo_2" $Database `
    "INSERT INTO objetivos_terapeuticos (id_paciente, descripcion, activo) VALUES (3, 'TEST ciclo repetido', TRUE);"

$activosFinal = Get-ScalarValue $Database `
    "SELECT COUNT(*) FROM objetivos_terapeuticos WHERE id_paciente = 3 AND descripcion = 'TEST ciclo repetido' AND activo = TRUE;"
$resultados += Assert-True $modulo "objetivo_recrear_ciclo_2_una_sola_fila_activa" ([int]$activosFinal -eq 1) `
    "Hay exactamente 1 fila activa con esa descripcion" "Hay $activosFinal filas activas, deberia haber 1"

Write-ResultsTable $resultados
return $resultados

# ------------------------------------------------------------------
# Mapa test -> hallazgo en AUDITORIA.md:
#   evolucion_update_hacia_objetivo_archivado              -> Critico #1
#   evolucion_update_hacia_objetivo_de_otro_paciente        -> Critico #1
#   objetivo_update_id_paciente_con_evoluciones_previas     -> Alto #1
#   sesion_update_estado_a_ausencia_con_evolucion_cargada   -> Alto #2
#   sesion_insert_directo_bypassa_solape                    -> Critico #2
#   sesion_update_directo_bypassa_solape                    -> Critico #2
# ------------------------------------------------------------------

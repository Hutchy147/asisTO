# tests/db/sesiones/test_sesiones_paciente_de_baja.ps1
#
# La regla de baja aplicada en los DOS triggers de sesiones (construccion,
# commit 72ce570), fusionada dentro de los triggers de solape.
#
# POR QUE ESTE ARCHIVO EXISTE. La regla ya estaba en p_registrar_sesion y
# cubierta desde ahi. Lo que agrega el commit es aplicarla tambien por las dos
# puertas que NO pasan por el procedimiento: un INSERT directo y un UPDATE
# directo sobre `sesiones`. Construccion verifico ocho casos a mano contra una
# base descartable; a mano no queda nada corriendo. Esto los deja corriendo.
#
# LAS TRES PUERTAS DE LA MISMA REGLA:
#   1. p_registrar_sesion            -> devuelve el texto por p_mensaje
#   2. trg_sesiones_solape_insert    -> SIGNAL 45000, errno 1644
#   3. trg_sesiones_solape_update    -> SIGNAL 45000, errno 1644
# El mensaje tiene que ser el MISMO en las tres. Se compara caracter por
# caracter mas abajo: es la misma clase de verificacion que se hizo con los
# triggers de asignaciones, y sirve para lo mismo -- que una de las tres no
# quede desactualizada respecto de las otras sin que nadie se entere.
#
# EL CASO QUE MAS IMPORTA DEL TRIGGER DE UPDATE es el que NO toca el horario:
# mover una sesion a otro paciente que esta dado de baja. El chequeo de baja
# va FUERA del `IF cambio el horario` justamente para eso, asi que esa es la
# ruta que lo ejercita. Si alguien lo moviera adentro del IF, todos los demas
# casos de este archivo seguirian pasando y solo caeria ese.
#
# Uso:
#   .\test_sesiones_paciente_de_baja.ps1 -Database asisto_test_audit2_sesbaja

param(
    [string]$Database
)

. "$PSScriptRoot\..\lib\TestHelpers.ps1"

if (-not $PSBoundParameters.ContainsKey('Database')) {
    $Database = Get-NombreBaseDePrueba -Base "asisto_test_audit" `
        -EjemploExplicito '.\test_sesiones_paciente_de_baja.ps1 -Database mi_base'
}

$modulo = "sesiones_baja"
$resultados = @()

# Limpieza previa: el modulo crea pacientes con nro_historia fijo, y
# `run_all.ps1` le da una base recien construida, pero correrlo dos veces a
# mano contra la misma base chocaba contra la UNIQUE de nro_historia y el
# alta devolvia NULL. El sintoma era feo -- "La baja de 0 no salio" -- y no
# tenia nada que ver con lo que el archivo prueba. Se limpia en el orden de
# las FK: evoluciones, sesiones, objetivos, asignaciones, pacientes.
$null = Invoke-Sql -Database $Database -Sql @"
DELETE e FROM evoluciones e JOIN sesiones s ON s.id = e.id_sesion
  JOIN pacientes p ON p.id = s.id_paciente WHERE p.nro_historia LIKE 'HC-SESBAJA-%';
DELETE s FROM sesiones s JOIN pacientes p ON p.id = s.id_paciente
 WHERE p.nro_historia LIKE 'HC-SESBAJA-%';
DELETE o FROM objetivos_terapeuticos o JOIN pacientes p ON p.id = o.id_paciente
 WHERE p.nro_historia LIKE 'HC-SESBAJA-%';
DELETE a FROM asignaciones a JOIN pacientes p ON p.id = a.id_paciente
 WHERE p.nro_historia LIKE 'HC-SESBAJA-%';
DELETE FROM pacientes WHERE nro_historia LIKE 'HC-SESBAJA-%';
"@

$MENSAJE_ESPERADO = 'El paciente esta dado de baja: solo se pueden cargar sesiones hasta el dia de la baja'

function Nuevo-Paciente {
    param([string]$Sufijo)
    $r = Invoke-Sql -Database $Database -Sql @"
CALL p_alta_paciente('Sesion','$Sufijo','2015-04-04',NULL,'HC-SESBAJA-$Sufijo',NULL,@id,@msg);
SELECT @id;
"@
    if ($r.ExitCode -ne 0) { throw "No se pudo crear el paciente $Sufijo : $($r.StdErr)" }
    return [int](($r.StdOut -split "`r?`n" | Where-Object { $_.Trim() -ne "" } | Select-Object -Last 1).Trim())
}

function Dar-Baja {
    param([int]$IdPaciente)
    $r = Invoke-Sql -Database $Database -Sql @"
CALL p_baja_paciente($IdPaciente, @o, @a, @m);
SELECT @m;
"@
    $ultima = ($r.StdOut -split "`r?`n" | Where-Object { $_.Trim() -ne "" } | Select-Object -Last 1).Trim()
    if ($ultima -notmatch "correctamente") { throw "La baja de $IdPaciente no salio: $ultima" }
    return (Get-ScalarValue $Database "SELECT fecha_baja FROM pacientes WHERE id=$IdPaciente;")
}

# Insert directo con hora distinta por caso: dos sesiones del MISMO terapeuta
# en el mismo horario chocarian con la regla 6 y el rechazo vendria del
# trigger equivocado. Cada caso usa su propia hora.
function Insertar-Sesion {
    param([int]$IdPaciente, [string]$Fecha, [string]$Hora, [string]$Notas = 'SESBAJA')
    return Invoke-Sql -Database $Database -Sql @"
INSERT INTO sesiones (id_terapeuta, id_paciente, fecha, hora_inicio, hora_fin, estado, notas)
VALUES (1, $IdPaciente, $Fecha, '$Hora', ADDTIME('$Hora','00:45:00'), 'completa', '$Notas');
"@
}

# =======================================================================
# PUERTA 2 — INSERT directo (trg_sesiones_solape_insert)
# =======================================================================

$pacBaja = Nuevo-Paciente "INS"
$fechaBaja = Dar-Baja $pacBaja

$rPost = Insertar-Sesion $pacBaja "DATE_ADD('$fechaBaja', INTERVAL 1 DAY)" '08:00:00'
$resultados += Assert-True $modulo "insert_directo_posterior_a_la_baja_es_rechazado" `
    ($rPost.ExitCode -ne 0 -and $rPost.StdErr -match [regex]::Escape($MENSAJE_ESPERADO)) `
    "Rechazado por el trigger con el mensaje de la regla" `
    "El INSERT directo posterior a la baja no fue rechazado como corresponde: exit=$($rPost.ExitCode) err=$($rPost.StdErr.Trim())"

$rExacto = Insertar-Sesion $pacBaja "'$fechaBaja'" '09:00:00'
$resultados += Assert-True $modulo "insert_directo_el_dia_exacto_de_la_baja_se_acepta" `
    ($rExacto.ExitCode -eq 0) `
    "El dia de la baja entra: el corte es la fecha posterior, no el estado del paciente" `
    "Se rechazo una sesion del dia exacto de la baja, que tiene que entrar: $($rExacto.StdErr.Trim())"

$rPrevio = Insertar-Sesion $pacBaja "DATE_SUB('$fechaBaja', INTERVAL 10 DAY)" '10:00:00'
$resultados += Assert-True $modulo "insert_directo_anterior_a_la_baja_se_acepta" `
    ($rPrevio.ExitCode -eq 0) `
    "La carga retroactiva entra por la puerta del trigger igual que por el procedimiento" `
    "Se rechazo una sesion anterior a la baja: $($rPrevio.StdErr.Trim())"

$pacActivo = Nuevo-Paciente "ACT"
$rActivo = Insertar-Sesion $pacActivo "DATE_ADD(CURRENT_DATE, INTERVAL 30 DAY)" '11:00:00'
$resultados += Assert-True $modulo "insert_directo_sobre_paciente_activo_se_acepta" `
    ($rActivo.ExitCode -eq 0) `
    "Control de no regresion: el chequeo nuevo no toca al paciente activo" `
    "El chequeo nuevo rompio el INSERT normal sobre un paciente activo: $($rActivo.StdErr.Trim())"

$sesionesTrasRechazo = [int](Get-ScalarValue $Database "SELECT COUNT(*) FROM sesiones WHERE id_paciente=$pacBaja;")
$resultados += Assert-True $modulo "el_insert_rechazado_no_dejo_fila" ($sesionesTrasRechazo -eq 2) `
    "Quedaron las 2 sesiones aceptadas y ninguna de la rechazada" `
    "Quedaron $sesionesTrasRechazo sesiones y tenian que quedar 2: el rechazo dejo rastro"

# =======================================================================
# PUERTA 3 — UPDATE directo (trg_sesiones_solape_update)
# =======================================================================

# Una sesion valida del paciente de baja (el dia exacto), para moverla.
$idSesionMovible = [int](Get-ScalarValue $Database @"
SELECT id FROM sesiones WHERE id_paciente=$pacBaja AND fecha='$fechaBaja' LIMIT 1;
"@)

$rMoverFecha = Invoke-Sql -Database $Database -Sql @"
UPDATE sesiones SET fecha = DATE_ADD('$fechaBaja', INTERVAL 1 DAY) WHERE id = $idSesionMovible;
"@
$resultados += Assert-True $modulo "update_que_mueve_la_fecha_despues_de_la_baja_es_rechazado" `
    ($rMoverFecha.ExitCode -ne 0 -and $rMoverFecha.StdErr -match [regex]::Escape($MENSAJE_ESPERADO)) `
    "Rechazado: mover la sesion a despues de la baja es lo mismo que crearla ahi" `
    "El UPDATE que mueve la fecha a despues de la baja no fue rechazado: exit=$($rMoverFecha.ExitCode) err=$($rMoverFecha.StdErr.Trim())"

$rMoverDentro = Invoke-Sql -Database $Database -Sql @"
UPDATE sesiones SET fecha = DATE_SUB('$fechaBaja', INTERVAL 3 DAY), hora_inicio='09:30:00', hora_fin='10:15:00'
 WHERE id = $idSesionMovible;
"@
$resultados += Assert-True $modulo "update_que_mueve_la_fecha_dentro_del_periodo_valido_se_acepta" `
    ($rMoverDentro.ExitCode -eq 0) `
    "Mover la sesion a una fecha anterior a la baja sigue permitido" `
    "Se rechazo un UPDATE hacia una fecha valida: $($rMoverDentro.StdErr.Trim())"

# --- EL CASO QUE IMPORTA: cambiar de paciente SIN tocar el horario ------
#
# Esta es la unica ruta que ejercita el chequeo fuera del `IF cambio el
# horario`. La sesion de origen es de un paciente ACTIVO y se la manda a uno
# de baja, con fecha posterior a esa baja y sin tocar fecha ni hora.
$idSesionDelActivo = [int](Get-ScalarValue $Database @"
SELECT id FROM sesiones WHERE id_paciente=$pacActivo LIMIT 1;
"@)
$rMoverPaciente = Invoke-Sql -Database $Database -Sql @"
UPDATE sesiones SET id_paciente = $pacBaja WHERE id = $idSesionDelActivo;
"@
$resultados += Assert-True $modulo "update_mueve_la_sesion_a_un_paciente_de_baja_sin_tocar_horario_es_rechazado" `
    ($rMoverPaciente.ExitCode -ne 0 -and $rMoverPaciente.StdErr -match [regex]::Escape($MENSAJE_ESPERADO)) `
    "Rechazado sin haber tocado fecha ni hora: el chequeo corre fuera del IF del horario" `
    "ACEPTADO: se movio una sesion a un paciente dado de baja sin tocar el horario. Si el chequeo estuviera adentro del IF del horario este es el unico caso del archivo que lo detecta. exit=$($rMoverPaciente.ExitCode) err=$($rMoverPaciente.StdErr.Trim())"

$duenoTrasIntento = [int](Get-ScalarValue $Database "SELECT id_paciente FROM sesiones WHERE id=$idSesionDelActivo;")
$resultados += Assert-True $modulo "el_update_rechazado_no_cambio_el_dueno" ($duenoTrasIntento -eq $pacActivo) `
    "La sesion sigue siendo del paciente activo" `
    "La sesion quedo apuntando al paciente $duenoTrasIntento y tenia que seguir en $pacActivo"

# Al reves: mover una sesion DESDE un paciente de baja hacia uno activo. El
# chequeo mira NEW.id_paciente, o sea el destino, asi que tiene que entrar.
$rMoverAActivo = Invoke-Sql -Database $Database -Sql @"
UPDATE sesiones SET id_paciente = $pacActivo, hora_inicio='16:00:00', hora_fin='16:45:00'
 WHERE id = $idSesionMovible;
"@
$resultados += Assert-True $modulo "update_mueve_la_sesion_hacia_un_paciente_activo_se_acepta" `
    ($rMoverAActivo.ExitCode -eq 0) `
    "El chequeo mira el paciente DESTINO: mover hacia uno activo esta permitido" `
    "Se rechazo mover una sesion hacia un paciente activo: $($rMoverAActivo.StdErr.Trim())"

$rUpdateActivo = Invoke-Sql -Database $Database -Sql @"
UPDATE sesiones SET hora_inicio='17:00:00', hora_fin='17:45:00' WHERE id = $idSesionDelActivo;
"@
$resultados += Assert-True $modulo "update_de_horario_sobre_paciente_activo_se_acepta" `
    ($rUpdateActivo.ExitCode -eq 0) `
    "Control de no regresion: el chequeo nuevo no toca el UPDATE normal" `
    "El chequeo nuevo rompio un UPDATE de horario sobre un paciente activo: $($rUpdateActivo.StdErr.Trim())"

# =======================================================================
# LAS TRES PUERTAS DICEN LO MISMO
#
# Se comparan los textos crudos, no "contiene": si una de las tres se
# reescribe a medias, la interfaz muestra dos mensajes distintos para la
# misma regla y el traductor de errores del backend puede dejar de
# reconocer uno.
# =======================================================================

$pacMensaje = Nuevo-Paciente "MSG"
$fechaBajaMsg = Dar-Baja $pacMensaje
$fechaPosterior = "DATE_ADD('$fechaBajaMsg', INTERVAL 5 DAY)"

$rProc = Invoke-Sql -Database $Database -Sql @"
CALL p_registrar_sesion(1, $pacMensaje, $fechaPosterior, '18:00:00', '18:45:00', 'completa', NULL, @id, @msg);
SELECT @msg;
"@
$mensajeProc = ($rProc.StdOut -split "`r?`n" | Where-Object { $_.Trim() -ne "" } | Select-Object -Last 1).Trim()

$rIns = Insertar-Sesion $pacMensaje $fechaPosterior '19:00:00'
$mensajeInsert = if ($rIns.StdErr -match 'ERROR \d+ \(\d+\)(?: at line \d+)?: (.+)') { $Matches[1].Trim() } else { "(no se pudo extraer: $($rIns.StdErr.Trim()))" }

# La sesion que se mueve tiene que tener fecha POSTERIOR a la baja del
# destino, si no el UPDATE es legitimo y no hay mensaje que comparar. La
# primera version tomaba "la primera sesion del paciente activo" y agarraba
# una con fecha vieja: el UPDATE entraba, el errno quedaba vacio y el test
# fallaba por su propio fixture, no por el codigo.
$null = Insertar-Sesion $pacActivo "DATE_ADD('$fechaBajaMsg', INTERVAL 9 DAY)" '21:00:00' 'SESBAJA-MSG'
$idParaMover = [int](Get-ScalarValue $Database @"
SELECT id FROM sesiones WHERE id_paciente=$pacActivo AND notas='SESBAJA-MSG' LIMIT 1;
"@)
$rUpd = Invoke-Sql -Database $Database -Sql @"
UPDATE sesiones SET id_paciente = $pacMensaje WHERE id = $idParaMover;
"@
$mensajeUpdate = if ($rUpd.StdErr -match 'ERROR \d+ \(\d+\)(?: at line \d+)?: (.+)') { $Matches[1].Trim() } else { "(no se pudo extraer: $($rUpd.StdErr.Trim()))" }

$resultados += Assert-True $modulo "mensaje_identico_en_las_tres_puertas" `
    ($mensajeProc -ceq $MENSAJE_ESPERADO -and $mensajeInsert -ceq $MENSAJE_ESPERADO -and $mensajeUpdate -ceq $MENSAJE_ESPERADO) `
    "Las tres puertas devuelven exactamente el mismo texto" `
    "Los mensajes difieren.`n  procedimiento: '$mensajeProc'`n  trigger INSERT: '$mensajeInsert'`n  trigger UPDATE: '$mensajeUpdate'`n  esperado: '$MENSAJE_ESPERADO'"

# El errno importa: es lo que lee el traductor de errores del backend. Los
# dos triggers tienen que dar 1644 (SIGNAL SQLSTATE 45000), no un error
# nativo de constraint.
$errnoInsert = if ($rIns.StdErr -match 'ERROR (\d+)') { $Matches[1] } else { '(ninguno)' }
$errnoUpdate = if ($rUpd.StdErr -match 'ERROR (\d+)') { $Matches[1] } else { '(ninguno)' }
$resultados += Assert-True $modulo "errno_1644_en_las_dos_puertas_de_trigger" `
    ($errnoInsert -eq '1644' -and $errnoUpdate -eq '1644') `
    "Las dos puertas de trigger rechazan con 1644" `
    "Errnos inesperados: INSERT=$errnoInsert UPDATE=$errnoUpdate (se esperaba 1644 en las dos)"

# =======================================================================
# EL BORDE QUE NO ESTABA EN LA LISTA: la sesion legitima que queda
# congelada
#
# Una sesion AGENDADA A FUTURO mientras el paciente estaba activo es
# legitima: se registro cuando correspondia. Despues llega la baja. Esa fila
# ahora tiene fecha > fecha_baja, y como el chequeo del trigger de UPDATE
# corre SIEMPRE -- no solo cuando cambia el horario o el paciente -- deja de
# poder tocarse por ningun motivo: ni marcarla como ausencia, ni cargarle una
# nota.
#
# Se afirma en la direccion de lo que parece razonable (poder cerrarla), asi
# que si hoy falla es un hallazgo, no un error del test. Ver AUDITORIA.md.
# =======================================================================

$pacFutura = Nuevo-Paciente "FUT"
$rAgenda = Invoke-Sql -Database $Database -Sql @"
CALL p_registrar_sesion(1, $pacFutura, DATE_ADD(CURRENT_DATE, INTERVAL 20 DAY),
                        '20:00:00', '20:45:00', 'incompleta', NULL, @id, @msg);
SELECT IFNULL(@id,'NULL'), @msg;
"@
$idFutura = [int](Get-ScalarValue $Database @"
SELECT id FROM sesiones WHERE id_paciente=$pacFutura ORDER BY id DESC LIMIT 1;
"@)
$null = Dar-Baja $pacFutura

$rCerrar = Invoke-Sql -Database $Database -Sql @"
UPDATE sesiones SET estado = 'ausencia' WHERE id = $idFutura;
"@
$resultados += Assert-True $modulo "una_sesion_futura_legitima_se_puede_cerrar_tras_la_baja" `
    ($rCerrar.ExitCode -eq 0) `
    "La sesion agendada antes de la baja se puede marcar como ausencia" `
    "CONGELADA: la sesion se agendo cuando el paciente estaba activo (legitima) y tras la baja no se le puede cambiar ni el estado, porque el chequeo del trigger de UPDATE corre aunque no se toquen ni la fecha ni el paciente. Queda una fila futura de un paciente de baja que nadie puede cerrar. err=$($rCerrar.StdErr.Trim())"

Write-ResultsTable $resultados
return $resultados

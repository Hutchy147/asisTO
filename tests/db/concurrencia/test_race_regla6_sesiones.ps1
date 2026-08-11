# tests/db/concurrencia/test_race_regla6_sesiones.ps1
#
# HALLAZGO CRITICO: p_registrar_sesion tiene la misma estructura que el
# trigger de la regla 1: cuenta los solapes y despues inserta, dentro de
# una transaccion pero sin ningun lock explicito. Es vulnerable al mismo
# tipo de carrera: dos llamadas que se solapan en el tiempo pueden contar
# 0 solapes cada una y terminar en dos sesiones superpuestas para el
# mismo terapeuta.
#
# El procedimiento real ejecuta sus pocas sentencias en milisegundos, asi
# que forzar la carrera con dos conexiones "a mano" es poco confiable (ver
# AUDITORIA.md: 10 llamadas concurrentes reales al procedimiento sin
# modificar NO alcanzaron a disparar la carrera, el overhead de conexion
# ya alcanza para serializarlas). Para probar el MECANISMO de forma
# reproducible, este test crea una copia del procedimiento IDENTICA salvo
# por un SELECT SLEEP() insertado entre el conteo de solapes y el INSERT
# -- exactamente donde una request real perdería tiempo en logica de
# aplicacion antes de confirmar. La copia se crea y se borra dentro de
# este mismo test, solo en la base de pruebas.
#
# HOY: se espera terminar con dos sesiones superpuestas para el mismo
# terapeuta (bug confirmado). Despues de una correccion (lock explicito o
# una validacion a nivel de trigger/tabla), no deberian coexistir.
#
# Uso:
#   .\test_race_regla6_sesiones.ps1 -Database asisto_test_audit

param(
    [string]$Database
)

. "$PSScriptRoot\..\lib\TestHelpers.ps1"


# Sin -Database explicito, el nombre sale del rol de la terminal
# (ASISTO_ROL). Con el nombre fijo de antes, dos terminales corriendo
# esto a la vez usaban la misma base y se la destruian entre si.
if (-not $PSBoundParameters.ContainsKey('Database')) {
    $Database = Get-NombreBaseDePrueba -Base "asisto_test_audit" `
        -EjemploExplicito '.\test_race_regla6_sesiones.ps1 -Database mi_base'
}

$modulo = "concurrencia"
$resultados = @()

$crearProcTest = @"
DROP PROCEDURE IF EXISTS p_registrar_sesion_race_test;
DELIMITER `$`$
CREATE PROCEDURE p_registrar_sesion_race_test (
  IN  p_id_terapeuta  INT UNSIGNED,
  IN  p_id_paciente   INT UNSIGNED,
  IN  p_fecha         DATE,
  IN  p_hora_inicio   TIME,
  IN  p_hora_fin      TIME,
  IN  p_estado        VARCHAR(20),
  IN  p_notas         TEXT,
  IN  p_delay         DECIMAL(5,2),
  OUT p_id_sesion     INT UNSIGNED,
  OUT p_mensaje       VARCHAR(255)
)
BEGIN
  DECLARE v_hora_fin      TIME         DEFAULT NULL;
  DECLARE v_superpuestas  INT UNSIGNED DEFAULT 0;
  DECLARE v_error         VARCHAR(255) DEFAULT '';

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    GET DIAGNOSTICS CONDITION 1 v_error = MESSAGE_TEXT;
    ROLLBACK;
    SET p_id_sesion = NULL;
    SET p_mensaje = CONCAT('Error al registrar la sesion: ', v_error);
  END;

  SET p_id_sesion = NULL;
  SET v_hora_fin = IFNULL(p_hora_fin, ADDTIME(p_hora_inicio, '01:00:00'));

  IF v_hora_fin <= p_hora_inicio THEN
    SET p_mensaje = 'La hora de fin debe ser posterior a la hora de inicio';
  ELSE
    START TRANSACTION;

    SELECT COUNT(*) INTO v_superpuestas
      FROM sesiones
     WHERE id_terapeuta = p_id_terapeuta
       AND fecha = p_fecha
       AND p_hora_inicio < IFNULL(hora_fin, ADDTIME(hora_inicio, '01:00:00'))
       AND v_hora_fin > hora_inicio;

    -- UNICA LINEA distinta del original: simula la latencia de una
    -- request real entre el conteo y el INSERT.
    SELECT SLEEP(p_delay);

    IF v_superpuestas > 0 THEN
      ROLLBACK;
      SET p_mensaje = CONCAT('El terapeuta ya tiene ', v_superpuestas, ' sesion(es) que se superponen con ese horario');
    ELSE
      INSERT INTO sesiones (id_terapeuta, id_paciente, fecha, hora_inicio, hora_fin, estado, notas)
      VALUES (p_id_terapeuta, p_id_paciente, p_fecha, p_hora_inicio, p_hora_fin, IFNULL(p_estado, 'incompleta'), p_notas);
      SET p_id_sesion = LAST_INSERT_ID();
      COMMIT;
      SET p_mensaje = 'Sesion registrada correctamente';
    END IF;
  END IF;
END`$`$
DELIMITER ;
"@

$rCrear = Invoke-Sql -Database $Database -Sql $crearProcTest
if ($rCrear.ExitCode -ne 0) {
    $resultados += New-TestResult $modulo "race_regla6_setup" "FAIL" "No se pudo crear el procedimiento instrumentado: $($rCrear.StdErr)"
    Write-ResultsTable $resultados
    return $resultados
}

# Fecha propia del test para no interferir con otros modulos. Terapeuta 1
# y dos pacientes distintos que ya tiene asignados (1 y 3), para aislar el
# solape del TERAPEUTA sin chocar con la UNIQUE (id_paciente, fecha, hora).
$jobScript = {
    param($MysqlExe, $LoginPath, $Database, $Sql)
    $tmpSql = [System.IO.Path]::GetTempFileName()
    $tmpOut = [System.IO.Path]::GetTempFileName()
    $tmpErr = [System.IO.Path]::GetTempFileName()
    Set-Content -Path $tmpSql -Value $Sql -Encoding utf8
    Start-Process -FilePath $MysqlExe -ArgumentList @("--login-path=$LoginPath", $Database) `
        -RedirectStandardInput $tmpSql -RedirectStandardOutput $tmpOut -RedirectStandardError $tmpErr `
        -NoNewWindow -Wait
    $out = Get-Content $tmpOut -Raw -ErrorAction SilentlyContinue
    Remove-Item $tmpSql, $tmpOut, $tmpErr -ErrorAction SilentlyContinue
    return $out
}

$fecha = "2026-09-01"
$sqlA = "CALL p_registrar_sesion_race_test(1, 1, '$fecha', '09:00:00', '10:00:00', 'incompleta', NULL, 4.0, @id, @msg); SELECT @id, @msg;"
$sqlB = "CALL p_registrar_sesion_race_test(1, 3, '$fecha', '09:30:00', '10:30:00', 'incompleta', NULL, 0, @id, @msg); SELECT @id, @msg;"

$job = Start-Job -ScriptBlock $jobScript -ArgumentList $script:MysqlExe, $script:LoginPath, $Database, $sqlA
Start-Sleep -Seconds 1
$rB = Invoke-Sql -Database $Database -Sql $sqlB
Wait-Job $job | Out-Null
Receive-Job $job | Out-Null
Remove-Job $job

$rSesiones = Invoke-Sql -Database $Database -Sql `
    "SELECT COUNT(*) FROM sesiones WHERE id_terapeuta = 1 AND fecha = '$fecha';"
$cantidad = [int](Get-ScalarValue $Database "SELECT COUNT(*) FROM sesiones WHERE id_terapeuta = 1 AND fecha = '$fecha';")

$resultados += Assert-True $modulo "race_regla6_no_quedan_sesiones_superpuestas" ($cantidad -le 1) `
    "Quedo $cantidad sesion(es) para el terapeuta ese dia (correcto, a lo sumo 1 debia poder registrarse)" `
    "Quedaron $cantidad sesiones simultaneas para el mismo terapeuta ese dia: la regla 6 fue violada por la carrera de concurrencia"

$null = Invoke-Sql -Database $Database -Sql "DROP PROCEDURE IF EXISTS p_registrar_sesion_race_test;"

Write-ResultsTable $resultados
return $resultados

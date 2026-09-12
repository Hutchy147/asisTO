# tests/db/graficos/test_evolucion_series.ps1
#
# p_evolucion_paciente, reescrito con LEFT JOIN para el modulo de graficos.
#
# LO QUE ESTE ARCHIVO VIGILA, Y POR QUE. El procedimiento decide QUE SERIES
# EXISTEN, y esa decision es la trampa de H2 en un lugar nuevo: si las series
# salieran de los objetivos activos HOY, una sesion de febrero que califico un
# objetivo archivado en marzo no tendria linea a la que pertenecer y el pasado
# perderia datos solo. La condicion correcta —y la que el procedimiento usa— es
# "objetivos VIVOS al momento de CADA sesion":
#
#     o.fecha_creacion <= TIMESTAMP(s.fecha, s.hora_inicio)
#     AND (o.activo = TRUE OR o.fecha_archivado > TIMESTAMP(s.fecha, s.hora_inicio))
#
# Es la misma condicion que el denominador de _conteo_de_objetivos (H2).
# Verificado que son identicas: si una cambia y la otra no, el grafico y el
# "3 de 4" del historial empiezan a contar objetivos distintos.
#
# EL FIXTURE ESTA HECHO PARA QUE LA VERSION INGENUA FALLE. El objetivo A se
# archiva en marzo y tiene evoluciones de febrero: con "los activos de hoy" no
# aparece ninguna serie para A, y sus dos evoluciones desaparecen del grafico
# sin ningun error.
#
# Uso:
#   .\test_evolucion_series.ps1 -Database asisto_test_audit2_graficos

param(
    [string]$Database
)

. "$PSScriptRoot\..\lib\TestHelpers.ps1"

if (-not $PSBoundParameters.ContainsKey('Database')) {
    $Database = Get-NombreBaseDePrueba -Base "asisto_test_audit" `
        -EjemploExplicito '.\test_evolucion_series.ps1 -Database mi_base'
}

$modulo = "graficos"
$resultados = @()

# Limpieza previa: ver el mismo bloque en sesiones/test_sesiones_paciente_de_baja.ps1.
$null = Invoke-Sql -Database $Database -Sql @"
DELETE e FROM evoluciones e JOIN sesiones s ON s.id = e.id_sesion
  JOIN pacientes p ON p.id = s.id_paciente WHERE p.nro_historia LIKE 'HC-GRAF-%';
DELETE s FROM sesiones s JOIN pacientes p ON p.id = s.id_paciente
 WHERE p.nro_historia LIKE 'HC-GRAF-%';
DELETE o FROM objetivos_terapeuticos o JOIN pacientes p ON p.id = o.id_paciente
 WHERE p.nro_historia LIKE 'HC-GRAF-%';
DELETE a FROM asignaciones a JOIN pacientes p ON p.id = a.id_paciente
 WHERE p.nro_historia LIKE 'HC-GRAF-%';
DELETE FROM pacientes WHERE nro_historia LIKE 'HC-GRAF-%';
"@

# Devuelve las filas del procedimiento como objetos. El orden de columnas lo
# fija el SELECT del procedimiento; si alguien lo cambia, este parser deja de
# leer lo que cree leer, asi que abajo hay una asercion sobre el encabezado.
function Get-SerieDelProcedimiento {
    param([int]$IdPaciente, [string]$Desde = '2000-01-01', [string]$Hasta = '2100-01-01')
    $r = Invoke-Sql -Database $Database -Sql @"
CALL p_evolucion_paciente($IdPaciente, '$Desde', '$Hasta', @m);
"@
    if ($r.ExitCode -ne 0) { throw "p_evolucion_paciente fallo: $($r.StdErr)" }
    $lineas = @($r.StdOut -split "`r?`n" | Where-Object { $_.Trim() -ne "" })
    if ($lineas.Count -eq 0) { return @() }
    $encabezado = $lineas[0] -split "`t"
    $filas = @()
    for ($i = 1; $i -lt $lineas.Count; $i++) {
        $c = $lineas[$i] -split "`t"
        $filas += [pscustomobject]@{
            IdSesion       = $c[0]
            Fecha          = $c[1]
            HoraInicio     = $c[2]
            EstadoSesion   = $c[3]
            IdObjetivo     = $c[4]
            Objetivo       = $c[5]
            ObjetivoActivo = $c[6]
            FechaArchivado = $c[7]
            Valor          = $c[8]
            Observaciones  = $c[9]
            Terapeuta      = $c[10]
        }
    }
    return @{ Encabezado = $encabezado; Filas = $filas }
}

# =======================================================================
# FIXTURE — el caso que la version ingenua no puede dibujar
#
#   objetivo A: creado 2026-01-05, ARCHIVADO 2026-03-15
#   objetivo B: creado 2026-01-05, sigue activo
#
#   sesion 1 (2026-02-10)  A=3  B=4      <- las dos vivas
#   sesion 2 (2026-02-20)  A sin calificar, B=5
#   sesion 3 (2026-04-10)  B=2            <- A ya archivada: no debe tener punto
#   sesion 4 (2026-04-20, AUSENCIA)       <- ninguna evolucion, por la regla 2
# =======================================================================

$r = Invoke-Sql -Database $Database -Sql @"
CALL p_alta_paciente('Grafico','Historico','2015-02-02',NULL,'HC-GRAF-1',NULL,@id,@msg);
SELECT @id;
"@
$pac = Get-IdDeSalida $r "El alta del paciente del grafico historico"

# La sesion 4 es la AUSENCIA del escenario y ahora tiene que declarar quien
# falto: desde b039bb4 el trigger de INSERT rechaza una fila de ausencia sin
# `ausencia_de`. 'paciente' no cambia nada de lo que este archivo mide --
# ninguna asercion mira esa columna, solo que la sesion 4 sea 'ausencia' y
# no traiga evolucion-- pero sin el dato la fila no entra.
#
# Y COMO ES UN INSERT MULTI-FILA, la fila rechazada se llevaba puestas a las
# otras tres: la sentencia entera se deshace. Por eso 8 aserciones daban rojo
# por UNA fila que faltaba, y ninguna hablaba de ausencias.
#
# El resultado del INSERT se REVISA, que antes no pasaba: estaba asignado a
# $null y el script seguia de largo con las variables vacias. Un fixture que
# no se sembro tiene que decirlo aca, no diez aserciones mas abajo.
$rSiembra = Invoke-Sql -Database $Database -Sql @"
INSERT INTO objetivos_terapeuticos (id_paciente, descripcion, activo)
  VALUES ($pac, 'GRAF objetivo A', TRUE), ($pac, 'GRAF objetivo B', TRUE);
UPDATE objetivos_terapeuticos SET fecha_creacion = '2026-01-05 09:00:00'
 WHERE id_paciente = $pac;
INSERT INTO sesiones (id_terapeuta, id_paciente, fecha, hora_inicio, hora_fin, estado, ausencia_de, notas) VALUES
  (1, $pac, '2026-02-10', '14:00:00', '14:45:00', 'completa',  NULL,       'GRAF s1'),
  (1, $pac, '2026-02-20', '14:00:00', '14:45:00', 'completa',  NULL,       'GRAF s2'),
  (1, $pac, '2026-04-10', '14:00:00', '14:45:00', 'completa',  NULL,       'GRAF s3'),
  (1, $pac, '2026-04-20', '14:00:00', '14:45:00', 'ausencia',  'paciente', 'GRAF s4');
"@
if ($rSiembra.ExitCode -ne 0) {
    throw "No se pudo sembrar el escenario del grafico: $(Get-UltimaLineaSql $rSiembra)"
}

$objA = [int](Get-ScalarValue $Database "SELECT id FROM objetivos_terapeuticos WHERE id_paciente=$pac AND descripcion='GRAF objetivo A';")
$objB = [int](Get-ScalarValue $Database "SELECT id FROM objetivos_terapeuticos WHERE id_paciente=$pac AND descripcion='GRAF objetivo B';")
$s1 = [int](Get-ScalarValue $Database "SELECT id FROM sesiones WHERE id_paciente=$pac AND fecha='2026-02-10';")
$s2 = [int](Get-ScalarValue $Database "SELECT id FROM sesiones WHERE id_paciente=$pac AND fecha='2026-02-20';")
$s3 = [int](Get-ScalarValue $Database "SELECT id FROM sesiones WHERE id_paciente=$pac AND fecha='2026-04-10';")

# Las evoluciones se cargan con A TODAVIA ACTIVA: la regla 4 no deja cargar
# sobre un objetivo archivado, y ese es justamente el orden real de los hechos.
$null = Invoke-Sql -Database $Database -Sql @"
INSERT INTO evoluciones (id_sesion, id_objetivo, valor) VALUES
  ($s1, $objA, 3), ($s1, $objB, 4),
  ($s2, $objB, 5),
  ($s3, $objB, 2);
"@

# Y recien ahora se archiva A, con la fecha que corresponde a la historia.
$null = Invoke-Sql -Database $Database -Sql @"
UPDATE objetivos_terapeuticos SET activo = FALSE WHERE id = $objA;
UPDATE objetivos_terapeuticos SET fecha_archivado = '2026-03-15 10:00:00' WHERE id = $objA;
"@

$salida = Get-SerieDelProcedimiento -IdPaciente $pac
$filas = $salida.Filas

# --- El parser lee lo que cree leer -------------------------------------
$esperadoEncabezado = @('id_sesion','fecha','hora_inicio','estado_sesion','id_objetivo',
                        'objetivo','objetivo_activo','fecha_archivado','valor',
                        'observaciones','terapeuta')
$resultados += Assert-True $modulo "el_orden_de_columnas_es_el_esperado" `
    (($salida.Encabezado -join ',') -eq ($esperadoEncabezado -join ',')) `
    "El SELECT del procedimiento devuelve las 11 columnas en el orden que el servicio desempaqueta" `
    "El orden de columnas cambio. Esperado: $($esperadoEncabezado -join ','). Llego: $($salida.Encabezado -join ','). El servicio desempaqueta por POSICION, asi que esto le rompe el mapeo sin ningun error."

# --- LA TRAMPA H2: el objetivo archivado tiene serie propia -------------
$filasA = @($filas | Where-Object { $_.IdObjetivo -eq "$objA" })
$resultados += Assert-True $modulo "el_objetivo_archivado_tiene_serie" ($filasA.Count -gt 0) `
    "El objetivo archivado en marzo aparece con su serie" `
    "El objetivo archivado NO tiene ninguna fila: las series estan saliendo de los objetivos activos de HOY y el pasado perdio datos. Es la trampa de H2."

# Vivo en s1 y s2 (febrero), archivado para s3 (abril) y s4 (abril).
$sesionesDeA = @($filasA | ForEach-Object { $_.IdSesion } | Sort-Object -Unique)
$resultados += Assert-True $modulo "el_archivado_tiene_puntos_solo_en_su_periodo_de_vida" `
    (($sesionesDeA -contains "$s1") -and ($sesionesDeA -contains "$s2") -and ($sesionesDeA.Count -eq 2)) `
    "El objetivo archivado tiene punto en las dos sesiones de febrero y en ninguna posterior a su archivado" `
    "Las sesiones del objetivo archivado son [$($sesionesDeA -join ', ')] y tenian que ser exactamente s1=$s1 y s2=$s2. Si aparece s3=$s3 (posterior al archivado), la condicion de vida no esta mirando fecha_archivado."

$valorAenS1 = ($filasA | Where-Object { $_.IdSesion -eq "$s1" }).Valor
$resultados += Assert-True $modulo "el_archivado_conserva_su_calificacion" ($valorAenS1 -eq '3') `
    "La calificacion de febrero del objetivo archivado sigue en la serie (valor 3)" `
    "El valor de la evolucion de febrero llego como '$valorAenS1' y tenia que ser 3"

$fechaArchivadoDeA = ($filasA | Select-Object -First 1).FechaArchivado
$resultados += Assert-True $modulo "la_serie_archivada_trae_su_fecha_de_cierre" `
    ($fechaArchivadoDeA -like '2026-03-15*') `
    "La serie trae fecha_archivado, asi que la linea puede terminar donde el objetivo se archivo" `
    "fecha_archivado llego como '$fechaArchivadoDeA': sin ella la linea del objetivo archivado queda abierta como si siguiera vigente"

# --- El valor nulo significa lo que dice significar ---------------------
$valorAenS2 = ($filasA | Where-Object { $_.IdSesion -eq "$s2" }).Valor
$resultados += Assert-True $modulo "sesion_sin_calificar_da_valor_nulo_y_no_desaparece" `
    ($valorAenS2 -eq 'NULL') `
    "La sesion donde el objetivo no se califico esta presente con valor NULL" `
    "La fila de la sesion sin calificar llego con valor '$valorAenS2'. Si no esta la fila, el grafico no puede distinguir 'no se midio' de 'no hubo sesion', que es la razon por la que se reescribio el procedimiento."

# La ausencia: la sesion existe como punto y NINGUN objetivo tiene valor.
$filasAusencia = @($filas | Where-Object { $_.EstadoSesion -eq 'ausencia' })
$conValorEnAusencia = @($filasAusencia | Where-Object { $_.Valor -ne 'NULL' })
$resultados += Assert-True $modulo "la_ausencia_aparece_como_punto_sin_valor" `
    ($filasAusencia.Count -gt 0 -and $conValorEnAusencia.Count -eq 0) `
    "La sesion en ausencia aparece con sus objetivos en NULL: el grafico puede dibujarla como hueco explicado" `
    "Filas de la sesion en ausencia: $($filasAusencia.Count), con valor: $($conValorEnAusencia.Count). La ausencia tiene que estar y tiene que venir sin valores."

# --- Ninguna evolucion se pierde ---------------------------------------
#
# Es la asercion mas general del archivo: cualquier evolucion cargada que no
# aparezca en ninguna serie es un dato clinico invisible en el grafico, sea
# cual sea el motivo (condicion de vida, fecha_archivado nula, JOIN de mas).
$evolucionesEnBase = [int](Get-ScalarValue $Database @"
SELECT COUNT(*) FROM evoluciones e JOIN sesiones s ON s.id = e.id_sesion
 WHERE s.id_paciente = $pac;
"@)
$filasConValor = @($filas | Where-Object { $_.Valor -ne 'NULL' }).Count
$resultados += Assert-True $modulo "ninguna_evolucion_queda_fuera_de_su_serie" `
    ($filasConValor -eq $evolucionesEnBase) `
    "Las $evolucionesEnBase evoluciones del paciente estan las $filasConValor en alguna serie" `
    "Hay $evolucionesEnBase evoluciones en la base y solo $filasConValor aparecen en el grafico: se perdieron $($evolucionesEnBase - $filasConValor) datos clinicos sin ningun error."

# Lo mismo contra el seed entero, que es donde hay historia de verdad.
$perdidasSeed = [int](Get-ScalarValue $Database @"
SELECT COUNT(*) FROM evoluciones e
  JOIN sesiones s ON s.id = e.id_sesion
  JOIN objetivos_terapeuticos o ON o.id = e.id_objetivo
 WHERE NOT (o.fecha_creacion <= TIMESTAMP(s.fecha, s.hora_inicio)
            AND (o.activo = TRUE OR o.fecha_archivado > TIMESTAMP(s.fecha, s.hora_inicio)));
"@)
$resultados += Assert-True $modulo "el_seed_no_tiene_evoluciones_invisibles" ($perdidasSeed -eq 0) `
    "Ninguna evolucion del seed cae fuera de la condicion de vida" `
    "$perdidasSeed evolucion(es) del seed no cumplen la condicion de vida de su objetivo, asi que no aparecen en ningun grafico. Caso tipico: un objetivo con activo=FALSE y fecha_archivado NULL (la columna la escribe el trigger al archivar; una fila insertada ya archivada no la tiene)."

# --- El orden que el servicio da por sentado ----------------------------
# El servicio agrupa recorriendo una sola vez, asi que si las filas de un
# mismo objetivo no vinieran juntas armaria dos series con el mismo id.
$ordenCorrecto = $true
$vistos = @{}
$anterior = $null
foreach ($f in $filas) {
    if ($f.IdObjetivo -ne $anterior) {
        if ($vistos.ContainsKey($f.IdObjetivo)) { $ordenCorrecto = $false; break }
        $vistos[$f.IdObjetivo] = $true
        $anterior = $f.IdObjetivo
    }
}
$resultados += Assert-True $modulo "las_filas_de_cada_objetivo_vienen_juntas" $ordenCorrecto `
    "Cada objetivo aparece en un solo bloque contiguo, que es lo que el servicio necesita para agrupar en una pasada" `
    "Las filas de un mismo objetivo vienen intercaladas con las de otro: el servicio agrupa en una sola pasada y armaria dos series con el mismo id."

# --- Paciente dado de baja con TODOS sus objetivos archivados -----------
$r = Invoke-Sql -Database $Database -Sql @"
CALL p_alta_paciente('Grafico','DeBaja','2015-03-03',NULL,'HC-GRAF-2',NULL,@id,@msg);
SELECT @id;
"@
$pacBaja = Get-IdDeSalida $r "El alta del paciente dado de baja del grafico"
$null = Invoke-Sql -Database $Database -Sql @"
INSERT INTO objetivos_terapeuticos (id_paciente, descripcion, activo)
  VALUES ($pacBaja, 'GRAF baja uno', TRUE), ($pacBaja, 'GRAF baja dos', TRUE);
UPDATE objetivos_terapeuticos SET fecha_creacion = '2026-01-05 09:00:00' WHERE id_paciente = $pacBaja;
INSERT INTO sesiones (id_terapeuta, id_paciente, fecha, hora_inicio, hora_fin, estado, notas)
  VALUES (1, $pacBaja, '2026-05-05', '16:00:00', '16:45:00', 'completa', 'GRAF baja s1');
"@
$sBaja = [int](Get-ScalarValue $Database "SELECT id FROM sesiones WHERE id_paciente=$pacBaja LIMIT 1;")
$objBaja1 = [int](Get-ScalarValue $Database "SELECT id FROM objetivos_terapeuticos WHERE id_paciente=$pacBaja AND descripcion='GRAF baja uno';")
$null = Invoke-Sql -Database $Database -Sql "INSERT INTO evoluciones (id_sesion,id_objetivo,valor) VALUES ($sBaja,$objBaja1,4);"

# La baja archiva los dos objetivos. Es el caso de "paciente de baja con todo
# archivado": el grafico tiene que seguir mostrando su historia entera.
$null = Invoke-Sql -Database $Database -Sql "CALL p_baja_paciente($pacBaja, @o, @a, @m);"

$salidaBaja = Get-SerieDelProcedimiento -IdPaciente $pacBaja
$filasBaja = $salidaBaja.Filas
$objetivosDeBaja = @($filasBaja | ForEach-Object { $_.IdObjetivo } | Sort-Object -Unique)
$resultados += Assert-True $modulo "paciente_de_baja_conserva_sus_dos_series" `
    ($objetivosDeBaja.Count -eq 2) `
    "El paciente dado de baja, con los dos objetivos archivados por la baja, conserva sus dos series" `
    "El paciente de baja devolvio $($objetivosDeBaja.Count) serie(s) y tenia que devolver 2. La baja archiva todos los objetivos: si la condicion de vida mirara solo `activo`, la historia entera de cualquier paciente de baja se volveria invisible."

$valorBaja = ($filasBaja | Where-Object { $_.Valor -ne 'NULL' } | Select-Object -First 1).Valor
$resultados += Assert-True $modulo "paciente_de_baja_conserva_su_calificacion" ($valorBaja -eq '4') `
    "La calificacion cargada antes de la baja sigue visible" `
    "La evolucion cargada antes de la baja llego como '$valorBaja' y tenia que ser 4"

# --- El procedimiento sigue contestando lo de antes ----------------------
$rInexistente = Invoke-Sql -Database $Database -Sql @"
CALL p_evolucion_paciente(999999, '2000-01-01', '2100-01-01', @m);
SELECT @m;
"@
$mensajeInexistente = Get-UltimaLineaSql $rInexistente
$resultados += Assert-True $modulo "paciente_inexistente_devuelve_su_mensaje" `
    ($mensajeInexistente -match "no existe") `
    "Sigue contestando 'El paciente indicado no existe'" `
    "Con un paciente inexistente contesto: '$mensajeInexistente'"

# El mensaje cuenta EVOLUCIONES, no filas. Es lo que hace comparable el
# conteo con el de antes de la reescritura, cuando cada fila era una
# evolucion. Si contara filas, el numero pasaria a ser sesiones x objetivos.
$rMensaje = Invoke-Sql -Database $Database -Sql @"
CALL p_evolucion_paciente($pac, '2000-01-01', '2100-01-01', @m);
SELECT @m;
"@
$mensaje = Get-UltimaLineaSql $rMensaje
$resultados += Assert-True $modulo "el_mensaje_cuenta_evoluciones_y_no_filas" `
    ($mensaje -match "Se encontraron $evolucionesEnBase evoluciones") `
    "El mensaje informa $evolucionesEnBase evoluciones, que es lo cargado" `
    "El mensaje dice '$mensaje' y las evoluciones cargadas son $evolucionesEnBase. Si informa $($filas.Count) esta contando filas (sesiones x objetivos), que es otra cosa."

Write-ResultsTable $resultados
return $resultados

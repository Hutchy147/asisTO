# tests/contratos/test_aridad_procedimientos.ps1
#
# Sujeta la FIRMA de los procedimientos almacenados: cuantos parametros tiene
# cada uno y como se llaman, declarado en `backend/database/schema.sql`, contra
# un manifiesto versionado (`firmas-procedimientos.txt`) que hay que tocar a
# mano.
#
# EL DEFECTO QUE ORIGINA ESTE TEST (2026-09-11 / 12). El commit b039bb4 agrego
# `p_ausencia_de` a `p_registrar_sesion` en la posicion 7. La aridad paso de 9
# a 10 y **13 llamadores de `tests/` quedaron rotos en silencio**. Ninguna
# suite dijo "la firma cambio": dijeron `ERROR 1318 (Incorrect number of
# arguments)`, que es el sintoma, trece veces, en tres carpetas. Y en `tests/db`
# ni siquiera eso se vio, porque el runner se caia antes de imprimir.
#
# QUE PRUEBA Y QUE NO -- dicho antes que nada, porque es la mitad del valor.
#
#   PRUEBA: que la firma declarada en schema.sql sea la que el manifiesto dice.
#   O sea: que cambiar una firma sea un ACTO CONSCIENTE, con su diff en un
#   archivo versionado, en vez de un efecto colateral que se descubre tres dias
#   despues.
#
#   NO PRUEBA: que los llamadores esten al dia. No los busca. Eso es la
#   "version completa" relevada en AUDITORIA.md (2026-09-12), y tiene tres
#   formas de dar verde falso -- las comas adentro de `DATE_ADD(...)`, el CALL
#   de Python partido en dos literales, y la colision de prefijos -- que
#   necesitan cada una su propia falsacion. Esta version no las tiene porque no
#   parsea llamadores.
#
#   Lo que si logra: quien cambie la firma tiene que tocar el manifiesto, y ESE
#   es el momento en que va a ir a buscar los llamadores. No los encuentra por
#   el; le avisa el mismo dia que hay que buscarlos.
#
# POR QUE NO LEE `information_schema`. Porque entonces necesitaria una base, y
# `tests/contratos` es la unica suite que corre en cualquier maquina sin MySQL,
# sin navegador y sin `ASISTO_ROL`. La pregunta que contesta es sobre el
# CODIGO FUENTE, no sobre una instancia. (Por el mismo motivo este archivo NO
# hace dot-source de `tests/db/lib/TestHelpers.ps1`: ese archivo resuelve
# `mysql.exe` AL IMPORTARSE y lanza si no lo encuentra.)
#
# NINGUN PATRON QUE NO MATCHEA SE SALTEA, igual que su archivo hermano: si el
# extractor no encuentra un procedimiento, o el manifiesto no tiene una linea,
# eso es FAIL POR NO PODER MEDIR. Nunca PASS por los que si se pudieron leer.
#
# COMO SE FALSO (criterio 4 de AUDITORIA.md): los dos archivos entran por
# parametro, asi que la falsacion se hace sobre COPIAS en un directorio
# temporal y no toca ni el schema ni el manifiesto de verdad. Los dos modos
# --firma cambiada sin tocar el manifiesto, y procedimiento borrado del
# manifiesto-- estan en la seccion de este test en AUDITORIA.md.
#
# Uso:
#   .\test_aridad_procedimientos.ps1
#   .\test_aridad_procedimientos.ps1 -SchemaSql copia.sql -Manifiesto copia.txt

param(
    [string]$SchemaSql  = "$PSScriptRoot\..\..\backend\database\schema.sql",
    [string]$Manifiesto = "$PSScriptRoot\firmas-procedimientos.txt"
)

$ErrorActionPreference = "Stop"

$MODULO = "contratos"

function Nuevo-Resultado {
    param([string]$Test, [string]$Resultado, [string]$Detalle)
    [pscustomobject]@{
        Modulo = $MODULO; Test = $Test; Resultado = $Resultado; Detalle = $Detalle
    }
}

function Leer-Archivo {
    param([string]$Ruta)
    if (-not (Test-Path -LiteralPath $Ruta)) { return $null }
    return (Get-Content -LiteralPath $Ruta -Raw)
}

# =======================================================================
# EL EXTRACTOR
#
# Un escaner de un solo paso que entiende profundidad de parentesis, comillas
# y comentarios A LA VEZ. No son tres pasadas de regex: son tres estados del
# mismo recorrido, y tienen que serlo, porque un parentesis adentro de un
# comentario no abre nada y una coma adentro de comillas no separa nada.
#
# POR QUE NO ALCANZA UN `-split ','`. Un parametro puede tener comas ADENTRO:
# `p_delay DECIMAL(5,2)` es UN parametro con una coma. Un split ingenuo cuenta
# 11 donde hay 10 y da VERDE FALSO. Es literalmente el caso que existe hoy en
# `p_registrar_sesion_race_test`, y por eso el control positivo de mas abajo lo
# usa de fixture.
#
# POR QUE NO SE LIMPIAN LOS COMENTARIOS DE TODO EL ARCHIVO ANTES. Porque un
# `--` adentro de un literal de cadena no es un comentario, y una pasada global
# que no mira comillas puede comerse media linea de codigo en una region que
# este test ni siquiera parsea, y corromper la siguiente. El escaner mira las
# comillas, asi que no tiene ese problema.
# =======================================================================

# Devuelve el texto entre el parentesis que abre en $Inicio y el que lo cierra,
# o $null si nunca cierra (archivo truncado / parentesis desbalanceado).
function Get-TextoEntreParentesis {
    param([string]$Texto, [int]$Inicio)

    $profundidad = 0
    $i = $Inicio
    $largo = $Texto.Length
    $enCadena = $false
    $enLinea = $false
    $enBloque = $false

    while ($i -lt $largo) {
        $c = $Texto[$i]
        $sig = if ($i + 1 -lt $largo) { $Texto[$i + 1] } else { [char]0 }

        if ($enLinea) {
            if ($c -eq "`n") { $enLinea = $false }
            $i++; continue
        }
        if ($enBloque) {
            if ($c -eq '*' -and $sig -eq '/') { $enBloque = $false; $i += 2; continue }
            $i++; continue
        }
        if ($enCadena) {
            # '' es una comilla escapada adentro de la cadena, no el cierre.
            if ($c -eq "'" -and $sig -eq "'") { $i += 2; continue }
            if ($c -eq '\') { $i += 2; continue }
            if ($c -eq "'") { $enCadena = $false }
            $i++; continue
        }

        if ($c -eq '-' -and $sig -eq '-') { $enLinea = $true; $i += 2; continue }
        if ($c -eq '#') { $enLinea = $true; $i++; continue }
        if ($c -eq '/' -and $sig -eq '*') { $enBloque = $true; $i += 2; continue }
        if ($c -eq "'") { $enCadena = $true; $i++; continue }

        if ($c -eq '(') { $profundidad++ }
        elseif ($c -eq ')') {
            $profundidad--
            if ($profundidad -eq 0) {
                return $Texto.Substring($Inicio + 1, $i - $Inicio - 1)
            }
        }
        $i++
    }
    return $null
}

# Parte una lista de parametros por las comas de NIVEL SUPERIOR.
function Split-ParametrosPorComa {
    param([string]$Lista)

    $partes = @()
    $actual = New-Object System.Text.StringBuilder
    $profundidad = 0
    $i = 0
    $largo = $Lista.Length
    $enCadena = $false
    $enLinea = $false
    $enBloque = $false

    while ($i -lt $largo) {
        $c = $Lista[$i]
        $sig = if ($i + 1 -lt $largo) { $Lista[$i + 1] } else { [char]0 }

        if ($enLinea) {
            if ($c -eq "`n") { $enLinea = $false; [void]$actual.Append(' ') }
            $i++; continue
        }
        if ($enBloque) {
            if ($c -eq '*' -and $sig -eq '/') { $enBloque = $false; $i += 2; continue }
            $i++; continue
        }
        if ($enCadena) {
            [void]$actual.Append($c)
            if ($c -eq "'" -and $sig -eq "'") { [void]$actual.Append($sig); $i += 2; continue }
            if ($c -eq "'") { $enCadena = $false }
            $i++; continue
        }

        if ($c -eq '-' -and $sig -eq '-') { $enLinea = $true; $i += 2; continue }
        if ($c -eq '#') { $enLinea = $true; $i++; continue }
        if ($c -eq '/' -and $sig -eq '*') { $enBloque = $true; $i += 2; continue }
        if ($c -eq "'") { $enCadena = $true; [void]$actual.Append($c); $i++; continue }

        if ($c -eq '(') { $profundidad++ }
        elseif ($c -eq ')') { $profundidad-- }

        if ($c -eq ',' -and $profundidad -eq 0) {
            $partes += $actual.ToString()
            [void]$actual.Clear()
            $i++; continue
        }

        [void]$actual.Append($c)
        $i++
    }
    $partes += $actual.ToString()

    # Una lista vacia (procedimiento sin parametros) da UN pedazo en blanco,
    # que no es un parametro. Sin este filtro, p_generar_demo() mediria 1.
    return @($partes | Where-Object { $_.Trim() -ne '' })
}

# De "IN  p_id_paciente  INT UNSIGNED" saca "IN p_id_paciente".
# La direccion por defecto en MySQL es IN cuando no se escribe.
function Get-DireccionYNombre {
    param([string]$Parametro)

    $limpio = ($Parametro -replace '\s+', ' ').Trim()
    $m = [regex]::Match($limpio, '(?i)^(IN|OUT|INOUT)\s+`?([A-Za-z0-9_$]+)`?\b')
    if ($m.Success) {
        return "$($m.Groups[1].Value.ToUpperInvariant()) $($m.Groups[2].Value)"
    }
    $m = [regex]::Match($limpio, '^`?([A-Za-z0-9_$]+)`?\b')
    if ($m.Success) { return "IN $($m.Groups[1].Value)" }
    return $null
}

# Devuelve un objeto por cada CREATE PROCEDURE encontrado.
#
# EL NOMBRE SE EXTRAE, NO SE BUSCA, y esa diferencia es la que evita la
# colision de prefijos. Preguntar "¿el texto contiene p_registrar_sesion?"
# matchea tambien a `p_registrar_sesion_race_test`; capturar
# `([A-Za-z0-9_$]+)` devuelve el identificador ENTERO y los dos quedan
# separados solos. El control positivo de mas abajo lo demuestra con los dos
# procedimientos de verdad.
function Get-ProcedimientosDeSql {
    param([string]$Sql)

    $procedimientos = @()
    $patron = '(?is)CREATE\s+PROCEDURE\s+(?:IF\s+NOT\s+EXISTS\s+)?' +
              '(?:`?([A-Za-z0-9_$]+)`?\s*\.\s*)?`?([A-Za-z0-9_$]+)`?\s*\('

    foreach ($m in [regex]::Matches($Sql, $patron)) {
        $nombre = $m.Groups[2].Value
        # El match termina JUSTO en el "(" que abre la lista.
        $posParen = $m.Index + $m.Length - 1
        $lista = Get-TextoEntreParentesis -Texto $Sql -Inicio $posParen

        if ($null -eq $lista) {
            $procedimientos += [pscustomobject]@{
                Nombre = $nombre; Aridad = $null; Firma = $null
                Problema = 'la lista de parametros nunca cierra el parentesis'
            }
            continue
        }

        $partes = Split-ParametrosPorComa -Lista $lista
        $nombres = @()
        $roto = $null
        foreach ($p in $partes) {
            $dn = Get-DireccionYNombre -Parametro $p
            if ($null -eq $dn) { $roto = "no se pudo leer el parametro '$($p.Trim())'"; break }
            $nombres += $dn
        }

        if ($roto) {
            $procedimientos += [pscustomobject]@{
                Nombre = $nombre; Aridad = $null; Firma = $null; Problema = $roto
            }
        } else {
            $procedimientos += [pscustomobject]@{
                Nombre   = $nombre
                Aridad   = $nombres.Count
                Firma    = ($nombres -join ', ')
                Problema = $null
            }
        }
    }
    return $procedimientos
}

# Linea de manifiesto para un procedimiento. Una sola funcion para escribirla
# y para sugerirla en el mensaje de un rojo: si fueran dos, el texto que el
# rojo manda a copiar podria no ser el que el test despues acepta.
function Format-LineaManifiesto {
    param($Procedimiento)
    return "$($Procedimiento.Nombre) | $($Procedimiento.Aridad) | $($Procedimiento.Firma)"
}

$resultados = @()

# =======================================================================
# 0. CONTROL POSITIVO DEL EXTRACTOR -- corre SIEMPRE, no solo al falsar
#
# Un test que sujeta un contrato con un parser adentro tiene DOS formas de
# mentir: que el contrato se rompa, o que el parser deje de medirlo. La
# segunda no la ve nadie, porque se ve igual que "todo bien".
#
# El fixture no es inventado: son los dos procedimientos REALES que ya se
# confundieron una vez (AUDITORIA.md, 2026-09-12 -- un grep por prefijo conto
# 15 llamadores donde habia 13). Y tienen LA MISMA ARIDAD, 10 y 10, asi que
# contar no alcanza para distinguirlos: hay que mirar los nombres. Ademas
# `p_delay DECIMAL(5,2)` mete una coma adentro de parentesis, que es la trampa
# del separador. Un solo fixture ejercita las dos.
# =======================================================================

$fixture = @'
DELIMITER $$
CREATE PROCEDURE p_registrar_sesion (
  IN  p_id_terapeuta  INT UNSIGNED,
  IN  p_id_paciente   INT UNSIGNED,
  IN  p_fecha         DATE,
  IN  p_hora_inicio   TIME,
  IN  p_hora_fin      TIME,
  IN  p_estado        VARCHAR(20),
  -- Un comentario con una coma, un (parentesis y una 'comilla
  IN  p_ausencia_de   VARCHAR(20),
  IN  p_notas         TEXT,
  OUT p_id_sesion     INT UNSIGNED,
  OUT p_mensaje       VARCHAR(255)
)
BEGIN
  SELECT 'no importa, (esto, no) se parsea';
END$$

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
  SELECT 1;
END$$
DELIMITER ;
'@

# El @() no es cosmetico: PowerShell 5.1 DESENVUELVE un array de un solo
# elemento al devolverlo, y ahi `.Count` no da 1 -- da vacio. Es el criterio 6
# de AUDITORIA.md, y lo cazo el control 0.d de este mismo archivo la primera
# vez que corrio. Sin el @(), un fixture de un solo procedimiento hace que el
# control se reporte roto sin que el extractor tenga nada malo.
$delFixture = @(Get-ProcedimientosDeSql -Sql $fixture)
$nombresFixture = @($delFixture | ForEach-Object { $_.Nombre })

# 0.a -- los dos nombres salen completos y distintos
$esperados = @('p_registrar_sesion', 'p_registrar_sesion_race_test')
$nombresOk = ($nombresFixture.Count -eq 2) -and
             ($nombresFixture[0] -ceq $esperados[0]) -and
             ($nombresFixture[1] -ceq $esperados[1])
if ($nombresOk) {
    $resultados += Nuevo-Resultado 'parser__distingue_nombres_con_prefijo_comun' "PASS" `
        "Sobre un fixture con los dos, el extractor devuelve 'p_registrar_sesion' y 'p_registrar_sesion_race_test' como identificadores enteros y distintos."
} else {
    $resultados += Nuevo-Resultado 'parser__distingue_nombres_con_prefijo_comun' "FAIL" `
        "El extractor no separo los dos nombres con prefijo comun. Devolvio: [$($nombresFixture -join ', ')]. Se esperaba exactamente [$($esperados -join ', ')]. Si esto falla, TODO lo de abajo puede estar midiendo el procedimiento equivocado."
}

# 0.b -- y no se confunden sus firmas, que es donde se nota de verdad, porque
#        la aridad de los dos es 10 y contar no los distingue
$sesionFix = $delFixture | Where-Object { $_.Nombre -ceq 'p_registrar_sesion' } | Select-Object -First 1
$raceFix   = $delFixture | Where-Object { $_.Nombre -ceq 'p_registrar_sesion_race_test' } | Select-Object -First 1
$firmasOk = ($null -ne $sesionFix) -and ($null -ne $raceFix) -and
            ($sesionFix.Firma -like '*p_ausencia_de*') -and ($sesionFix.Firma -notlike '*p_delay*') -and
            ($raceFix.Firma  -like '*p_delay*')       -and ($raceFix.Firma  -notlike '*p_ausencia_de*')
if ($firmasOk) {
    $resultados += Nuevo-Resultado 'parser__no_cruza_las_firmas_de_los_dos' "PASS" `
        "Cada uno se queda con SU firma: p_registrar_sesion trae p_ausencia_de y no p_delay; el _race_test al reves. Los dos miden 10, asi que esto es lo unico que los separa."
} else {
    $resultados += Nuevo-Resultado 'parser__no_cruza_las_firmas_de_los_dos' "FAIL" `
        "Las firmas se cruzaron entre dos procedimientos de prefijo comun. p_registrar_sesion='$($sesionFix.Firma)' | _race_test='$($raceFix.Firma)'."
}

# 0.c -- la coma de DECIMAL(5,2) no inflo el conteo
$aridadRace = if ($raceFix) { $raceFix.Aridad } else { $null }
if ($aridadRace -eq 10) {
    $resultados += Nuevo-Resultado 'parser__la_coma_adentro_de_parentesis_no_cuenta' "PASS" `
        "p_registrar_sesion_race_test mide 10 con un DECIMAL(5,2) adentro. Un split por coma a secas habria contado 11."
} else {
    $resultados += Nuevo-Resultado 'parser__la_coma_adentro_de_parentesis_no_cuenta' "FAIL" `
        "Con un parametro DECIMAL(5,2), el extractor conto $aridadRace y tenia que contar 10. El separador esta contando comas que estan adentro de parentesis: cualquier aridad de abajo puede estar inflada."
}

# 0.d -- un procedimiento sin parametros mide 0, no 1
$sinParams = @(Get-ProcedimientosDeSql -Sql "CREATE PROCEDURE p_generar_demo()`nBEGIN`n SELECT 1;`nEND")
$aridadCero = if ($sinParams.Count -eq 1) { $sinParams[0].Aridad } else { $null }
if ($aridadCero -eq 0) {
    $resultados += Nuevo-Resultado 'parser__sin_parametros_mide_cero' "PASS" `
        "Un procedimiento sin parametros mide 0. (El caso existe: p_generar_demo() en seed_demo.sql.)"
} else {
    $resultados += Nuevo-Resultado 'parser__sin_parametros_mide_cero' "FAIL" `
        "Un procedimiento sin parametros midio $aridadCero en vez de 0: la lista vacia se esta contando como un parametro en blanco."
}

# =======================================================================
# 1. LEER LAS DOS FUENTES
# =======================================================================

$textoSchema = Leer-Archivo $SchemaSql
$textoManifiesto = Leer-Archivo $Manifiesto

$delSchema = @()
if ($null -eq $textoSchema) {
    $resultados += Nuevo-Resultado 'fuente__schema_legible' "FAIL" `
        "No se pudo leer $SchemaSql. Sin el schema no hay nada contra que comparar."
} else {
    $delSchema = @(Get-ProcedimientosDeSql -Sql $textoSchema)
    if ($delSchema.Count -eq 0) {
        # "Vacio o identico no es un resultado": cero procedimientos en un
        # schema que sabemos que tiene nueve es el extractor roto, no un
        # schema sin procedimientos.
        $resultados += Nuevo-Resultado 'fuente__schema_legible' "FAIL" `
            "El extractor no encontro NINGUN procedimiento en $SchemaSql. Un schema sin procedimientos no existe en este proyecto: lo que se rompio es el extractor, y mientras tanto este test no esta sujetando nada."
    } else {
        $resultados += Nuevo-Resultado 'fuente__schema_legible' "PASS" `
            "$($delSchema.Count) procedimientos leidos de schema.sql."
    }
}

# El manifiesto: "nombre | aridad | firma" por linea. Se ignoran las lineas en
# blanco y las que arrancan con #.
$delManifiesto = @{}
$lineasMalas = @()
if ($null -eq $textoManifiesto) {
    $resultados += Nuevo-Resultado 'fuente__manifiesto_legible' "FAIL" `
        "No se pudo leer el manifiesto $Manifiesto. Sin el, este test no puede afirmar nada sobre ninguna firma."
} else {
    $n = 0
    foreach ($linea in ($textoManifiesto -split "`r?`n")) {
        $n++
        $t = $linea.Trim()
        if ($t -eq '' -or $t.StartsWith('#')) { continue }
        $partes = $t -split '\s*\|\s*', 3
        if ($partes.Count -ne 3 -or $partes[1] -notmatch '^\d+$') {
            $lineasMalas += "linea ${n}: '$t'"
            continue
        }
        $delManifiesto[$partes[0]] = [pscustomobject]@{
            Nombre = $partes[0]; Aridad = [int]$partes[1]; Firma = $partes[2].Trim()
        }
    }
    if ($lineasMalas.Count -gt 0) {
        $resultados += Nuevo-Resultado 'fuente__manifiesto_legible' "FAIL" `
            "El manifiesto tiene $($lineasMalas.Count) linea(s) que no se pudieron leer: $($lineasMalas -join ' ; '). El formato es 'nombre | aridad | firma'. Una linea ilegible es un procedimiento que dejo de estar sujetado."
    } elseif ($delManifiesto.Count -eq 0) {
        $resultados += Nuevo-Resultado 'fuente__manifiesto_legible' "FAIL" `
            "El manifiesto $Manifiesto no tiene ninguna entrada. Un manifiesto vacio hace pasar este test sin medir nada."
    } else {
        $resultados += Nuevo-Resultado 'fuente__manifiesto_legible' "PASS" `
            "$($delManifiesto.Count) entradas leidas del manifiesto."
    }
}

# =======================================================================
# 2. COBERTURA: ninguno de los dos lados puede tener algo que el otro no
#
# Estas dos aserciones son las que convierten "no lo pude medir" en ROJO.
# Sin ellas, borrar una linea del manifiesto haria que el procedimiento
# simplemente no se compare, y el test terminaria en verde con menos
# cobertura: exactamente el modo de falla que este archivo viene a impedir.
# =======================================================================

$nombresSchema = @($delSchema | ForEach-Object { $_.Nombre })
$faltanEnManifiesto = @($nombresSchema | Where-Object { -not $delManifiesto.ContainsKey($_) })
$sobranEnManifiesto = @($delManifiesto.Keys | Where-Object { $nombresSchema -notcontains $_ })

if ($delSchema.Count -eq 0 -or $delManifiesto.Count -eq 0) {
    $resultados += Nuevo-Resultado 'cobertura__todos_los_del_schema_estan_en_el_manifiesto' "FAIL" `
        "No se pudo comparar la cobertura: una de las dos fuentes no se leyo (ver arriba)."
} elseif ($faltanEnManifiesto.Count -eq 0) {
    $resultados += Nuevo-Resultado 'cobertura__todos_los_del_schema_estan_en_el_manifiesto' "PASS" `
        "Los $($nombresSchema.Count) procedimientos de schema.sql tienen su linea en el manifiesto."
} else {
    $sugeridas = @($delSchema |
        Where-Object { $faltanEnManifiesto -contains $_.Nombre -and $null -ne $_.Aridad } |
        ForEach-Object { Format-LineaManifiesto $_ })
    $resultados += Nuevo-Resultado 'cobertura__todos_los_del_schema_estan_en_el_manifiesto' "FAIL" `
        ("$($faltanEnManifiesto.Count) procedimiento(s) de schema.sql NO estan en el manifiesto: $($faltanEnManifiesto -join ', '). " +
         "Su firma no la esta sujetando nadie. Agregar al manifiesto: $($sugeridas -join '  //  ')")
}

if ($delSchema.Count -eq 0 -or $delManifiesto.Count -eq 0) {
    $resultados += Nuevo-Resultado 'cobertura__el_manifiesto_no_tiene_fantasmas' "FAIL" `
        "No se pudo comparar la cobertura: una de las dos fuentes no se leyo (ver arriba)."
} elseif ($sobranEnManifiesto.Count -eq 0) {
    $resultados += Nuevo-Resultado 'cobertura__el_manifiesto_no_tiene_fantasmas' "PASS" `
        "El manifiesto no nombra ningun procedimiento que schema.sql ya no tenga."
} else {
    $resultados += Nuevo-Resultado 'cobertura__el_manifiesto_no_tiene_fantasmas' "FAIL" `
        ("El manifiesto nombra $($sobranEnManifiesto.Count) procedimiento(s) que NO estan en schema.sql: " +
         "$($sobranEnManifiesto -join ', '). O se borro/renombro el procedimiento y el manifiesto quedo viejo, " +
         "o el extractor dejo de encontrarlo. Las dos hay que mirarlas: la segunda apaga este test en silencio.")
}

# =======================================================================
# 3. LA ASERCION CENTRAL: una por procedimiento
#
# Se compara PRIMERO la aridad, porque es la que rompe llamadores y la que
# tiene que salir nombrada en el mensaje: un `CALL` con la cantidad equivocada
# de argumentos es ERROR 1318 y no compila. La firma se compara despues, y
# atrapa lo que la aridad no puede: dos parametros dados vuelta, o uno
# cambiado por otro, con el total igual. Ese caso NO da error de MySQL -- los
# llamadores siguen "andando" y escriben el dato en la columna equivocada.
# =======================================================================

foreach ($p in ($delSchema | Sort-Object Nombre)) {
    $test = "firma__$($p.Nombre)"

    if ($null -ne $p.Problema) {
        $resultados += Nuevo-Resultado $test "FAIL" `
            "No se pudo leer la firma de $($p.Nombre) en schema.sql: $($p.Problema). Mientras esto no se lea, ese procedimiento no esta sujetado."
        continue
    }

    if (-not $delManifiesto.ContainsKey($p.Nombre)) {
        # Ya lo reporto la cobertura; aca se repite como rojo propio para que
        # el procedimiento no quede sin fila en la tabla y parezca verde.
        $resultados += Nuevo-Resultado $test "FAIL" `
            "$($p.Nombre) no tiene linea en el manifiesto, asi que su firma no se comparo contra nada. Linea a agregar: $(Format-LineaManifiesto $p)"
        continue
    }

    $m = $delManifiesto[$p.Nombre]

    if ($p.Aridad -ne $m.Aridad) {
        $resultados += Nuevo-Resultado $test "FAIL" `
            ("ARIDAD DISTINTA en $($p.Nombre): schema.sql declara $($p.Aridad) parametros y el manifiesto dice $($m.Aridad). " +
             "Un CALL con la cantidad vieja da ERROR 1318 y no compila. " +
             "schema.sql: [$($p.Firma)] | manifiesto: [$($m.Firma)]. " +
             "Si el cambio es intencional, la linea nueva del manifiesto es: $(Format-LineaManifiesto $p)")
    } elseif ($p.Firma -cne $m.Firma) {
        $resultados += Nuevo-Resultado $test "FAIL" `
            ("MISMA ARIDAD ($($p.Aridad)) PERO OTRA FIRMA en $($p.Nombre). Este es el caso silencioso: MySQL no se queja, " +
             "los CALL existentes siguen compilando y el dato entra en el parametro equivocado. " +
             "schema.sql: [$($p.Firma)] | manifiesto: [$($m.Firma)]. " +
             "Si el cambio es intencional, la linea nueva del manifiesto es: $(Format-LineaManifiesto $p)")
    } else {
        $resultados += Nuevo-Resultado $test "PASS" `
            "$($p.Nombre): $($p.Aridad) parametros, firma igual a la del manifiesto."
    }
}

# =======================================================================
# 4. Recordatorio de alcance, como INFO
# =======================================================================

$resultados += Nuevo-Resultado 'alcance__este_test_no_mira_llamadores' "INFO" `
    ("Este archivo compara schema.sql contra el manifiesto y NADA MAS: no busca ni un solo CALL. " +
     "Un procedimiento puede estar perfectamente sujetado aca y tener llamadores rotos igual. " +
     "El relevamiento de la version que si los busca -- y de las tres formas que tiene de dar " +
     "verde falso -- esta en AUDITORIA.md, 2026-09-12.")

# --- Salida --------------------------------------------------------------

$resultados | Format-Table -AutoSize -Property Modulo, Test, Resultado, Detalle | Out-String -Width 220 | Write-Host

$pass = @($resultados | Where-Object { $_.Resultado -eq "PASS" }).Count
$fail = @($resultados | Where-Object { $_.Resultado -eq "FAIL" }).Count
$info = @($resultados | Where-Object { $_.Resultado -eq "INFO" }).Count

# Write-Host y no Write-Output, por lo documentado en TestHelpers.ps1: el
# resumen por el stream de salida se cuela como un objeto mas en cualquier
# llamador que haga "$todos += & este.ps1" e infla el TOTAL.
Write-Host "PASS: $pass   FAIL: $fail   INFO: $info   TOTAL: $($resultados.Count)"

return $resultados

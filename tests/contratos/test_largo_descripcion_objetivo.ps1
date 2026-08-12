# tests/contratos/test_largo_descripcion_objetivo.ps1
#
# Sujeta el largo maximo de la descripcion de un objetivo terapeutico, que
# hoy vale 700 y esta escrito en CINCO lugares de tres capas distintas.
#
# EL DEFECTO QUE ORIGINA ESTE TEST (ESTADO.md, diagnostico del 2026-08-06):
# habia tres limites distintos y ninguno sabia del otro -- 180 en el
# textarea, NINGUNO en el servicio, 500 en la columna --, y el unico que se
# aplicaba de verdad era un atributo HTML. Un objetivo en el formato real de
# la practica (398 caracteres medidos) se cortaba en silencio a mitad de
# frase y despues no se podia ni editar. El lote del 2026-08-07 dejo los tres
# numeros en 700, y desde entonces coinciden POR CONVENCION: no hay nada que
# los sujete. Este archivo es lo que faltaba.
#
# QUE PRUEBA Y QUE NO. Es un barrido estatico sobre el codigo fuente: lee los
# cinco numeros y afirma que son el mismo. NO prueba que la base rechace 701
# -- eso ya lo cubre el servicio -- ni que el navegador corte en 700. Lo que
# agarra es la clase de cambio que produjo el defecto original: alguien
# ensancha la columna y se olvida del frontend, o baja el tope del formulario
# y deja la base donde estaba. Ahi los numeros se separan y esto se pone en
# rojo el mismo dia, no en la demo.
#
# POR QUE CINCO Y NO TRES. Los tres del diagnostico son la columna, el modelo
# y el servicio del frontend. Los otros dos los pide el propio schema.sql:
#   - `descripcion_activa` es una columna GENERADA a partir de `descripcion`
#     y su tipo tiene que seguir al de la columna de origen (schema.sql:235).
#   - `plantillas_objetivos.descripcion` acompania a la otra a proposito:
#     "una plantilla que no pueda contener un objetivo real no sirve para
#     nada. Si una de las dos cambia de tamano, cambian las dos"
#     (schema.sql:495).
# Las dos son parte del mismo numero, asi que se sujetan con el mismo test.
#
# NINGUN PATRON QUE NO MATCHEA SE SALTEA. Si una expresion regular deja de
# encontrar su numero, este archivo reporta FAIL por ese archivo, no PASS por
# los otros. Es el modo de falla que este proyecto ya vio cuatro veces: un
# test que pasa en verde porque dejo de medir lo que decia medir.
#
# COMO SE FALSO (criterio 4 de AUDITORIA.md, "un test verde no prueba nada
# hasta que se lo vio en rojo"): los cinco archivos entran por parametro, asi
# que la falsacion se hace sobre COPIAS en un directorio temporal y no toca
# el codigo de la aplicacion. Ver la seccion de este test en AUDITORIA.md.
#
# Uso:
#   .\test_largo_descripcion_objetivo.ps1
#   .\test_largo_descripcion_objetivo.ps1 -Database asisto
#
# -Database agrega tres aserciones contra una base REAL: compara el largo
# aplicado en las columnas contra el que declara schema.sql. Sirve para
# detectar una instancia local donde la migracion del 2026-08-07 nunca se
# corrio. Es la unica parte que necesita MySQL, y es de SOLO LECTURA: lo
# unico que consulta es information_schema. Por eso -- y solo por eso -- aca
# si tiene sentido apuntar a "asisto": este archivo no escribe ni borra nada.

param(
    [string]$SchemaSql  = "$PSScriptRoot\..\..\backend\database\schema.sql",
    [string]$ModeloPy   = "$PSScriptRoot\..\..\backend\app\models\objetivo.py",
    [string]$ServicioPy = "$PSScriptRoot\..\..\backend\app\services\objetivos_service.py",
    [string]$ServicioJs = "$PSScriptRoot\..\..\frontend\src\services\objetivosService.js",
    [string]$ModalJsx   = "$PSScriptRoot\..\..\frontend\src\components\objetivos\ModalObjetivo.jsx",
    [string]$FrontendSrc = "$PSScriptRoot\..\..\frontend\src",
    [string]$Database   = ""
)

$ErrorActionPreference = "Stop"

# Techo duro de InnoDB para esta columna, MEDIDO y documentado en
# schema.sql:215-220: la UNIQUE es (id_paciente, descripcion_activa), o sea
# INT UNSIGNED + VARCHAR(N) en utf8mb4, y 767*4 + 4 = 3072 bytes es el limite
# de clave. Con VARCHAR(768) el CREATE TABLE falla con ERROR 1071. Si alguien
# sube el numero a 800, la base ni siquiera se puede crear: mejor decirlo
# aca que descubrirlo cuando falle el ALTER.
$TECHO_INNODB = 767

$MODULO = "contratos"

function Nuevo-Resultado {
    param([string]$Test, [string]$Resultado, [string]$Detalle)
    [pscustomobject]@{
        Modulo = $MODULO; Test = $Test; Resultado = $Resultado; Detalle = $Detalle
    }
}

# Saca los comentarios de SQL antes de buscar nada. NO es cosmetico: el
# comentario que explica POR QUE la columna mide 700 tiene la palabra 700
# adentro, y el bloque de arriba de la tabla incluso escribe "VARCHAR(N)".
# Sin este recorte, un dia el test podria estar leyendo la explicacion en vez
# de la declaracion.
function Quitar-ComentariosSql {
    param([string]$Texto)
    $evaluador = [System.Text.RegularExpressions.MatchEvaluator] {
        param($m)
        return ($m.Value -replace '[^\r\n]', '')
    }
    $sinBloques = [regex]::Replace($Texto, '/\*[\s\S]*?\*/', $evaluador)
    return [regex]::Replace($sinBloques, '--[^\r\n]*', '')
}

# Devuelve el cuerpo del CREATE TABLE pedido, o $null si no esta. Se acota a
# la tabla a proposito: `descripcion VARCHAR(...)` a secas matchearia
# cualquier tabla que tenga una columna con ese nombre, y el dia que exista
# otra el test estaria midiendo la equivocada sin avisar.
function Get-BloqueCreateTable {
    param([string]$Sql, [string]$Tabla)
    $patron = '(?is)CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?' +
              [regex]::Escape($Tabla) + '\s*\((.*?)\)\s*ENGINE'
    $m = [regex]::Match($Sql, $patron)
    if (-not $m.Success) { return $null }
    return $m.Groups[1].Value
}

# Largo declarado de una columna VARCHAR dentro de un bloque de CREATE TABLE.
# El anclaje a principio de linea es lo que evita que `descripcion` matchee
# la declaracion de `descripcion_activa` (y al reves).
function Get-LargoVarchar {
    param([string]$Bloque, [string]$Columna)
    if (-not $Bloque) { return $null }
    $patron = '(?im)^\s*' + [regex]::Escape($Columna) + '\s+VARCHAR\s*\(\s*(\d+)\s*\)'
    $m = [regex]::Match($Bloque, $patron)
    if (-not $m.Success) { return $null }
    return [int]$m.Groups[1].Value
}

function Get-EnteroPorPatron {
    param([string]$Texto, [string]$Patron)
    $m = [regex]::Match($Texto, $Patron)
    if (-not $m.Success) { return $null }
    return [int]$m.Groups[1].Value
}

function Leer-Archivo {
    param([string]$Ruta)
    if (-not (Test-Path $Ruta)) { return $null }
    return (Get-Content -LiteralPath $Ruta -Raw)
}

$resultados = @()

# --- 1. Los cinco numeros ------------------------------------------------

$textoSchema = Leer-Archivo $SchemaSql
$sqlSinComentarios = if ($textoSchema) { Quitar-ComentariosSql $textoSchema } else { $null }
$bloqueObjetivos = if ($sqlSinComentarios) { Get-BloqueCreateTable $sqlSinComentarios 'objetivos_terapeuticos' } else { $null }
$bloquePlantillas = if ($sqlSinComentarios) { Get-BloqueCreateTable $sqlSinComentarios 'plantillas_objetivos' } else { $null }

$textoModelo = Leer-Archivo $ModeloPy
$textoServicioJs = Leer-Archivo $ServicioJs

$fuentes = @(
    [pscustomobject]@{
        Test   = 'largo__schema_objetivos_descripcion'
        Origen = 'schema.sql -> objetivos_terapeuticos.descripcion'
        Valor  = (Get-LargoVarchar $bloqueObjetivos 'descripcion')
        Ayuda  = 'No se encontro la declaracion VARCHAR de la columna dentro del CREATE TABLE objetivos_terapeuticos.'
    },
    [pscustomobject]@{
        Test   = 'largo__schema_descripcion_activa'
        Origen = 'schema.sql -> objetivos_terapeuticos.descripcion_activa'
        Valor  = (Get-LargoVarchar $bloqueObjetivos 'descripcion_activa')
        Ayuda  = 'No se encontro la declaracion VARCHAR de la columna generada. Es STORED: su tipo sigue al de descripcion.'
    },
    [pscustomobject]@{
        Test   = 'largo__schema_plantillas_descripcion'
        Origen = 'schema.sql -> plantillas_objetivos.descripcion'
        Valor  = (Get-LargoVarchar $bloquePlantillas 'descripcion')
        Ayuda  = 'No se encontro la declaracion VARCHAR dentro del CREATE TABLE plantillas_objetivos.'
    },
    [pscustomobject]@{
        Test   = 'largo__modelo_backend'
        Origen = 'models/objetivo.py -> MAXIMO_CARACTERES_DESCRIPCION'
        Valor  = $(if ($textoModelo) { Get-EnteroPorPatron $textoModelo '(?m)^\s*MAXIMO_CARACTERES_DESCRIPCION\s*=\s*(\d+)' } else { $null })
        Ayuda  = 'No se encontro la asignacion de MAXIMO_CARACTERES_DESCRIPCION en el modelo.'
    },
    [pscustomobject]@{
        Test   = 'largo__servicio_frontend'
        Origen = 'services/objetivosService.js -> MAXIMO_CARACTERES_DESCRIPCION'
        Valor  = $(if ($textoServicioJs) { Get-EnteroPorPatron $textoServicioJs '(?m)^\s*export\s+const\s+MAXIMO_CARACTERES_DESCRIPCION\s*=\s*(\d+)' } else { $null })
        Ayuda  = 'No se encontro el export de MAXIMO_CARACTERES_DESCRIPCION en el servicio del frontend.'
    }
)

foreach ($f in $fuentes) {
    if ($null -ne $f.Valor) {
        $resultados += Nuevo-Resultado $f.Test "PASS" "$($f.Origen) declara $($f.Valor)."
    } else {
        # FAIL, no INFO ni salteo: si esto no se lee, este archivo dejo de
        # sujetar ese numero y hay que enterarse.
        $resultados += Nuevo-Resultado $f.Test "FAIL" `
            "No se pudo leer el largo en $($f.Origen). $($f.Ayuda) Mientras esto no se lea, este test NO esta sujetando ese numero."
    }
}

# --- 2. La asercion central: los cinco dicen lo mismo --------------------

$leidos = @($fuentes | Where-Object { $null -ne $_.Valor })
$detalleValores = ($fuentes | ForEach-Object {
    "$($_.Origen)=$(if ($null -ne $_.Valor) { $_.Valor } else { '?' })"
}) -join '; '

$largoReferencia = $null
if ($leidos.Count -ne $fuentes.Count) {
    $resultados += Nuevo-Resultado 'largo__los_cinco_numeros_coinciden' "FAIL" `
        "No se pudieron leer los $($fuentes.Count) numeros ($($leidos.Count) leidos), asi que la coincidencia no se puede afirmar. Valores: $detalleValores"
} else {
    $distintos = @($leidos | ForEach-Object { $_.Valor } | Sort-Object -Unique)
    if ($distintos.Count -eq 1) {
        $largoReferencia = $distintos[0]
        $resultados += Nuevo-Resultado 'largo__los_cinco_numeros_coinciden' "PASS" `
            "Los $($fuentes.Count) lugares declaran $largoReferencia."
    } else {
        $resultados += Nuevo-Resultado 'largo__los_cinco_numeros_coinciden' "FAIL" `
            "El largo se separo en $($distintos.Count) valores distintos ($($distintos -join ' / ')). Es el defecto del 2026-08-06 volviendo: $detalleValores"
    }
}

# --- 3. Que la constante siga siendo la que se usa -----------------------
#
# Los numeros pueden coincidir y el limite estar roto igual: alcanza con que
# un consumidor deje de leer la constante y escriba el numero al lado. Estas
# tres aserciones sujetan la CADENA, no el numero.

$cadena = @(
    [pscustomobject]@{
        Test    = 'cadena__el_modelo_dimensiona_la_columna_con_la_constante'
        Texto   = $textoModelo
        Archivo = 'models/objetivo.py'
        Patron  = 'db\.String\(\s*MAXIMO_CARACTERES_DESCRIPCION\s*\)'
        Ok      = 'La columna del modelo se dimensiona con la constante, no con un literal.'
        Mal     = 'db.String() ya no recibe MAXIMO_CARACTERES_DESCRIPCION. Si ahi quedo un numero literal, el modelo puede alejarse de la constante sin que nada avise.'
    },
    [pscustomobject]@{
        Test    = 'cadena__el_servicio_backend_valida_con_la_constante'
        Texto   = (Leer-Archivo $ServicioPy)
        Archivo = 'services/objetivos_service.py'
        Patron  = '>\s*MAXIMO_CARACTERES_DESCRIPCION'
        Ok      = 'La validacion de largo compara contra la constante importada del modelo.'
        Mal     = 'La comparacion de largo ya no usa MAXIMO_CARACTERES_DESCRIPCION. Con un numero literal ahi, el servicio deja de acompanar al schema.'
    },
    [pscustomobject]@{
        Test    = 'cadena__el_modal_pasa_la_constante_al_campo'
        Texto   = (Leer-Archivo $ModalJsx)
        Archivo = 'components/objetivos/ModalObjetivo.jsx'
        Patron  = 'maximoCaracteres=\{\s*MAXIMO_CARACTERES_DESCRIPCION\s*\}'
        Ok      = 'El formulario toma el tope (y el contador, y el maxLength) de la constante del servicio.'
        Mal     = 'El formulario ya no pasa MAXIMO_CARACTERES_DESCRIPCION a maximoCaracteres. Ese prop es el que fija el maxLength del input: con un literal ahi vuelve el caso de 2026-08-06, donde el unico limite real era un atributo HTML que no coincidia con la base.'
    }
)

foreach ($c in $cadena) {
    if (-not $c.Texto) {
        $resultados += Nuevo-Resultado $c.Test "FAIL" "No se pudo leer $($c.Archivo)."
    } elseif ($c.Texto -match $c.Patron) {
        $resultados += Nuevo-Resultado $c.Test "PASS" $c.Ok
    } else {
        $resultados += Nuevo-Resultado $c.Test "FAIL" "$($c.Archivo): $($c.Mal)"
    }
}

# --- 4. Ningun tope escrito a mano en el formulario de objetivos ---------

$textoModal = Leer-Archivo $ModalJsx
if (-not $textoModal) {
    $resultados += Nuevo-Resultado 'cadena__el_modal_no_fija_el_tope_a_mano' "FAIL" `
        "No se pudo leer $ModalJsx."
} elseif ($textoModal -match 'maximoCaracteres=\{\s*\d+\s*\}') {
    $resultados += Nuevo-Resultado 'cadena__el_modal_no_fija_el_tope_a_mano' "FAIL" `
        "ModalObjetivo.jsx fija maximoCaracteres con un numero literal. El tope tiene que salir de la constante o queda un cuarto lugar donde el numero puede divergir."
} else {
    $resultados += Nuevo-Resultado 'cadena__el_modal_no_fija_el_tope_a_mano' "PASS" `
        "El tope no esta escrito a mano en el formulario."
}

# El mismo barrido sobre TODO el frontend, pero como INFO y no como FAIL:
# otro formulario puede tener un tope legitimo distinto (notas, observaciones)
# y ese no es asunto de este test. Se reporta igual porque la leccion del
# episodio 180/500/700 aplica a cualquier campo: el numero en un solo lugar
# conceptual. Hoy no hay ninguno.
$literales = @()
if (Test-Path $FrontendSrc) {
    $jsx = Get-ChildItem -LiteralPath $FrontendSrc -Recurse -Filter "*.jsx" -ErrorAction SilentlyContinue
    foreach ($archivo in $jsx) {
        $contenido = Get-Content -LiteralPath $archivo.FullName -Raw
        foreach ($m in [regex]::Matches($contenido, 'maximoCaracteres=\{\s*(\d+)\s*\}')) {
            $ruta = $archivo.FullName.Substring((Resolve-Path $FrontendSrc).Path.Length + 1) -replace '\\', '/'
            $literales += "src/$ruta -> $($m.Groups[1].Value)"
        }
    }
}
$resultados += Nuevo-Resultado 'cadena__topes_literales_en_otros_formularios' "INFO" `
    $(if ($literales.Count -eq 0) {
        "Ningun .jsx del frontend fija maximoCaracteres con un numero literal."
    } else {
        "Formularios que fijan el tope con un literal (no es un fallo de este test, pero es la misma clase de numero suelto): $($literales -join ', ')"
    })

# --- 5. El numero entra en la clave de InnoDB ----------------------------

# Se mide contra el MAYOR de los numeros leidos, no contra la referencia:
# si los cinco se separaron, el de arriba ya reporto eso y este chequeo tiene
# que seguir diciendo algo util igual. Asi una divergencia da UN rojo, y este
# se suma solo cuando el techo esta roto de verdad.
$mayorLeido = $null
if ($leidos.Count -gt 0) {
    $mayorLeido = ($leidos | ForEach-Object { $_.Valor } | Measure-Object -Maximum).Maximum
}

if ($null -eq $mayorLeido) {
    $resultados += Nuevo-Resultado 'largo__entra_en_la_clave_de_innodb' "FAIL" `
        "No se pudo leer ningun largo, asi que el techo de $TECHO_INNODB no se verifico."
} elseif ($mayorLeido -le $TECHO_INNODB) {
    $resultados += Nuevo-Resultado 'largo__entra_en_la_clave_de_innodb' "PASS" `
        "$mayorLeido <= ${TECHO_INNODB}: la UNIQUE (id_paciente, descripcion_activa) sigue entrando en los 3072 bytes de clave."
} else {
    $resultados += Nuevo-Resultado 'largo__entra_en_la_clave_de_innodb' "FAIL" `
        "$mayorLeido supera el techo medido de $TECHO_INNODB. Con ese tamano el CREATE TABLE falla con ERROR 1071 ('Specified key was too long'): la base no se puede ni crear."
}

# --- 6. Opcional: lo que quedo APLICADO en una base real -----------------

if (-not $Database) {
    $resultados += Nuevo-Resultado 'base__largo_aplicado' "INFO" `
        "No se verifico ninguna base: esto compara archivos, no columnas. Para comprobar que la migracion del 2026-08-07 se aplico en esta instancia: .\test_largo_descripcion_objetivo.ps1 -Database asisto (solo lee information_schema)."
} else {
    . "$PSScriptRoot\..\db\lib\TestHelpers.ps1"

    # Cada columna se compara contra SU declaracion en schema.sql, no contra
    # la referencia comun: si los archivos ya se separaron, esta parte tiene
    # que poder decir igual cual de las columnas quedo vieja en la base.
    $columnas = @(
        @{ Tabla = 'objetivos_terapeuticos'; Columna = 'descripcion';        Declarado = $fuentes[0].Valor },
        @{ Tabla = 'objetivos_terapeuticos'; Columna = 'descripcion_activa'; Declarado = $fuentes[1].Valor },
        @{ Tabla = 'plantillas_objetivos';   Columna = 'descripcion';        Declarado = $fuentes[2].Valor }
    )

    foreach ($c in $columnas) {
        $test = "base__$($c.Tabla)_$($c.Columna)"
        $sql = @"
SELECT CHARACTER_MAXIMUM_LENGTH FROM information_schema.columns
WHERE TABLE_SCHEMA = '$Database' AND TABLE_NAME = '$($c.Tabla)'
  AND COLUMN_NAME = '$($c.Columna)';
"@
        try {
            $valor = Get-ScalarValue -Database $Database -Sql $sql
        } catch {
            $resultados += Nuevo-Resultado $test "FAIL" "No se pudo consultar $Database : $($_.Exception.Message)"
            continue
        }

        if (-not $valor) {
            # information_schema filtra por privilegio: una fila vacia puede
            # ser "la columna no existe" o "este usuario no la puede ver".
            # Se distinguen a mano; lo que no se hace es darlo por bueno.
            $resultados += Nuevo-Resultado $test "FAIL" `
                "information_schema no devolvio nada para $($c.Tabla).$($c.Columna) en '$Database'. O la columna no existe (migracion sin aplicar) o el login usado no tiene privilegios sobre esa tabla; las dos hay que mirarlas."
        } elseif ($null -eq $c.Declarado) {
            $resultados += Nuevo-Resultado $test "FAIL" `
                "$Database.$($c.Tabla).$($c.Columna) mide $valor, pero no se pudo leer el largo declarado en schema.sql para compararlo."
        } elseif ([int]$valor -eq $c.Declarado) {
            $resultados += Nuevo-Resultado $test "PASS" `
                "$Database.$($c.Tabla).$($c.Columna) = $valor, igual que schema.sql."
        } else {
            $resultados += Nuevo-Resultado $test "FAIL" `
                "$Database.$($c.Tabla).$($c.Columna) mide $valor y schema.sql declara $($c.Declarado). Esa instancia no tiene aplicada la migracion del 2026-08-07 (o tiene otra cosa encima)."
        }
    }
}

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

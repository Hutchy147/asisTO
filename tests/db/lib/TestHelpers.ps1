# tests/db/lib/TestHelpers.ps1
#
# Utilidades compartidas por todos los modulos de tests de base de datos.
# Se ejecuta contra una base de pruebas descartable (nunca "asisto"),
# creada por tests/db/setup/build_test_db.ps1.
#
# Cada modulo hace ". $PSScriptRoot\..\lib\TestHelpers.ps1" y despues usa
# Assert-Fails / Assert-Succeeds / Get-ScalarValue para armar su lista de
# resultados. run_all.ps1 junta los resultados de todos los modulos.

# Nombre de base de pruebas SEGUN EL ROL de la terminal.
#
# POR QUE EXISTE ESTO. Los nombres de base de prueba eran fijos, asi que dos
# terminales que corrieran la misma suite al mismo tiempo usaban la MISMA
# base. Y estas suites no solo escriben: `build_test_db.ps1` arranca con
# DROP DATABASE. El resultado es que a la terminal de al lado se le borra la
# base a mitad de la corrida. Paso de verdad, en las dos direcciones:
# construccion perdio dos corridas con "Unknown database", y del lado de
# auditoria aparecieron dos tests en rojo que despues, en aislamiento, no se
# reprodujeron.
#
# El rol llega por ASISTO_ROL, la misma variable que usa el hook de
# SessionStart.
#
# SIN ROL NO SE CORRE: esto FALLA, no avisa. La primera version avisaba y
# seguia, y eso es exactamente lo que dejo pasar una sesion entera de
# corridas contra la base de otra terminal sin que nadie lo notara. Un aviso
# en medio de 40 lineas de salida no lo lee nadie; estas suites BORRAN y
# recrean su base, asi que el costo de seguir es destruirle la corrida al de
# al lado.
#
# La salida de escape sigue existiendo y es explicita: quien pase el nombre
# a mano (-TestDbName / -TestDbPrefix / -Database) ni siquiera llega aca.
#
# El mapeo esta duplicado en tests/backend/_entorno.py, que resuelve lo
# mismo del lado de Python para las corridas directas de unittest. Si se
# toca uno hay que tocar el otro. Eso incluye el recorte de espacios de
# abajo: los dos comparan el valor RECORTADO.
function Get-NombreBaseDePrueba {
    param(
        [Parameter(Mandatory)] [string]$Base,
        # Como se pasa el nombre a mano en el script que llama. Cambia entre
        # run_all.ps1 (-TestDbPrefix) y el resto (-TestDbName / -Database).
        [string]$EjemploExplicito = '-TestDbName <nombre>'
    )
    # SE COMPARA RECORTADO, y no es cosmetico. La forma `set VAR=valor &&
    # comando` de CMD guarda el espacio que queda ANTES del `&&`, asi que las
    # tres terminales arrancan con "auditoria " (con espacio al final) sin que
    # eso se vea en ningun lado. Sin el recorte, el fallo duro de abajo rebota
    # en las tres por un caracter invisible, y el mensaje acusa a un valor que
    # a simple vista se lee perfecto.
    #
    # MAYUSCULAS: tampoco distinguen (decision del 2026-08-12). "Auditoria" y
    # "AUDITORIA" son el rol auditoria. No hay ningun caso donde una mayuscula
    # signifique otra cosa, y rechazar un valor valido cuesta una sesion entera
    # de trabajo; aceptarlo no cuesta nada. Los tres lugares que leen la
    # variable convergen a insensible, no a estricto.
    #
    # El .ToLowerInvariant() es explicito aunque el `switch` de PowerShell ya
    # ignore mayusculas por defecto: asi la decision queda ESCRITA y no heredada
    # de un default del lenguaje. Si alguien agrega -CaseSensitive al switch, el
    # comportamiento no cambia. Invariant y no ToLower() a secas para no quedar
    # atado a la cultura de la maquina (la I turca es el caso clasico).
    #
    # Se normalizan espacios y mayusculas, y NADA MAS: no se normalizan acentos
    # ni se aceptan abreviaturas. Un valor realmente invalido tiene que seguir
    # fallando.
    #
    # La interpolacion "$(...)" es para que un ASISTO_ROL ausente no reviente
    # en .Trim(): $null.Trim() es un error en PowerShell 5.1, y el camino "no
    # esta definida" tiene que llegar al mensaje de abajo, no a una excepcion
    # de metodo sobre un valor nulo.
    $rolComoLoEscribieron = "$($env:ASISTO_ROL)".Trim()
    $rol = $rolComoLoEscribieron.ToLowerInvariant()
    switch ($rol) {
        "construccion" { return $Base }
        "auditoria"    { return "${Base}2" }
        "apoyo"        { return "${Base}3" }
    }

    # El valor que se muestra es el RECORTADO PERO SIN CAMBIAR DE CAJA: como lo
    # escribio quien lanzo la terminal, menos los espacios. Mostrar el crudo
    # haria pensar que el espacio es el problema cuando ya no lo es, y mostrarlo
    # en minusculas haria buscar una diferencia de mayusculas que tampoco
    # importa. Un valor de solo espacios cae en la rama "no esta definida", que
    # es lo que es.
    $motivo = if ($rol) {
        "ASISTO_ROL trae un valor desconocido ('$rolComoLoEscribieron')."
    } else {
        "ASISTO_ROL no esta definida."
    }

    # La guia va por Write-Host y el throw lleva una sola linea: si el texto
    # largo va adentro del throw, PowerShell lo imprime dos veces -- una como
    # mensaje y otra dentro del ErrorRecord, reformateado y partido -- y lo
    # que tiene que ser una instruccion de cinco segundos se vuelve ilegible.
    Write-Host ""
    Write-Host $motivo -ForegroundColor Red
    Write-Host ""
    Write-Host "Esta suite BORRA y recrea su base de datos, asi que sin saber el rol de"
    Write-Host "esta terminal no se puede correr: usaria '$Base', que es la del rol"
    Write-Host "CONSTRUCCION, y si esa terminal esta corriendo algo se le borra la base"
    Write-Host "a mitad de camino."
    Write-Host ""
    Write-Host "Definir el rol en esta sesion y volver a correr:"
    Write-Host ""
    Write-Host '    $env:ASISTO_ROL = "auditoria"      # o "construccion" / "apoyo"' -ForegroundColor Cyan
    Write-Host ""
    # El comando de lanzamiento de la terminal NO se imprime aca y no es un
    # detalle de estilo: este archivo esta versionado y sube al repositorio,
    # asi que cualquier cosa que se escriba aca queda publicada. El comando
    # concreto —con su binario, su modelo y sus flags— vive en
    # PROCEDIMIENTOS.md, que es donde lo busca quien lo necesita.
    Write-Host "O arrancar la terminal con el rol ya puesto: el comando exacto esta en"
    Write-Host "PROCEDIMIENTOS.md."
    Write-Host ""
    Write-Host "Si preferis un nombre puntual y sabes lo que haces, pasalo explicito y"
    Write-Host "esto no se ejecuta:"
    Write-Host ""
    Write-Host "    $EjemploExplicito" -ForegroundColor Cyan
    Write-Host ""

    throw "$motivo Ver las instrucciones de arriba."
}

function Get-MysqlExe {
    if ($env:ASISTO_MYSQL_EXE -and (Test-Path $env:ASISTO_MYSQL_EXE)) {
        return $env:ASISTO_MYSQL_EXE
    }
    $cmd = Get-Command mysql -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $candidates = @(
        "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe",
        "C:\Program Files\MySQL\MySQL Server 8.4\bin\mysql.exe",
        "C:\Program Files\MySQL\MySQL Server 9.0\bin\mysql.exe",
        "C:\Program Files\MySQL\MySQL Server 9.1\bin\mysql.exe",
        "C:\xampp\mysql\bin\mysql.exe"
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) { return $c }
    }
    throw "No se encontro mysql.exe. Si esta instalado en una ruta no listada, " + `
          "definir la variable de entorno ASISTO_MYSQL_EXE con la ruta completa."
}

$script:MysqlExe = Get-MysqlExe
$script:LoginPath = "asisto"

# Corre una o mas sentencias SQL contra $Database (o sin base por defecto
# si se omite, util para DROP/CREATE DATABASE). Devuelve exit code, stdout
# y stderr por separado.
#
# OJO: usa Start-Process con redireccion a archivo, NO "mysql ... 2>$file"
# ni "2>&1". En PowerShell 5.1, redirigir el stderr de un ejecutable
# nativo con los operadores de PowerShell lo envuelve en un ErrorRecord y
# lo reformatea con cortes de linea segun el ancho de consola, partiendo
# mensajes largos a la mitad (p.ej. "4 objetivos \r\nactivos" en vez de
# "4 objetivos activos"). Start-Process redirige a nivel de so, sin que
# PowerShell toque el contenido.
function Invoke-Sql {
    param(
        [string]$Database = "",
        [Parameter(Mandatory)] [string]$Sql
    )
    $tmpSql = [System.IO.Path]::GetTempFileName()
    $tmpOut = [System.IO.Path]::GetTempFileName()
    $tmpErr = [System.IO.Path]::GetTempFileName()
    try {
        Set-Content -Path $tmpSql -Value $Sql -Encoding utf8

        $argList = @("--login-path=$script:LoginPath")
        if ($Database) { $argList += $Database }

        $proc = Start-Process -FilePath $script:MysqlExe -ArgumentList $argList `
            -RedirectStandardInput $tmpSql -RedirectStandardOutput $tmpOut -RedirectStandardError $tmpErr `
            -NoNewWindow -Wait -PassThru

        $stdout = Get-Content $tmpOut -Raw -ErrorAction SilentlyContinue
        $stderr = Get-Content $tmpErr -Raw -ErrorAction SilentlyContinue
        [pscustomobject]@{
            ExitCode = $proc.ExitCode
            StdOut   = $(if ($stdout) { $stdout } else { "" })
            StdErr   = $(if ($stderr) { $stderr } else { "" })
        }
    } finally {
        Remove-Item $tmpSql, $tmpOut, $tmpErr -ErrorAction SilentlyContinue
    }
}

function New-TestResult {
    param([string]$Modulo, [string]$Test, [string]$Resultado, [string]$Detalle)
    [pscustomobject]@{
        Modulo    = $Modulo
        Test      = $Test
        Resultado = $Resultado
        Detalle   = $Detalle
    }
}

# Afirma que la sentencia DEBE fallar y que el mensaje de error contiene
# $Contains. Si falla con otro mensaje, o si no falla, es FAIL.
function Assert-Fails {
    param(
        [Parameter(Mandatory)] [string]$Modulo,
        [Parameter(Mandatory)] [string]$Test,
        [Parameter(Mandatory)] [string]$Database,
        [Parameter(Mandatory)] [string]$Sql,
        [Parameter(Mandatory)] [string]$Contains
    )
    $r = Invoke-Sql -Database $Database -Sql $Sql
    if ($r.ExitCode -ne 0 -and $r.StdErr -match [regex]::Escape($Contains)) {
        return New-TestResult $Modulo $Test "PASS" "Rechazado como se esperaba"
    } elseif ($r.ExitCode -ne 0) {
        return New-TestResult $Modulo $Test "FAIL" "Fallo pero con otro mensaje: $($r.StdErr.Trim())"
    } else {
        return New-TestResult $Modulo $Test "FAIL" "No fue rechazado (se esperaba que fallara)"
    }
}

# Afirma que la sentencia DEBE ejecutarse sin error.
function Assert-Succeeds {
    param(
        [Parameter(Mandatory)] [string]$Modulo,
        [Parameter(Mandatory)] [string]$Test,
        [Parameter(Mandatory)] [string]$Database,
        [Parameter(Mandatory)] [string]$Sql
    )
    $r = Invoke-Sql -Database $Database -Sql $Sql
    if ($r.ExitCode -eq 0) {
        return New-TestResult $Modulo $Test "PASS" "Ejecutado sin error"
    } else {
        return New-TestResult $Modulo $Test "FAIL" "Fallo de forma inesperada: $($r.StdErr.Trim())"
    }
}

# Afirma una condicion arbitraria ya evaluada por el llamador (para casos
# que no son "falla / no falla" sino "el dato final quedo bien o mal").
function Assert-True {
    param(
        [Parameter(Mandatory)] [string]$Modulo,
        [Parameter(Mandatory)] [string]$Test,
        [Parameter(Mandatory)] [bool]$Condicion,
        [string]$DetalleOk = "Condicion verificada",
        [string]$DetalleFail = "Condicion no se cumplio"
    )
    if ($Condicion) {
        return New-TestResult $Modulo $Test "PASS" $DetalleOk
    } else {
        return New-TestResult $Modulo $Test "FAIL" $DetalleFail
    }
}

# Ejecuta un SELECT de una sola columna/fila y devuelve el valor como
# string (para armar aserciones sobre datos, no solo sobre errores).
function Get-ScalarValue {
    param(
        [Parameter(Mandatory)] [string]$Database,
        [Parameter(Mandatory)] [string]$Sql
    )
    $r = Invoke-Sql -Database $Database -Sql $Sql
    if ($r.ExitCode -ne 0) {
        throw "Get-ScalarValue fallo: $($r.StdErr.Trim())"
    }
    # Se toma la ULTIMA linea no vacia, no la segunda: si la columna no
    # tiene alias, mysql usa el propio texto de la expresion como
    # encabezado, y ese texto puede ocupar varias lineas si la consulta
    # tenia saltos de linea. La fila de datos siempre es la ultima.
    $lines = $r.StdOut -split "`r?`n" | Where-Object { $_.Trim() -ne "" }
    if ($lines.Count -lt 2) { return $null }
    return $lines[-1].Trim()
}

# =======================================================================
# LA GUARDA CONTRA LA SALIDA VACIA
#
# POR QUE EXISTE, y es la parte que importa mas que las tres funciones:
#
# `mysql` en modo batch ABORTA el lote en el primer error, y ese error sale
# por STDERR. O sea que un `CALL` que falla deja el STDOUT COMPLETAMENTE
# VACIO: el `SELECT` que venia despues nunca llega a correr. La forma que
# estaba repetida en seis archivos --
#
#     ($r.StdOut -split "`r?`n" | Where-Object {...} | Select-Object -Last 1).Trim()
#
# -- devuelve $null en ese caso, y `$null.Trim()` es un error TERMINANTE en
# PowerShell 5.1.
#
# Con `$ErrorActionPreference = "Stop"` (run_all.ps1, linea 30) ese error no
# se queda en el modulo que lo produjo: SE LLEVA EL RUNNER ENTERO. Paso de
# verdad el 2026-09-11. Un cambio de aridad en `p_registrar_sesion` dejo el
# stdout vacio en `pacientes/test_baja_reactivacion.ps1`, el `.Trim()`
# reviento, y los modulos 13 y 14 NUNCA CORRIERON ni se imprimio el RESUMEN.
# Un error de un modulo borro la medicion de los catorce.
#
# Y hay un agravante que es el verdadero motivo de esta seccion: el error
# venia SOLO POR STDERR. El unico lugar donde estaba escrito que habia
# pasado era el stream que nadie miraba. Por eso la regla no es "no revientes
# con null" sino:
#
#   UN ERROR QUE SALE SOLO POR STDERR TIENE QUE DAR UN ROJO CON MENSAJE,
#   NUNCA TIRAR LA SUITE.
#
# Falsado el 2026-09-12: ver la seccion de control positivo en AUDITORIA.md.
# =======================================================================

# Ultima linea no vacia de una salida capturada. NUNCA devuelve $null:
# devuelve "" cuando no hay ninguna, para que el llamador pueda seguir
# usando metodos de string sin reventar.
function Get-UltimaLinea {
    param([AllowNull()] $Salida)
    if ($null -eq $Salida) { return "" }
    # `Receive-Job` devuelve un ARRAY de lineas y `Invoke-Sql` una sola cadena
    # con los saltos adentro. El -join cubre los dos casos: sobre la cadena
    # suelta es un no-op, y sobre el array conserva los cortes. Interpolar
    # con "$Salida" NO sirve aca -- aplastaria el array con espacios, que es
    # justo lo que destruiria la nocion de "ultima linea".
    $texto = @($Salida) -join "`n"
    $lineas = @($texto -split "`r?`n" | Where-Object { $_.Trim() -ne "" })
    if ($lineas.Count -eq 0) { return "" }
    return $lineas[-1].Trim()
}

# Igual que la anterior pero para un resultado de Invoke-Sql: si el stdout
# vino vacio, devuelve el ERROR de stderr en una sola linea en vez de "".
# Asi la asercion que use este valor falla CON el motivo adentro, que es el
# punto entero de la guarda.
function Get-UltimaLineaSql {
    param([Parameter(Mandatory)] $Resultado)
    $ultima = Get-UltimaLinea $Resultado.StdOut
    if ($ultima -ne "") { return $ultima }

    # LA CONTRAPARTIDA DE DEVOLVER EL ERROR EN VEZ DE "", dicha y no
    # escondida: si el llamador afirma con `-match "<texto del dominio>"` y
    # el rechazo vino de un SIGNAL de trigger que lleva ESE MISMO texto, la
    # asercion pasa. Eso no es un verde falso sobre el sistema --el rechazo
    # ocurrio de verdad-- pero si sobre QUE CAPA rechazo. Los llamadores que
    # necesitan distinguir la capa comparan con `-ceq` contra el texto
    # exacto, y el prefijo de abajo rompe esa igualdad a proposito.
    #
    # La alternativa (devolver "") pierde el mensaje, que es exactamente el
    # defecto que esta seccion viene a arreglar. Entre perder el motivo y
    # confundir la capa, se elige lo segundo y se deja escrito.
    $err = ("$($Resultado.StdErr)" -replace "`r?`n", " ").Trim()
    if ($err -ne "") { return "(SIN SALIDA, exit=$($Resultado.ExitCode)) $err" }
    return "(SIN SALIDA NI ERROR, exit=$($Resultado.ExitCode))"
}

# Para los fixtures que leen un id recien creado. Reemplaza la forma
# `[int](($r.StdOut -split ...).Trim())`, que tenia DOS maneras de reventar:
# el `.Trim()` sobre $null y, si eso se arreglaba devolviendo "", el
# `[int]""` que tambien es un error terminante.
#
# Sigue lanzando --un fixture que no se pudo armar no tiene como seguir--
# pero ahora lanza con el motivo puesto, y run_all.ps1 lo atrapa por modulo
# (NO CORRIO) en vez de morirse con el.
function Get-IdDeSalida {
    param(
        [Parameter(Mandatory)] $Resultado,
        [Parameter(Mandatory)] [string]$Que
    )
    $ultima = Get-UltimaLineaSql $Resultado
    $n = 0
    if (-not [int]::TryParse($ultima, [ref]$n)) {
        throw "$Que no devolvio un id utilizable. Respuesta: '$ultima'"
    }
    return $n
}

function Write-ResultsTable {
    # Bug encontrado en esta misma ronda: antes escribia la tabla formateada
    # con una expresion suelta al final de la funcion, y PowerShell la
    # emitia por el stream de salida (no solo la imprimia). Cuando el
    # llamador hace "$todos += & $modulo.ps1", esa cadena de texto se cuela
    # como UN OBJETO MAS en $todos -- no tiene propiedad Resultado, asi que
    # no se cuenta como PASS/FAIL/INFO, pero SI infla $todos.Count. Con 7
    # modulos que llaman a esta funcion, el TOTAL quedaba inflado en 7
    # (39 tests reales -> 46). Write-Host escribe directo a la consola, no
    # al stream de salida, asi que no puede volver a colarse en un return.
    param([Parameter(Mandatory)] $Resultados)
    $texto = $Resultados | Format-Table -AutoSize -Property Modulo, Test, Resultado, Detalle | Out-String -Width 200
    Write-Host $texto
}

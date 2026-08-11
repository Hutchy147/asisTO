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
# SessionStart. Si falta o trae un valor desconocido se usa el nombre base y
# se AVISA: es preferible una corrida ruidosa que una medicion invalida sin
# que nadie se entere.
#
# El mapeo esta duplicado en tests/backend/_entorno.py, que resuelve lo
# mismo del lado de Python para las corridas directas de unittest. Si se
# toca uno hay que tocar el otro.
function Get-NombreBaseDePrueba {
    param(
        [Parameter(Mandatory)] [string]$Base
    )
    $rol = $env:ASISTO_ROL
    switch ($rol) {
        "construccion" { return $Base }
        "auditoria"    { return "${Base}2" }
        "apoyo"        { return "${Base}3" }
        default {
            if ($rol) {
                Write-Host "AVISO: ASISTO_ROL trae un valor desconocido ('$rol')." -ForegroundColor Yellow
            } else {
                Write-Host "AVISO: ASISTO_ROL no esta definida." -ForegroundColor Yellow
            }
            Write-Host ("         Se usa '$Base', que es la base del rol CONSTRUCCION. Si hay otra " +
                        "terminal corriendo esta misma suite, las dos van a usar la misma base y " +
                        "se van a pisar: una le borra la base a la otra a mitad de la corrida.") -ForegroundColor Yellow
            Write-Host "         Para evitarlo: definir ASISTO_ROL (construccion | auditoria | apoyo)." -ForegroundColor Yellow
            return $Base
        }
    }
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

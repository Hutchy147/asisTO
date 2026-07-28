# tests/db/lib/TestHelpers.ps1
#
# Utilidades compartidas por todos los modulos de tests de base de datos.
# Se ejecuta contra una base de pruebas descartable (nunca "asisto"),
# creada por tests/db/setup/build_test_db.ps1.
#
# Cada modulo hace ". $PSScriptRoot\..\lib\TestHelpers.ps1" y despues usa
# Assert-Fails / Assert-Succeeds / Get-ScalarValue para armar su lista de
# resultados. run_all.ps1 junta los resultados de todos los modulos.

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
    param([Parameter(Mandatory)] $Resultados)
    $Resultados | Format-Table -AutoSize -Property Modulo, Test, Resultado, Detalle | Out-String -Width 200
}

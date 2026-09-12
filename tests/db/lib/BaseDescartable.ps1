# tests/db/lib/BaseDescartable.ps1
#
# LA POLITICA DE BASES DESCARTABLES, EN UN SOLO ARCHIVO.
#
# Son dos reglas y salen las dos del mismo incidente: el 2026-08-17 se borro
# `asisto_demo_prueba`, la unica copia de los datos que habia cargado a mano
# una terapeuta ocupacional externa, en una tanda de siete DROP DATABASE que
# barrio seis bases de scratch y esa. Ver AUDITORIA.md, "El grafico de
# Fernando Acosta".
#
#   1. MARCA AL CREAR. Una base descartable se declara descartable DENTRO de
#      si misma, con la tabla `_base_descartable`, en el momento en que la
#      crea el script. Nada mas puede borrarla.
#
#   2. RESPALDO ANTES DE DESTRUIR. Cualquier operacion destructiva sobre una
#      base hace primero un mysqldump completo -- datos, triggers y rutinas.
#
# POR QUE LA MARCA VA ADENTRO Y NO EN UNA LISTA. Una lista externa (un .txt,
# un array en un script, un prefijo de nombre) es exactamente lo que fallo:
# quien borra tiene que acertar a clasificar, y se puede equivocar. La marca
# invierte quien decide -- el permiso lo otorga QUIEN CREO la base, y viaja
# pegado a ella. Una base que nadie marco no se borra, sin importar como se
# llame ni a que se parezca.
#
# POR QUE NO ALCANZA CON CONTAR FILAS ANTES DE BORRAR. Se probo y no sirve:
# esa sesion SI conto las filas, 117 segundos antes del DROP, y dejo
# registrado `asisto 16/631/460/47` contra `asisto_demo_prueba 17/641/469/53`.
# La diferencia estuvo en pantalla y la base se borro igual. Un chequeo que
# depende de que alguien interprete bien un numero en el momento de borrar ya
# fallo una vez.
#
# LIMITES DE LAS DOS, y estan escritos aca a proposito para que no haya que ir
# a buscarlos:
#
#   - LA MARCA ATA SOLO A LOS SCRIPTS DE ESTE REPO. Aquel borrado fue un
#     `mysql -e "DROP DATABASE ..."` directo, escrito a mano en una terminal.
#     NO habria pasado por aca y la marca NO lo habria detenido.
#   - EL RESPALDO CUBRE TAMBIEN AL COMANDO QUE NADIE ESCRIBIO, pero solo si
#     alguien lo corre antes. No previene el borrado equivocado: lo vuelve
#     reversible. Es la unica de las dos que no depende de que quien borra
#     tenga razon.
#   - NINGUNA DE LAS DOS reemplaza al control humano. En aquel caso el pedido
#     terminaba en "Reporta y espera" y el borrado ocurrio sin reportar y sin
#     esperar. Esa regla vive en las convenciones del proyecto y es de
#     construccion, no de este archivo.

# Nombre de la tabla-marca. Va con guion bajo adelante para que no se confunda
# con una tabla del dominio y para que ordene aparte en un SHOW TABLES.
$script:TablaMarca = '_base_descartable'

# Cuantos respaldos se conservan por base. No es historico: es una red para
# deshacer el ultimo error, no un archivo.
$script:RespaldosAConservar = 5


function Get-MysqldumpExe {
    # Mismo criterio que Get-MysqlExe en TestHelpers.ps1: variable de entorno,
    # PATH, y despues las rutas tipicas. Se resuelve aparte y no se deduce de
    # la ruta de mysql.exe porque el fallo tiene que decir QUE falta.
    if ($env:ASISTO_MYSQLDUMP_EXE -and (Test-Path $env:ASISTO_MYSQLDUMP_EXE)) {
        return $env:ASISTO_MYSQLDUMP_EXE
    }
    $cmd = Get-Command mysqldump -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $candidatos = @(
        "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqldump.exe",
        "C:\Program Files\MySQL\MySQL Server 8.4\bin\mysqldump.exe",
        "C:\Program Files\MySQL\MySQL Server 9.0\bin\mysqldump.exe",
        "C:\Program Files\MySQL\MySQL Server 9.1\bin\mysqldump.exe",
        "C:\xampp\mysql\bin\mysqldump.exe"
    )
    foreach ($c in $candidatos) { if (Test-Path $c) { return $c } }
    throw "No se encontro mysqldump.exe. Sin el no se puede respaldar, y sin " + `
          "respaldo no se borra nada. Definir ASISTO_MYSQLDUMP_EXE con la ruta completa."
}


function Get-CarpetaDeRespaldos {
    # Dentro del repo pero gitignoreada: un dump de la base de demostracion
    # tiene nombres y diagnosticos, no va a git ni por accidente.
    $carpeta = Join-Path (Resolve-Path "$PSScriptRoot\..").Path "_respaldos"
    if (-not (Test-Path $carpeta)) {
        New-Item -ItemType Directory -Path $carpeta | Out-Null
    }
    return $carpeta
}


function Get-EscalarSinBase {
    <#
        Un SELECT escalar contra information_schema, SIN conectarse a ninguna
        base en particular.

        Existe porque Get-ScalarValue (TestHelpers.ps1) tiene -Database como
        parametro OBLIGATORIO, y pasarle cadena vacia no es "sin base": es un
        error de binding. Estas consultas tienen que poder correr cuando la
        base ni siquiera existe, que es justamente el caso que se pregunta.
    #>
    param([Parameter(Mandatory)] [string]$Sql)
    $r = Invoke-Sql -Sql $Sql
    if ($r.ExitCode -ne 0) {
        throw "No se pudo consultar el catalogo de MySQL: $($r.StdErr.Trim())"
    }
    $lineas = @($r.StdOut -split "`r?`n" | Where-Object { $_.Trim() -ne "" })
    if ($lineas.Count -lt 2) { return $null }
    return $lineas[-1].Trim()
}


function Test-BaseExiste {
    param([Parameter(Mandatory)] [string]$Database)
    # OJO: information_schema.SCHEMATA se consulta aca para preguntar por UNA
    # base concreta que el llamador ya nombro. NO se enumera para elegir a
    # quien borrar -- esa es justamente la forma que produjo el incidente, y
    # en todo el repo no existe.
    $v = Get-EscalarSinBase -Sql @"
SELECT COUNT(*) FROM information_schema.SCHEMATA WHERE SCHEMA_NAME = '$Database';
"@
    return ([int]$v -gt 0)
}


function Test-BaseTieneMarca {
    param([Parameter(Mandatory)] [string]$Database)
    if (-not (Test-BaseExiste -Database $Database)) { return $false }
    $v = Get-EscalarSinBase -Sql @"
SELECT COUNT(*) FROM information_schema.TABLES
 WHERE TABLE_SCHEMA = '$Database' AND TABLE_NAME = '$script:TablaMarca';
"@
    return ([int]$v -gt 0)
}


function Get-DetalleDeMarca {
    param([Parameter(Mandatory)] [string]$Database)
    if (-not (Test-BaseTieneMarca -Database $Database)) { return $null }
    return Get-ScalarValue -Database $Database -Sql @"
SELECT CONCAT(creada_por, ' el ', creada_en) FROM ``$script:TablaMarca`` LIMIT 1;
"@
}


function Set-MarcaDeBaseDescartable {
    <#
        Estampa la marca. La llama build_test_db.ps1 DESPUES de cargar schema
        y seed -- antes no tendria sentido, porque schema.sql arranca con
        DROP DATABASE y se llevaria la marca puesta.
    #>
    param(
        [Parameter(Mandatory)] [string]$Database,
        [Parameter(Mandatory)] [string]$CreadaPor
    )
    $r = Invoke-Sql -Database $Database -Sql @"
CREATE TABLE IF NOT EXISTS ``$script:TablaMarca`` (
  base       VARCHAR(64)  NOT NULL,
  creada_en  DATETIME     NOT NULL,
  creada_por VARCHAR(255) NOT NULL,
  PRIMARY KEY (base)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
REPLACE INTO ``$script:TablaMarca`` (base, creada_en, creada_por)
  VALUES ('$Database', NOW(), '$CreadaPor');
"@
    if ($r.ExitCode -ne 0) {
        throw "No se pudo estampar la marca de base descartable en $Database : $($r.StdErr)"
    }
}


function Assert-BaseBorrable {
    <#
        El unico permiso de borrado que existe. Sin marca no se sigue.

        NO HAY EXCEPCION POR NOMBRE, y su ausencia es deliberada. Hasta el
        2026-08-19 teardown_test_db.ps1 rechazaba el literal 'asisto' y nada
        mas. Esa forma es la que fallo: `asisto_demo_prueba` no estaba en la
        excepcion, y la proxima base que importe tampoco va a estar. Ahora
        `asisto` se salva por el mismo motivo que cualquier otra base con
        datos que no sean de prueba -- porque nadie la marco.
    #>
    param([Parameter(Mandatory)] [string]$Database)

    if (-not (Test-BaseExiste -Database $Database)) { return }

    if (-not (Test-BaseTieneMarca -Database $Database)) {
        $filas = Get-EscalarSinBase -Sql @"
SELECT IFNULL(SUM(TABLE_ROWS), 0) FROM information_schema.TABLES
 WHERE TABLE_SCHEMA = '$Database';
"@
        throw ("NO SE BORRA '$Database': no tiene la tabla '$script:TablaMarca', asi " +
               "que no la creo ningun script de este repo como base descartable. " +
               "Tiene aproximadamente $filas filas.`n`n" +
               "SI ES UNA BASE DE PRUEBA ANTERIOR AL 2026-08-19 -- creada antes de que " +
               "existiera la marca -- la migracion es de una sola vez:`n" +
               "    cd tests/db`n" +
               "    . .\lib\TestHelpers.ps1 ; . .\lib\BaseDescartable.ps1`n" +
               "    Invoke-RespaldoDeBase -Database '$Database' -Motivo 'migracion a base marcada'`n" +
               "    Invoke-Sql -Sql `"DROP DATABASE ``$Database``;`"`n" +
               "y despues build_test_db.ps1 la recrea marcada. Se recrea en vez de " +
               "marcarla a mano a proposito: una puerta de 'adopcion' seria el mismo " +
               "bypass que esta marca vino a sacar.`n`n" +
               "SI NO ES UNA BASE DE PRUEBA, no la borres: es justo el caso que este " +
               "guardarrail existe para frenar. Ver la nota de arriba en " +
               "tests/db/lib/BaseDescartable.ps1.")
    }
}


function Invoke-RespaldoDeBase {
    <#
        mysqldump completo antes de destruir. Devuelve la ruta del archivo, o
        $null si la base no existia (no hay nada que respaldar).

        LAS OPCIONES NO SON DECORATIVAS:
          --routines          los 5 procedimientos. Sin esto el dump restaura
                              una base que "anda" hasta que alguien llama a
                              p_alta_paciente.
          --triggers          los 8 triggers, que es DONDE VIVEN las 6 reglas
                              de negocio de este proyecto. Viene por defecto,
                              se escribe igual: un dump sin triggers parece
                              completo y es el peor de los respaldos.
          --single-transaction  todo es InnoDB, asi que el dump sale de un
                              snapshot coherente y sin lockear la base.
          --result-file       lo escribe mysqldump, no PowerShell. En 5.1
                              redirigir stdout de un exe nativo reescribe los
                              finales de linea y puede romper un .sql.

        NO se usa --databases a proposito: sin el, el dump no lleva CREATE
        DATABASE ni USE, asi que se puede restaurar en CUALQUIER nombre de
        base. Es lo que permite verificarlo sin tocar el original.
    #>
    param(
        [Parameter(Mandatory)] [string]$Database,
        [string]$Motivo = "sin motivo declarado"
    )

    if (-not (Test-BaseExiste -Database $Database)) { return $null }

    $exe = Get-MysqldumpExe
    $carpeta = Get-CarpetaDeRespaldos
    $sello = Get-Date -Format "yyyyMMdd-HHmmss"
    $destino = Join-Path $carpeta "$Database`_$sello.sql"

    $argumentos = @(
        "--login-path=asisto",
        "--single-transaction",
        "--routines",
        "--triggers",
        "--result-file=$destino",
        $Database
    )
    $tmpErr = [System.IO.Path]::GetTempFileName()
    try {
        $proc = Start-Process -FilePath $exe -ArgumentList $argumentos `
            -RedirectStandardError $tmpErr -NoNewWindow -Wait -PassThru
        $errores = Get-Content $tmpErr -Raw -ErrorAction SilentlyContinue
        if ($proc.ExitCode -ne 0) {
            throw "mysqldump fallo sobre '$Database' (codigo $($proc.ExitCode)): $errores"
        }
    } finally {
        Remove-Item $tmpErr -ErrorAction SilentlyContinue
    }

    if (-not (Test-Path $destino)) {
        throw "mysqldump dijo que anduvo pero no dejo el archivo $destino."
    }
    $tam = (Get-Item $destino).Length
    if ($tam -lt 1024) {
        throw "El respaldo de '$Database' quedo en $tam bytes: es demasiado chico para " +
              "ser un dump con schema. No se sigue con el borrado."
    }

    # Write-Host y NO Write-Output, y no es cosmetico: esta funcion DEVUELVE la
    # ruta del dump, y un Write-Output se cuela como un segundo objeto en el
    # valor de retorno. Lo reproduje escribiendo este archivo -- `$p =
    # Invoke-RespaldoDeBase ...` quedaba como array de dos elementos y el
    # Get-Content siguiente reventaba. Es el mismo defecto que TestHelpers.ps1
    # ya documenta en Write-ResultsTable, en el mismo repo y por segunda vez.
    Write-Host ("Respaldo de '$Database' -> {0} ({1:N0} bytes, motivo: $Motivo)" -f `
        (Split-Path $destino -Leaf), $tam)

    Remove-RespaldosViejos -Database $Database
    return $destino
}


function Remove-RespaldosViejos {
    param(
        [Parameter(Mandatory)] [string]$Database,
        [int]$Conservar = $script:RespaldosAConservar
    )
    $carpeta = Get-CarpetaDeRespaldos
    # El filtro lleva el guion bajo del sello de fecha para que
    # 'asisto_test_audit2' no se coma los respaldos de
    # 'asisto_test_audit2_graficos'.
    $viejos = @(Get-ChildItem -Path $carpeta -Filter "$Database`_*.sql" -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match "^$([regex]::Escape($Database))_\d{8}-\d{6}\.sql$" } |
        Sort-Object Name -Descending | Select-Object -Skip $Conservar)
    foreach ($v in $viejos) { Remove-Item $v.FullName -ErrorAction SilentlyContinue }
}

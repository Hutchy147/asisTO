# tests/frontend/test_observacion_en_pantalla.ps1
#
# LA SONDA DE UI MAS CHICA QUE PUEDE PONERSE EN ROJO.
#
# Afirma UNA sola cosa: un texto guardado en la base APARECE EN LA PANTALLA.
#
# QUE CUBRE: la misma afirmacion sobre DOS columnas distintas, las dos leidas
# en el modal de detalle de sesion al que se llega desde el historial de la
# ficha:
#   - `evoluciones.observaciones`
#   - `sesiones.notas`            (agregada el 2026-08-21)
# Las dos se guardaban desde julio sin mostrarse en ningun lado: es el mismo
# defecto en dos tablas.
#
# QUE NO CUBRE, y hay que decirlo o se lee como si hubiera red donde no hay:
#   - que se vea la PALABRA clinica y nunca el numero;
#   - el objetivo calificado y despues archivado;
#   - la sesion de otro terapeuta y la ausencia del boton de cargar;
#   - la sesion en ausencia;
#   - el token irrompible que desborda;
#   - la regresion de que el historial abra LECTURA mientras el panel y el
#     calendario abren CARGA.
#   Ninguno de esos siete esta probado por nada, en ningun lado.
#
#   Y SOBRE TODO: las otras CUATRO pantallas -- panel, listado de pacientes,
#   calendario y login -- siguen SIN NINGUNA RED. Los "188 PASS de UI sobre
#   Chrome real" de ESTADO.md no existen como suite: eran chequeos hechos a
#   mano dentro de sesiones de construccion, contados en prosa, que nadie
#   puede volver a correr. Ver AUDITORIA.md, seccion del 2026-08-20.
#
# COMO SE CORRE A MANO:
#   cd tests/frontend
#   pnpm install                       # una sola vez: instala playwright-core
#   .\test_observacion_en_pantalla.ps1
#
# CORRE EN SUS PROPIOS PUERTOS (5178 / 5058 por omision) y NO pisa el entorno
# de desarrollo. Levanta su PROPIO backend apuntado a su base descartable,
# porque el de desarrollo apunta a `asisto` y sembrar el caso ahi seria
# escribir en la base real. Desde `66186c9` Vite toma el puerto y el destino
# del proxy de ASISTO_PUERTO_VITE y ASISTO_API_URL, asi que ya no hace falta
# ocupar 5173/5000. Si los puertos elegidos estan ocupados, esto FALLA en vez
# de arriesgarse a hablarle a un backend ajeno.
#
# FALSACION, con los dos interruptores adentro del script y no como ejercicio
# manual: -SembrarSinObservacion y -SembrarSinNotas siembran el mismo caso con
# esa columna vacia. Cada uno tiene que dar ROJO. Una suite que solo se vio en
# verde no prueba nada -- es el mismo defecto que los 188.

param(
    [string]$Database,
    # Puertos PROPIOS, distintos de los de desarrollo (5173/5000). Desde
    # `66186c9` Vite toma el puerto y el destino del proxy de ASISTO_PUERTO_VITE
    # y ASISTO_API_URL, asi que esta sonda ya no obliga a bajar el entorno de
    # desarrollo para correr.
    [int]$PuertoVite = 5178,
    [int]$PuertoApi  = 5058,
    [switch]$SembrarSinObservacion,
    [switch]$SembrarSinNotas,
    [switch]$Verbosa
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\..\db\lib\TestHelpers.ps1"
. "$PSScriptRoot\..\db\lib\BaseDescartable.ps1"

$repoRoot = (Resolve-Path "$PSScriptRoot\..\..").Path

if (-not $PSBoundParameters.ContainsKey('Database')) {
    $Database = (Get-NombreBaseDePrueba -Base "asisto_test_audit" `
        -EjemploExplicito '.\test_observacion_en_pantalla.ps1 -Database mi_base') + "_ui"
}

# El texto que tiene que aparecer en pantalla. Unico e inconfundible a
# proposito: si aparece, llego desde la base y no de un placeholder ni de otro
# caso del seed. Se siembra aca; NO se busca uno que ya exista.
$marca = "SONDA-UI-" + (Get-Date -Format "yyyyMMddHHmmss")
$texto = "$marca toleró el cepillo en antebrazo 3 de 5 intentos"
# Segundo texto, de OTRA tabla: `sesiones.notas`. Mismo origen y mismo defecto
# que la observacion -- se guardaba desde julio y no se mostraba en ninguna
# pantalla -- asi que se afirma igual y por separado.
$notas = "$marca NOTA llegó somnoliento, se acortó a 30 min"

Write-Host ""
Write-Host "=== Sonda de UI: un texto guardado aparece en la pantalla ===" -ForegroundColor Cyan
Write-Host "Base:   $Database"
Write-Host "Puertos: vite $PuertoVite / api $PuertoApi"
Write-Host "Obs.:   $texto"
Write-Host "Notas:  $notas"
if ($SembrarSinObservacion) {
    Write-Host "MODO FALSACION: se siembra SIN observacion. Tiene que dar ROJO." -ForegroundColor Yellow
}
if ($SembrarSinNotas) {
    Write-Host "MODO FALSACION: se siembra SIN notas. Tiene que dar ROJO." -ForegroundColor Yellow
}
Write-Host ""

function Get-ListenersDelPuerto {
    <#
        TODOS los listeners de un puerto TCP. Devuelve una lista (vacia si no
        hay ninguno), no un si/no: el numero es el dato que importa.

        POR QUE NO `Get-NetTCPConnection`, que es lo que habia aca hasta el
        2026-09-08. MIENTE cuando hay mas de un socket en el mismo puerto.
        Medido ese dia en esta maquina, con dos backends vivos a la vez en
        127.0.0.1:5000:

            Get-NetTCPConnection -LocalPort 5000 -State Listen  ->  1 fila (pid 23724)
            netstat -ano, lineas LISTENING de :5000             ->  2 filas (6868 y 23724)

        En Windows `SO_REUSEADDR` deja que dos sockets tomen el mismo puerto, y
        las conexiones nuevas se las lleva el que arranco ultimo. Un chequeo que
        solo ve uno puede dar por LIBRE un puerto con dos duenos, o acusar al pid
        equivocado. Construccion perdio un diagnostico entero con esto
        (ESTADO.md, "backends zombi secuestran el puerto 5000").

        POR QUE NO SE MIRA EL HEADER `Server:` PARA DESEMPATAR: no distingue. El
        2026-09-06 los dos listeners de 5000 decian Python 3.12.10, la misma
        version que el venv del proyecto. La version del interprete no dice con
        quien estas hablando. Lo unico que sirve es contar los sockets ANTES de
        levantar el propio.

        El estado se compara contra LISTENING y ESCUCHANDO porque netstat
        traduce esa columna en algunas configuraciones regionales. En esta
        maquina sale en ingles (medido). Sin filtrar por estado, una conexion
        ESTABLISHED entrante contaria como listener y la sonda se negaria de mas.
    #>
    param([Parameter(Mandatory)] [int]$Puerto)

    $salida = & netstat -ano -p TCP 2>$null
    if (-not $salida) {
        throw ("No se pudo leer la tabla de conexiones con netstat. Sin ese dato no se " +
               "puede saber si el puerto $Puerto esta libre, y esta sonda NO corre a ciegas: " +
               "levantaria su backend encima de uno ajeno apuntado a 'asisto'.")
    }

    $encontrados = @()
    foreach ($linea in $salida) {
        $campos = @(($linea -replace '^\s+', '') -split '\s+')
        if ($campos.Count -lt 5) { continue }
        if ($campos[0] -notmatch '^TCP$') { continue }
        if ($campos[3] -notmatch '^(LISTENING|ESCUCHANDO)$') { continue }

        # El puerto se corta por el ULTIMO ':' y no con un -match sobre la linea
        # entera: `[::1]:5058` tiene cuatro, y un `:5058` suelto tambien pegaria
        # contra la direccion remota o contra un puerto como 50580.
        $local = $campos[1]
        $corte = $local.LastIndexOf(':')
        if ($corte -lt 0) { continue }
        $puertoLocal = 0
        if (-not [int]::TryParse($local.Substring($corte + 1), [ref]$puertoLocal)) { continue }
        if ($puertoLocal -ne $Puerto) { continue }

        $procesoId = 0
        [void][int]::TryParse($campos[4], [ref]$procesoId)
        $nombre = try { (Get-Process -Id $procesoId -ErrorAction Stop).ProcessName } catch { "proceso desconocido" }
        $encontrados += [pscustomobject]@{
            Direccion = $local
            ProcesoId = $procesoId
            Proceso   = $nombre
        }
    }
    return $encontrados
}

# --- 1. Puertos ---------------------------------------------------------
# Los propios, no los de desarrollo. Si estan ocupados esto FALLA en vez de
# seguir: sin puerto propio la sonda terminaria hablandole al backend de
# desarrollo, que apunta a `asisto`, y estaria leyendo la base real.
#
# SE CUENTAN TODOS LOS LISTENERS, no se pregunta "si o no". Dos procesos pueden
# escuchar el mismo puerto a la vez y contesta el ultimo que arranco: si esto
# viera uno solo, alcanzaria con que el zombi fuera el primero para que la sonda
# se creyera duena del puerto y terminara leyendo la base real.
foreach ($puerto in @($PuertoApi, $PuertoVite)) {
    $listeners = @(Get-ListenersDelPuerto -Puerto $puerto)
    if ($listeners.Count -gt 0) {
        $detalle = ($listeners | ForEach-Object {
            "$($_.Direccion) pid $($_.ProcesoId) ($($_.Proceso))"
        }) -join " | "
        throw ("El puerto $puerto tiene $($listeners.Count) listener(s): $detalle. " +
               "Esta sonda levanta su propio backend contra '$Database'; si usara uno ajeno " +
               "podria estar leyendo 'asisto', que es la base real. Elegi otro par con " +
               "-PuertoVite / -PuertoApi, o libera ese puerto.")
    }
}

# --- 2. Base descartable, con marca y respaldo ---------------------------
# build_test_db.ps1 aplica el guardarrail y el respaldo previo por su cuenta.
& "$repoRoot\tests\db\setup\build_test_db.ps1" -TestDbName $Database | Out-Null

$envPath = Join-Path $repoRoot "backend\.env"
if (-not (Test-Path $envPath)) { throw "No se encontro $envPath." }
$lineaUsuario = Get-Content $envPath | Where-Object { $_ -match "^\s*DB_USER\s*=" } | Select-Object -First 1
$dbUserApp = if ($lineaUsuario) { ($lineaUsuario -split '=', 2)[1].Trim() } else { "root" }

if ($dbUserApp -ne "root") {
    $r = Invoke-Sql -Sql @"
GRANT SELECT, INSERT, UPDATE, DELETE, EXECUTE ON ``$Database``.* TO '$dbUserApp'@'localhost';
FLUSH PRIVILEGES;
"@
    if ($r.ExitCode -ne 0) { throw "No se pudo otorgar permisos sobre $Database : $($r.StdErr)" }
}

# Hashes bcrypt reales: sin esto el login del seed no entra.
$python = Join-Path $repoRoot "backend\venv\Scripts\python.exe"
Push-Location (Join-Path $repoRoot "backend")
try {
    $env:DB_NAME = $Database
    $p = Start-Process -FilePath $python -ArgumentList @("scripts\generar_hashes.py", "--aplicar") `
        -NoNewWindow -Wait -PassThru -RedirectStandardOutput ([System.IO.Path]::GetTempFileName())
    if ($p.ExitCode -ne 0) { throw "generar_hashes.py fallo (codigo $($p.ExitCode))" }
} finally {
    Remove-Item Env:\DB_NAME -ErrorAction SilentlyContinue
    Pop-Location
}

# --- 3. El caso, sembrado ------------------------------------------------
# La sesion va en el PASADO y el objetivo se crea ANTES que ella: la regla 7
# rechaza calificar contra un objetivo posterior a la sesion.
$observacion = if ($SembrarSinObservacion) { "NULL" } else { "'$texto'" }
$notasSql    = if ($SembrarSinNotas)       { "NULL" } else { "'$notas'" }
$r = Invoke-Sql -Database $Database -Sql @"
CALL p_alta_paciente('Sonda','Interfaz','2016-04-04',NULL,'HC-SONDA-UI',NULL,@pac,@m);
INSERT INTO objetivos_terapeuticos (id_paciente, descripcion)
  VALUES (@pac, 'SONDA UI objetivo unico de la sonda de interfaz');
SET @obj = LAST_INSERT_ID();
UPDATE objetivos_terapeuticos SET fecha_creacion = DATE_SUB(NOW(), INTERVAL 30 DAY)
 WHERE id = @obj;
CALL p_registrar_sesion(1, @pac, DATE_SUB(CURDATE(), INTERVAL 7 DAY),
                        '11:00:00', '11:45:00', 'completa', NULL, $notasSql, @ses, @m);
CALL p_registrar_evolucion(@ses, @obj, 3, $observacion, 1, @evo, @m);
SELECT @pac, @ses, @evo, @m;
"@
if ($r.ExitCode -ne 0) { throw "No se pudo sembrar el caso: $($r.StdErr)" }
$campos = (($r.StdOut -split "`r?`n" | Where-Object { $_.Trim() -ne "" } | Select-Object -Last 1) -split "`t")
$idPaciente = $campos[0]
if (-not $campos[2] -or $campos[2] -eq 'NULL') {
    throw "La evolucion no se registro. Mensaje del procedimiento: $($campos[3])"
}
Write-Host "Sembrado: paciente $idPaciente, sesion $($campos[1]), evolucion $($campos[2])"

# --- 4. Backend y Vite propios ------------------------------------------
$procesos = @()
$logs = @()
function Start-Servicio {
    # OJO con el nombre del parametro: NO puede llamarse $Args. `$Args` es una
    # variable automatica de PowerShell (los argumentos posicionales de la
    # funcion), asi que declararla como parametro la deja VACIA y
    # Start-Process aborta con "El argumento es NULL". Costo la primera
    # corrida de esta sonda.
    param([string]$Exe, [string[]]$Argumentos, [string]$Dir, [string]$Nombre)
    # Los DOS flujos van a $logs. La primera version mandaba stderr a un temp
    # que nadie leia nunca, asi que cuando el backend no levantaba, el motivo
    # se perdia y quedaba solo "no contestaron a tiempo".
    $out = [System.IO.Path]::GetTempFileName()
    $err = [System.IO.Path]::GetTempFileName()
    $script:logs += $out
    $script:logs += $err
    # El llamador necesita poder leer la salida de UN servicio concreto. Ir por
    # indice dentro de $logs es fragil y ya iba a leer mal: Flask tambien
    # imprime "Running on http://127.0.0.1:<puerto>", asi que buscar el
    # anuncio de Vite en el monton devolvia el puerto del backend.
    $script:ultimoLogSalida = $out
    $p = Start-Process -FilePath $Exe -ArgumentList $Argumentos -WorkingDirectory $Dir `
        -RedirectStandardOutput $out -RedirectStandardError $err `
        -NoNewWindow -PassThru
    Write-Host "  levantado $Nombre (pid $($p.Id))"
    return $p
}

try {
    $env:DB_NAME = $Database
    $env:FLASK_DEBUG = "0"   # sin recargador: si no, deja un proceso hijo colgado
    # No se usa run.py: ese entrypoint fija el puerto 5000 y esta sonda corre
    # en el suyo para no pisar el entorno de desarrollo. El -c de una sola
    # linea levanta la MISMA app (create_app) en el puerto elegido.
    # LAS COMILLAS DOBLES ALREDEDOR DEL -c SON OBLIGATORIAS.
    # Start-Process NO entrecomilla los elementos de -ArgumentList: los une con
    # espacios y se los pasa asi al proceso. Sin las comillas, Python recibia
    # `-c from` y moria con `SyntaxError: invalid syntax` en la linea 1, y lo
    # unico que se veia arriba era "el backend no contesto a tiempo".
    $comandoPython = "from app import create_app; create_app().run(host='127.0.0.1', port=$PuertoApi)"
    $procesos += Start-Servicio -Exe $python `
        -Argumentos @("-c", "`"$comandoPython`"") `
        -Dir (Join-Path $repoRoot "backend") -Nombre "backend :$PuertoApi -> $Database"
    # --host 127.0.0.1 EXPLICITO, y no es cosmetico: por defecto Vite se ata a
    # "localhost", que en Windows resuelve primero a ::1 (IPv6). El servidor
    # quedaba arriba y anunciando http://localhost:5173, pero una peticion a
    # http://127.0.0.1:5173 no encontraba a nadie, asi que la espera se
    # agotaba con los dos servicios perfectamente sanos.
    #
    # El puerto y el destino del proxy van por las variables que expone
    # vite.config.js desde `66186c9`. Se pasan por entorno y no por --port
    # para ejercitar el mismo camino que va a usar cualquiera que las
    # configure.
    $env:ASISTO_PUERTO_VITE = "$PuertoVite"
    $env:ASISTO_API_URL = "http://127.0.0.1:$PuertoApi"
    $procesos += Start-Servicio -Exe "node" `
        -Argumentos @("node_modules\vite\bin\vite.js", "--host", "127.0.0.1") `
        -Dir (Join-Path $repoRoot "frontend") -Nombre "vite :$PuertoVite -> api :$PuertoApi"
    $logVite = $script:ultimoLogSalida

    # Esperar a que los dos contesten. Sin esto la sonda entra a una pagina
    # que todavia no existe y el rojo no significa nada.
    # Se prueban por separado para poder decir CUAL de los dos no contesto.
    # Juntos en un solo try, un fallo del front se reportaba como si fueran
    # los dos.
    $backendOk = $false
    $frontOk = $false
    foreach ($intento in 1..60) {
        Start-Sleep -Milliseconds 500
        if (-not $backendOk) {
            try { $backendOk = (Invoke-WebRequest -Uri "http://127.0.0.1:$PuertoApi/api/health" -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200 } catch { }
        }
        if (-not $frontOk) {
            try { $frontOk = (Invoke-WebRequest -Uri "http://127.0.0.1:$PuertoVite/" -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200 } catch { }
        }
        if ($backendOk -and $frontOk) { break }
    }
    $listo = $backendOk -and $frontOk
    if (-not $listo) {
        Write-Host "  backend responde: $backendOk   vite responde: $frontOk" -ForegroundColor Yellow
    }
    if (-not $listo) {
        # El motivo real esta en los logs de los dos procesos: si no se
        # imprime aca, el fallo dice "no contestaron" y no POR QUE.
        Write-Host "--- salida de los servicios ---" -ForegroundColor Yellow
        foreach ($l in $logs) {
            # Write-Host y no una cadena suelta: una cadena suelta se va por el
            # pipeline y, cuando a este script lo llama run_all.ps1, el
            # diagnostico termina como valor de retorno en vez de en pantalla.
            if (Test-Path $l) { Get-Content $l | Select-Object -Last 20 | ForEach-Object { Write-Host "    $_" } }
        }
        throw "El backend o Vite no contestaron a tiempo."
    }
    # VITE NO TIENE strictPort, y eso hay que atajarlo desde aca.
    # `vite.config.js:39-44` lo dice explicito: no se puso para no cambiar el
    # comportamiento por omision, y "si la sonda lo necesita, que lo pida
    # ella". Lo pedi en AUDITORIA.md; mientras tanto, esto:
    #
    # Sin strictPort, Vite que encuentra su puerto ocupado SALTA al siguiente
    # libre. Con el chequeo previo de puertos eso ya casi no puede pasar, pero
    # si pasara, la sonda le estaria hablando a un servidor AJENO en el puerto
    # que pidio -- que es justo el riesgo que el comentario del config nombra.
    # Asi que se compara el puerto que Vite ANUNCIA contra el que se pidio.
    $anuncio = (Get-Content $logVite -Raw -ErrorAction SilentlyContinue)
    if ($anuncio -and $anuncio -match 'http://127\.0\.0\.1:(\d+)') {
        $puertoReal = [int]$Matches[1]
        if ($puertoReal -ne $PuertoVite) {
            throw ("Vite pidio el puerto $PuertoVite y se quedo con el $puertoReal " +
                   "(no tiene strictPort). Lo que conteste en $PuertoVite es un servidor " +
                   "ajeno, asi que esto NO sigue.")
        }
    }

    Write-Host "  backend y vite responden"
    Write-Host ""

    # --- 5. La sonda -----------------------------------------------------
    $env:SONDA_BASE_URL = "http://127.0.0.1:$PuertoVite"
    $env:SONDA_EMAIL = "laura.fernandez@asisto.local"
    $env:SONDA_CONTRASENA = "asisto2026"   # del seed, publica en el repo
    $env:SONDA_ID_PACIENTE = $idPaciente
    $env:SONDA_TEXTO = $texto
    $env:SONDA_TEXTO_NOTAS = $notas

    $proc = Start-Process -FilePath "node" -ArgumentList @("sonda_observacion_en_pantalla.mjs") `
        -WorkingDirectory $PSScriptRoot -NoNewWindow -Wait -PassThru
    $codigo = $proc.ExitCode
} finally {
    foreach ($p in $procesos) {
        if ($p -and -not $p.HasExited) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue }
    }
    if ($Verbosa) { foreach ($l in $logs) { if (Test-Path $l) { Get-Content $l | Select-Object -Last 15 } } }
    foreach ($l in $logs) { Remove-Item $l -ErrorAction SilentlyContinue }
    foreach ($v in @('DB_NAME','FLASK_DEBUG','ASISTO_PUERTO_VITE','ASISTO_API_URL',
                     'SONDA_BASE_URL','SONDA_EMAIL','SONDA_CONTRASENA','SONDA_ID_PACIENTE',
                     'SONDA_TEXTO','SONDA_TEXTO_NOTAS')) {
        Remove-Item "Env:\$v" -ErrorAction SilentlyContinue
    }
}

Write-Host ""
if ($codigo -eq 0) {
    Write-Host "PASS: 2   FAIL: 0   TOTAL: 2" -ForegroundColor Green
} else {
    # No se afirma cuantas fallaron: el detalle por afirmacion lo imprime la
    # sonda arriba, y poner "FAIL: 2" cuando fallo una sola seria inventar un
    # numero. El total si se sabe.
    Write-Host "FAIL: al menos 1 de 2 afirmaciones (cual, arriba)   TOTAL: 2" -ForegroundColor Red
}
exit $codigo

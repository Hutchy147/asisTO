# tests/frontend/test_observacion_en_pantalla.ps1
#
# LA SONDA DE UI MAS CHICA QUE PUEDE PONERSE EN ROJO.
#
# Afirma UNA sola cosa: un texto guardado en la base APARECE EN LA PANTALLA.
#
# QUE CUBRE:
#   la observacion de una evolucion, cargada en la base, leida en el modal de
#   detalle de sesion al que se llega desde el historial de la ficha.
#
# QUE NO CUBRE, y hay que decirlo o se lee como si hubiera red donde no hay:
#   - las notas de la sesion (`sesiones.notas`), que tienen el mismo origen y
#     el mismo defecto;
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
# LOS PUERTOS 5000 Y 5173 TIENEN QUE ESTAR LIBRES. Esta suite levanta su
# PROPIO backend apuntado a su base descartable, porque el backend de
# desarrollo apunta a `asisto` y sembrar el caso ahi seria escribir en la base
# real. Si los puertos estan ocupados, esto FALLA en vez de correr contra la
# base equivocada. Vite proxea /api a 127.0.0.1:5000 fijo
# (frontend/vite.config.js:13), asi que el backend tiene que estar ahi.
#
# FALSACION: con -SembrarSinObservacion se siembra el mismo caso pero con la
# observacion vacia. Tiene que dar ROJO. Una suite que solo se vio en verde no
# prueba nada -- es el mismo defecto que los 188.

param(
    [string]$Database,
    [switch]$SembrarSinObservacion,
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

Write-Host ""
Write-Host "=== Sonda de UI: un texto guardado aparece en la pantalla ===" -ForegroundColor Cyan
Write-Host "Base:  $Database"
Write-Host "Texto: $texto"
if ($SembrarSinObservacion) {
    Write-Host "MODO FALSACION: se siembra SIN observacion. Tiene que dar ROJO." -ForegroundColor Yellow
}
Write-Host ""

# --- 1. Puertos ---------------------------------------------------------
foreach ($puerto in @(5000, 5173)) {
    $ocupado = Get-NetTCPConnection -LocalPort $puerto -State Listen -ErrorAction SilentlyContinue
    if ($ocupado) {
        throw ("El puerto $puerto esta ocupado. Esta suite levanta su propio backend " +
               "contra '$Database'; si usara el de desarrollo estaria sembrando y leyendo " +
               "en 'asisto', que es la base real. Cerra el backend y Vite de desarrollo " +
               "y volve a correr.")
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
$r = Invoke-Sql -Database $Database -Sql @"
CALL p_alta_paciente('Sonda','Interfaz','2016-04-04',NULL,'HC-SONDA-UI',NULL,@pac,@m);
INSERT INTO objetivos_terapeuticos (id_paciente, descripcion)
  VALUES (@pac, 'SONDA UI objetivo unico de la sonda de interfaz');
SET @obj = LAST_INSERT_ID();
UPDATE objetivos_terapeuticos SET fecha_creacion = DATE_SUB(NOW(), INTERVAL 30 DAY)
 WHERE id = @obj;
CALL p_registrar_sesion(1, @pac, DATE_SUB(CURDATE(), INTERVAL 7 DAY),
                        '11:00:00', '11:45:00', 'completa', NULL, @ses, @m);
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
    $p = Start-Process -FilePath $Exe -ArgumentList $Argumentos -WorkingDirectory $Dir `
        -RedirectStandardOutput $out -RedirectStandardError $err `
        -NoNewWindow -PassThru
    Write-Host "  levantado $Nombre (pid $($p.Id))"
    return $p
}

try {
    $env:DB_NAME = $Database
    $env:FLASK_DEBUG = "0"   # sin recargador: si no, deja un proceso hijo colgado
    $procesos += Start-Servicio -Exe $python -Argumentos @("run.py") `
        -Dir (Join-Path $repoRoot "backend") -Nombre "backend -> $Database"
    # --host 127.0.0.1 EXPLICITO, y no es cosmetico: por defecto Vite se ata a
    # "localhost", que en Windows resuelve primero a ::1 (IPv6). El servidor
    # quedaba arriba y anunciando http://localhost:5173, pero una peticion a
    # http://127.0.0.1:5173 no encontraba a nadie, asi que la espera se
    # agotaba con los dos servicios perfectamente sanos.
    $procesos += Start-Servicio -Exe "node" `
        -Argumentos @("node_modules\vite\bin\vite.js", "--host", "127.0.0.1", "--port", "5173", "--strictPort") `
        -Dir (Join-Path $repoRoot "frontend") -Nombre "vite"

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
            try { $backendOk = (Invoke-WebRequest -Uri "http://127.0.0.1:5000/api/health" -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200 } catch { }
        }
        if (-not $frontOk) {
            try { $frontOk = (Invoke-WebRequest -Uri "http://127.0.0.1:5173/" -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200 } catch { }
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
            if (Test-Path $l) { Get-Content $l | Select-Object -Last 20 | ForEach-Object { "    $_" } }
        }
        throw "El backend o Vite no contestaron a tiempo."
    }
    Write-Host "  backend y vite responden"
    Write-Host ""

    # --- 5. La sonda -----------------------------------------------------
    $env:SONDA_BASE_URL = "http://127.0.0.1:5173"
    $env:SONDA_EMAIL = "laura.fernandez@asisto.local"
    $env:SONDA_CONTRASENA = "asisto2026"   # del seed, publica en el repo
    $env:SONDA_ID_PACIENTE = $idPaciente
    $env:SONDA_TEXTO = $texto

    $proc = Start-Process -FilePath "node" -ArgumentList @("sonda_observacion_en_pantalla.mjs") `
        -WorkingDirectory $PSScriptRoot -NoNewWindow -Wait -PassThru
    $codigo = $proc.ExitCode
} finally {
    foreach ($p in $procesos) {
        if ($p -and -not $p.HasExited) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue }
    }
    if ($Verbosa) { foreach ($l in $logs) { if (Test-Path $l) { Get-Content $l | Select-Object -Last 15 } } }
    foreach ($l in $logs) { Remove-Item $l -ErrorAction SilentlyContinue }
    foreach ($v in @('DB_NAME','FLASK_DEBUG','SONDA_BASE_URL','SONDA_EMAIL','SONDA_CONTRASENA','SONDA_ID_PACIENTE','SONDA_TEXTO')) {
        Remove-Item "Env:\$v" -ErrorAction SilentlyContinue
    }
}

Write-Host ""
if ($codigo -eq 0) {
    Write-Host "PASS: 1   FAIL: 0   TOTAL: 1" -ForegroundColor Green
} else {
    Write-Host "PASS: 0   FAIL: 1   TOTAL: 1" -ForegroundColor Red
}
exit $codigo

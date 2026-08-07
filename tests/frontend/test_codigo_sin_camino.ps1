# tests/frontend/test_codigo_sin_camino.ps1
#
# Barrido de codigo sin camino de usuario: componentes definidos que nunca
# se importan desde otro archivo, y funciones exportadas de un servicio
# que nunca se llaman fuera de su propio archivo.
#
# Nacio de un pedido puntual de auditoria ("la Terminal 1 encontro que un
# componente de aviso quedaba inalcanzable... quiero saber si hay mas de
# esa clase"). El barrido encontro diez: un componente y nueve funciones
# de servicio. Terminal 1 cerro el hallazgo (B3 de AUDITORIA.md): nueve
# eran codigo muerto de una iteracion de diseño anterior y se borraron;
# el decimo (listarEvolucionesDeSesion) resulto ser un camino de usuario
# FALTANTE, no sobrante -- el modal de evolucion no miraba las
# evoluciones ya embebidas y ofrecia elegir un objetivo ya calificado,
# que el servidor siempre rechazaba. Se conecto ese dato en vez de
# conectar el wrapper, que se borro igual.
#
# El test queda como REGRESION, no como hallazgo abierto: vuelve a
# escanear src/ cada vez que se corre, asi que si aparece codigo nuevo
# sin camino (o si alguien reintroduce alguno de los diez), lo va a
# marcar FAIL de nuevo sin que haga falta tocar este archivo.
#
# LIMITE CONOCIDO: el barrido de componentes busca por nombre de archivo
# (asume que el default export se llama igual que el archivo, que es la
# convencion del resto del proyecto). Un archivo con VARIOS exports
# nombrados (como FilaObjetivo.jsx, que exporta ObjetivoActivo y
# ObjetivoArchivado, ninguno llamado "FilaObjetivo") puede dar un falso
# PASS si algun otro import del archivo lo mantiene "referenciado" sin
# que el export puntual se use de verdad. Verificado a mano: hoy
# FilaObjetivo.jsx es el UNICO archivo de componentes con mas de un
# export, y los dos se usan (PacienteFicha.jsx los renderiza). Si se
# agregan mas archivos con varios exports nombrados, revisar a mano.
#
# Los simbolos en $PERMITIDOS estan documentados como reservados a
# proposito (comentario propio en el archivo fuente) y no cuentan como
# hallazgo si aparecen sin referencias -- se listan aparte, como INFO.
#
# Uso:
#   .\test_codigo_sin_camino.ps1

param(
    [string]$FrontendSrc = "$PSScriptRoot\..\..\frontend\src"
)

$ErrorActionPreference = "Stop"
$FrontendSrc = (Resolve-Path $FrontendSrc).Path

# Simbolos que un comentario en su propio archivo marca como reservados
# para uso futuro. No son un hallazgo de codigo abandonado.
$PERMITIDOS = @('listarPacientesConFiltros')

# obtenerPaciente: el endpoint GET /api/pacientes/<id> funciona y esta
# documentado en docs/api-pacientes-objetivos.md; la ficha compone los
# mismos datos desde otras dos llamadas (objetivos + sesiones) en vez de
# usar este wrapper. No es codigo roto ni logica que pueda divergir (no
# hay una segunda copia de ninguna regla): es superficie de API sin
# consumidor propio hoy. Se reporta aparte, como INFO, no como FAIL.
$SOLO_INFO = @('obtenerPaciente')

function Buscar-Referencias {
    param([string]$Simbolo, [string]$ArchivoPropio)
    $patron = "\b$([regex]::Escape($Simbolo))\b"
    $coincidencias = Get-ChildItem -Path $FrontendSrc -Recurse -Include "*.jsx", "*.js" |
        Where-Object { $_.FullName -ne $ArchivoPropio } |
        Select-String -Pattern $patron -SimpleMatch:$false
    return $coincidencias.Count
}

$resultados = @()

# --- Componentes: cada .jsx bajo components/ y pages/, menos index.js ---
$componentes = Get-ChildItem -Path (Join-Path $FrontendSrc "components"), (Join-Path $FrontendSrc "pages") `
    -Recurse -Filter "*.jsx"

foreach ($archivo in $componentes) {
    $nombre = $archivo.BaseName
    $referencias = Buscar-Referencias -Simbolo $nombre -ArchivoPropio $archivo.FullName
    $ruta = $archivo.FullName.Substring($FrontendSrc.Length + 1) -replace '\\', '/'

    if ($referencias -eq 0) {
        $resultados += [pscustomobject]@{
            Modulo = "frontend"; Test = "componente_referenciado__$nombre"
            Resultado = "FAIL"
            Detalle = "src/$ruta no se importa desde ningun otro archivo: no hay ningun camino de usuario que lo renderice."
        }
    } else {
        $resultados += [pscustomobject]@{
            Modulo = "frontend"; Test = "componente_referenciado__$nombre"
            Resultado = "PASS"
            Detalle = "Referenciado $referencias vez/veces fuera de su propio archivo."
        }
    }
}

# --- Funciones exportadas de cada services/*.js, menos api.js (infraestructura base) ---
$servicios = Get-ChildItem -Path (Join-Path $FrontendSrc "services") -Filter "*.js" |
    Where-Object { $_.Name -ne "api.js" }

foreach ($archivo in $servicios) {
    $contenido = Get-Content $archivo.FullName -Raw
    $nombres = [regex]::Matches($contenido, 'export (?:function|const) ([a-zA-Z_][a-zA-Z0-9_]*)') |
        ForEach-Object { $_.Groups[1].Value }

    foreach ($nombre in $nombres) {
        $referencias = Buscar-Referencias -Simbolo $nombre -ArchivoPropio $archivo.FullName
        $ruta = $archivo.FullName.Substring($FrontendSrc.Length + 1) -replace '\\', '/'

        if ($referencias -gt 0) {
            $resultados += [pscustomobject]@{
                Modulo = "frontend"; Test = "export_referenciado__$nombre"
                Resultado = "PASS"
                Detalle = "Referenciado $referencias vez/veces fuera de src/$ruta."
            }
        } elseif ($PERMITIDOS -contains $nombre) {
            $resultados += [pscustomobject]@{
                Modulo = "frontend"; Test = "export_referenciado__$nombre"
                Resultado = "INFO"
                Detalle = "Sin referencias, pero documentado en el propio archivo como reservado para uso futuro (src/$ruta)."
            }
        } elseif ($SOLO_INFO -contains $nombre) {
            $resultados += [pscustomobject]@{
                Modulo = "frontend"; Test = "export_referenciado__$nombre"
                Resultado = "INFO"
                Detalle = "Sin consumidor en el frontend hoy; el endpoint que envuelve sigue funcionando y documentado (src/$ruta)."
            }
        } else {
            $resultados += [pscustomobject]@{
                Modulo = "frontend"; Test = "export_referenciado__$nombre"
                Resultado = "FAIL"
                Detalle = "src/$ruta exporta '$nombre' y no se usa en ningun otro archivo: logica sin ningun camino que la ejercite."
            }
        }
    }
}

$resultados | Format-Table -AutoSize -Property Modulo, Test, Resultado, Detalle | Out-String -Width 220 | Write-Host

$pass = @($resultados | Where-Object { $_.Resultado -eq "PASS" }).Count
$fail = @($resultados | Where-Object { $_.Resultado -eq "FAIL" }).Count
$info = @($resultados | Where-Object { $_.Resultado -eq "INFO" }).Count

# Write-Host y no Write-Output: con Write-Output esta linea se cuela en el
# stream de salida y un llamador que junte el return se la lleva como un
# objeto mas, inflando el TOTAL. Es el mismo defecto que ya documenta
# TestHelpers.ps1 (39 tests que se contaban como 46). Hoy nadie agrega
# este archivo, pero el dia que exista un run_all de frontend lo haria.
Write-Host "PASS: $pass   FAIL: $fail   INFO: $info   TOTAL: $($resultados.Count)"

return $resultados

# tests/frontend/test_texto_libre_en_campos.ps1
#
# Regresion de la decision 14 bis: todo texto libre que viene de la base
# lleva la clase `texto-libre` (o un recorte intencional equivalente).
#
# EL BUG QUE ORIGINA ESTE TEST (ESTADO.md, "El bug del token irrompible"):
# un texto largo SIN espacios no envuelve. El navegador solo corta renglon
# donde hay oportunidad de salto, asi que una secuencia continua se pinta
# FUERA de su caja. Medido: 1312 px de texto saliendo de la tarjeta.
#
# QUE PRUEBA ESTO Y QUE NO. No prueba el layout: es un barrido estatico,
# no hay motor de render aca. Lo que prueba es que cada archivo que
# renderiza uno de los campos de texto libre conocidos declara alguna
# proteccion. Eso NO agarra un desborde real, pero SI agarra al
# componente nuevo que se olvido de la clase, que es exactamente como
# aparecio este bug. Es la opcion 1 de las tres que dejo anotadas
# Terminal 1, y la unica de las tres que cabe sin navegador.
#
# LA OPCION 3 NO SE ESCRIBE, A PROPOSITO. Afirmar
# `document.documentElement.scrollWidth === clientWidth` pasa en VERDE con
# el bug presente: AppLayout envuelve el contenido en un overflow:auto que
# absorbe el desborde y lo convierte en scroll interno. Medido por
# Terminal 1: dio 0 de exceso con el bug adentro. Un test asi promete algo
# que no verifica, que es el mismo defecto de los dos tests de deadlock
# que pasaron sin probar nada. Lo que si lo agarraria es la opcion 2
# (recorrer el DOM elemento por elemento con scrollWidth > clientWidth,
# filtrando overflow-x distinto de visible), y necesita Chrome manejado
# desde el test, que hoy el proyecto no automatiza.
#
# COMO DECIDE SI UN ARCHIVO "RENDERIZA" UN CAMPO. Busca el campo como
# ACCESO A PROPIEDAD (`paciente.nombre_completo`, `objetivo?.descripcion`)
# y descarta los accesos cuyo objeto es un contenedor de estado de
# formulario ($OBJETOS_DE_FORMULARIO): `valores.notas` es un textarea, y
# un textarea envuelve solo. Buscar la propiedad y no la palabra suelta es
# lo que evita que "observaciones tecnicas" dentro de una frase en
# castellano cuente como un campo de la base.
#
# ES UNA APROXIMACION, y conviene decir de que lado se equivoca: se
# equivoca marcando de mas, no de menos. Dos falsos positivos conocidos y
# aceptados:
#   - un acceso a propiedad que no se renderiza sino que alimenta el
#     estado inicial de un formulario (ModalObjetivo linea 30);
#   - una constante local de la UI que se llama igual que un campo de la
#     base (ModalRegistrarSesion linea 169: `estado.descripcion` son
#     textos fijos en castellano, no datos de nadie).
# Los dos caen en archivos que de todos modos hay que mirar por otro
# motivo, asi que hoy no cambian ningun resultado.
#
# LIMITE REAL, y este si puede tapar algo: el barrido conoce los campos
# por su NOMBRE en la base. Un valor que el componente recibe renombrado
# en una prop (`<Aviso nombre={...}>`) deja de matchear. Por eso el
# resultado de este test no reemplaza al barrido visual: lo complementa.
#
# Uso:
#   .\test_texto_libre_en_campos.ps1

param(
    [string]$FrontendSrc = "$PSScriptRoot\..\..\frontend\src"
)

$ErrorActionPreference = "Stop"
$FrontendSrc = (Resolve-Path $FrontendSrc).Path

# Los campos de texto libre que hoy llegan de la base a una pantalla.
$CAMPOS = @(
    'descripcion', 'diagnostico', 'observaciones', 'notas',
    'nombre_completo', 'obra_social', 'nro_historia'
)

# Las tres formas validas de declarar que el texto esta contenido. La
# comparacion es sin distinguir mayusculas a proposito: `noWrap` es la
# prop de MUI y `whiteSpace: 'nowrap'` es la regla CSS equivalente, y las
# dos expresan la misma intencion de recorte.
$MARCADORES = @('texto-libre', 'noWrap', 'textOverflow')

# Objetos que contienen el estado de un formulario. Un acceso contra
# estos es un campo de entrada, no un texto renderizado.
$OBJETOS_DE_FORMULARIO = @('valores', 'inicial', 'formulario')

# Archivos que renderizan un campo pero NO llevan marcador propio porque
# delegan el render en un componente que si lo lleva. Cada entrada dice
# en quien delega: si esa delegacion se rompe, la justificacion queda
# escrita al lado para poder revisarla.
#
# Corresponden a las filas de la tabla de ESTADO.md donde el arreglo se
# aplico en el contenedor y no en el llamador ("arreglado en Dato, no en
# cada llamador", "arreglado en Aviso, cubre los cuatro").
$DELEGADOS = @{
    'pages/Pacientes.jsx' =
        'Delega en PersonCell (nombre_completo, nowrap + ellipsis) y en DataTable (diagnostico con truncar, nro_historia en celda propia; la tabla scrollea dentro de su tarjeta). Los dos figuran como ya cubiertos en ESTADO.md.'
    'components/objetivos/ModalObjetivo.jsx' =
        'El unico render es el subtitulo `nombre_completo · nro_historia`, que arma ModalFormulario y ese componente lleva texto-libre. El acceso de la linea 30 es el valor inicial del formulario, no un render.'
    'components/avisos/AvisoSesionDeOtroTerapeuta.jsx' =
        'Interpola el nombre del terapeuta como children de Aviso, y Aviso lleva texto-libre (ESTADO.md: "arreglado en Aviso, cubre los cuatro").'
}

# Campos que todavia no se renderizan en ningun lado en modo lectura.
# NO es que esten cubiertos: es que no hay donde. Se reportan como INFO
# para que el dia que aparezca la pantalla, el campo ya este en la lista
# y el test lo empiece a exigir solo.
$SIN_RENDER_TODAVIA = @{
    'obra_social' =
        'La columna existe en pacientes desde la migracion del 2026-08-07 pero la ficha todavia no la muestra. Cuando se conecte, el Dato de PacienteFicha ya lleva texto-libre.'
    'notas' =
        'sesiones.notas hoy solo existe como textarea en ModalRegistrarSesion. Es uno de los dos campos de texto libre mas largos del modelo: cuando exista la vista de LECTURA de la sesion, necesita texto-libre.'
    'observaciones' =
        'evoluciones.observaciones hoy solo existe como textarea en ModalCargarEvolucion. Mismo caso que notas: en cuanto haya vista de lectura o historial de evoluciones, necesita texto-libre.'
}

# Saca comentarios de bloque y de linea antes de buscar nada.
#
# NO es cosmetico: sin esto, el comentario que explica POR QUE se puso la
# clase alcanza para que el archivo pase. FilaObjetivo.jsx tiene
# `{/* texto-libre: la descripcion la escribe una persona ... */}` arriba
# del Typography, asi que un archivo al que le saquen las dos clases
# reales y le dejen el comentario seguiria en verde. Descubierto probando
# que este test se pone en rojo cuando corresponde, que era justamente el
# punto de probarlo.
#
# Limite del recorte: un "//" dentro de una cadena (una URL) se come el
# resto de la linea. Solo puede QUITAR texto, nunca inventar una
# coincidencia, asi que empuja hacia marcar de mas, que es el lado seguro.
function Quitar-Comentarios {
    param([string]$Texto)
    # Un comentario de bloque se reemplaza por SUS PROPIOS saltos de linea,
    # no por un espacio: si se colapsara, el "campo:linea" del detalle
    # dejaria de coincidir con el archivo real y mandaria a mirar la linea
    # equivocada.
    $evaluador = [System.Text.RegularExpressions.MatchEvaluator] {
        param($m)
        return ($m.Value -replace '[^\r\n]', '')
    }
    $sinBloques = [regex]::Replace($Texto, '/\*[\s\S]*?\*/', $evaluador)
    return [regex]::Replace($sinBloques, '//[^\r\n]*', ' ')
}

# Devuelve las coincidencias "campo:linea" del archivo, ya filtradas.
function Buscar-CamposRenderizados {
    param([string[]]$Lineas)

    $hallados = @()
    for ($i = 0; $i -lt $Lineas.Count; $i++) {
        foreach ($campo in $CAMPOS) {
            # objeto?.campo / objeto.campo -- se captura el objeto para
            # poder descartar los contenedores de formulario.
            $patron = '([A-Za-z_$][A-Za-z0-9_$]*)\s*\??\.\s*' + [regex]::Escape($campo) + '\b'
            foreach ($m in [regex]::Matches($Lineas[$i], $patron)) {
                if ($OBJETOS_DE_FORMULARIO -contains $m.Groups[1].Value) { continue }
                $hallados += [pscustomobject]@{ Campo = $campo; Linea = $i + 1 }
            }
        }
    }
    return $hallados
}

$resultados = @()

$archivos = Get-ChildItem -Path (Join-Path $FrontendSrc "components"), (Join-Path $FrontendSrc "pages") `
    -Recurse -Filter "*.jsx" | Sort-Object FullName

$camposConAlgunRender = @{}

foreach ($archivo in $archivos) {
    # Se conserva la numeracion original: se reemplaza cada comentario por
    # espacio en su propia linea, no se borran lineas. Asi el "campo:linea"
    # del detalle sigue apuntando al archivo real.
    $lineas = (Quitar-Comentarios (Get-Content $archivo.FullName -Raw)) -split "`r?`n"
    $ruta = $archivo.FullName.Substring($FrontendSrc.Length + 1) -replace '\\', '/'

    $hallados = Buscar-CamposRenderizados -Lineas $lineas
    if ($hallados.Count -eq 0) { continue }

    foreach ($h in $hallados) { $camposConAlgunRender[$h.Campo] = $true }

    $detalleCampos = ($hallados | ForEach-Object { "$($_.Campo):$($_.Linea)" } |
        Sort-Object -Unique) -join ', '

    # Sin comentarios: la clase tiene que estar puesta, no explicada.
    $contenido = $lineas -join "`n"
    $marcadoresPresentes = @($MARCADORES | Where-Object { $contenido -match [regex]::Escape($_) })

    $nombreTest = "texto_libre__" + (($ruta -replace '\.jsx$', '') -replace '[/]', '__')

    if ($marcadoresPresentes.Count -gt 0) {
        $resultados += [pscustomobject]@{
            Modulo = "frontend"; Test = $nombreTest
            Resultado = "PASS"
            Detalle = "Renderiza $detalleCampos y declara: $($marcadoresPresentes -join ', ')."
        }
    } elseif ($DELEGADOS.ContainsKey($ruta)) {
        $resultados += [pscustomobject]@{
            Modulo = "frontend"; Test = $nombreTest
            Resultado = "PASS"
            Detalle = "Renderiza $detalleCampos sin marcador propio, por delegacion justificada. $($DELEGADOS[$ruta])"
        }
    } else {
        $resultados += [pscustomobject]@{
            Modulo = "frontend"; Test = $nombreTest
            Resultado = "FAIL"
            Detalle = "src/$ruta renderiza $detalleCampos y no declara texto-libre, noWrap ni textOverflow, ni delega en un componente que lo lleve. Un token sin espacios en ese dato se pinta fuera de su caja."
        }
    }
}

# --- Campos de la lista que hoy no se renderizan en ningun lado ---------
foreach ($campo in ($SIN_RENDER_TODAVIA.Keys | Sort-Object)) {
    if ($camposConAlgunRender.ContainsKey($campo)) { continue }
    $resultados += [pscustomobject]@{
        Modulo = "frontend"; Test = "texto_libre__pendiente__$campo"
        Resultado = "INFO"
        Detalle = $SIN_RENDER_TODAVIA[$campo]
    }
}

# --- Guarda de la propia lista de marcadores ----------------------------
# Si alguien renombra la clase en theme.js y no toca este archivo, todos
# los PASS de arriba pasarian a medir una cadena que ya no existe. Este
# test es el que avisa.
$temaPath = Join-Path $FrontendSrc "theme\theme.js"
$temaContiene = (Get-Content $temaPath -Raw) -match "'\.texto-libre'"
$resultados += [pscustomobject]@{
    Modulo = "frontend"; Test = "texto_libre__la_clase_existe_en_el_tema"
    Resultado = $(if ($temaContiene) { "PASS" } else { "FAIL" })
    Detalle = $(if ($temaContiene) {
        "theme.js define '.texto-libre': el resto de los tests de este archivo mide algo que existe."
    } else {
        "theme.js ya no define '.texto-libre'. Todos los PASS de este archivo estan midiendo una clase inexistente."
    })
}

$resultados | Format-Table -AutoSize -Property Modulo, Test, Resultado, Detalle | Out-String -Width 220 | Write-Host

$pass = @($resultados | Where-Object { $_.Resultado -eq "PASS" }).Count
$fail = @($resultados | Where-Object { $_.Resultado -eq "FAIL" }).Count
$info = @($resultados | Where-Object { $_.Resultado -eq "INFO" }).Count

# Write-Host y no Write-Output, por el mismo motivo documentado en
# TestHelpers.ps1: Write-Output mete la linea del resumen en el stream de
# salida, y cualquier llamador que haga "$todos += & este.ps1" se la come
# como UN OBJETO MAS. No tiene propiedad Resultado, asi que no suma a
# ningun contador pero SI infla el TOTAL. Verificado aca: daba TOTAL 16
# con 11+1+3 = 15 resultados reales.
Write-Host "PASS: $pass   FAIL: $fail   INFO: $info   TOTAL: $($resultados.Count)"

return $resultados

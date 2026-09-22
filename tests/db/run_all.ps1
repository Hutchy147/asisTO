# tests/db/run_all.ps1
#
# Corre todos los modulos de test, cada uno contra su PROPIA base de
# pruebas descartable recien creada desde backend/database/schema.sql +
# seed.sql. Nunca toca "asisto". Pensado para volver a correrse tal cual
# despues de que Terminal 1 aplique las correcciones de AUDITORIA.md: los
# tests que hoy fallan a proposito (documentando un hallazgo) deberian
# pasar a PASS.
#
# Cada modulo usa su propia base (no una compartida) a proposito: varios
# modulos de "bordes" y "concurrencia" CREAN deliberadamente violaciones
# de las reglas de negocio para probar que existen. Si compartieran base
# con "seed", sus violaciones de prueba contaminarian los chequeos de
# coherencia del seed y se verian como si fueran del seed original,
# cuando en realidad las causo otro modulo. Aislar por base evita ese
# falso positivo sin importar el orden en que se corran los modulos.
#
# Uso:
#   .\run_all.ps1
#   .\run_all.ps1 -TestDbPrefix otro_prefijo -KeepDb
#
# -KeepDb deja las bases de pruebas creadas al terminar (por defecto se
# borran). Util para inspeccionar a mano el resultado de una corrida.

param(
    [string]$TestDbPrefix,
    [switch]$KeepDb
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\lib\TestHelpers.ps1"

# Sin -TestDbPrefix explicito, el prefijo sale del rol de la terminal.
#
# Cada modulo arma su base como "<prefijo>_<modulo>", asi que con el prefijo
# fijo de antes dos terminales corriendo esta suite a la vez se destruian las
# bases entre si: cada modulo arranca con build_test_db.ps1, y ese script
# empieza con DROP DATABASE. El sintoma no era claro -- no un error de
# permisos, sino tests fallando por datos que ya no estaban.
if (-not $PSBoundParameters.ContainsKey('TestDbPrefix')) {
    $TestDbPrefix = Get-NombreBaseDePrueba -Base "asisto_test_audit" `
        -EjemploExplicito '.\run_all.ps1 -TestDbPrefix mi_prefijo'
}
Write-Output "Prefijo de bases de prueba: $TestDbPrefix"

$modulos = @(
    @{ Nombre = "reglas_negocio"; Script = "$PSScriptRoot\reglas_negocio\test_reglas_1_a_6.ps1" },
    @{ Nombre = "bordes";         Script = "$PSScriptRoot\bordes\test_update_delete_gaps.ps1" },
    @{ Nombre = "errores";        Script = "$PSScriptRoot\errores\test_mensajes_error.ps1" },
    @{ Nombre = "rrhh";           Script = "$PSScriptRoot\rrhh\test_contenido_clinico.ps1" },
    @{ Nombre = "seed";           Script = "$PSScriptRoot\seed\test_seed_coherencia.ps1" },
    @{ Nombre = "concurrencia_r1"; Script = "$PSScriptRoot\concurrencia\test_race_regla1_objetivos.ps1" },
    @{ Nombre = "concurrencia_r6"; Script = "$PSScriptRoot\concurrencia\test_race_regla6_sesiones.ps1" },
    @{ Nombre = "concurrencia_evol"; Script = "$PSScriptRoot\concurrencia\test_race_reglas_2_3_4_evoluciones.ps1" },
    @{ Nombre = "regla19";        Script = "$PSScriptRoot\bordes\test_regla19_objetivo_archivado_inmutable.ps1" },
    @{ Nombre = "autorizacion";   Script = "$PSScriptRoot\autorizacion\test_evolucion_autoria_respaldada_en_bd.ps1" },
    @{ Nombre = "asignaciones";   Script = "$PSScriptRoot\asignaciones\test_asignaciones_vigencia.ps1" },
    @{ Nombre = "baja";           Script = "$PSScriptRoot\pacientes\test_baja_reactivacion.ps1" },
    @{ Nombre = "sesiones_baja";  Script = "$PSScriptRoot\sesiones\test_sesiones_paciente_de_baja.ps1" },
    @{ Nombre = "graficos";       Script = "$PSScriptRoot\graficos\test_evolucion_series.ps1" }
)

# CADA MODULO VA ADENTRO DE UN try/catch, Y ESTO NO ES DEFENSIVO POR GUSTO.
#
# Hasta el 2026-09-11 este bucle llamaba al modulo pelado. Con
# `$ErrorActionPreference = "Stop"` de la linea 30, CUALQUIER excepcion sin
# capturar adentro de CUALQUIER modulo mataba el runner entero: los modulos
# que faltaban no corrian y el RESUMEN no se imprimia. Paso de verdad -- un
# `$null.Trim()` en el modulo 12 (`pacientes`) se llevo puestos el 13 y el 14
# y dejo la corrida sin ningun numero final.
#
# Lo que estaba mal no era el `.Trim()`: era que el resultado de trece
# modulos dependiera de que el catorce no tropezara. Un modulo que revienta
# tiene que ser UN rojo, no la perdida de la medicion completa.
#
# Se copia la forma de tests/frontend/run_all.ps1, que ya degradaba limpio
# por esto mismo:
#
#   - el modulo que revienta queda como NO CORRIO, con el mensaje de la
#     excepcion adentro;
#   - NO CORRIO cuenta como rojo, nunca se suma a los PASS ni se omite en
#     silencio (un "se salteo" indistinguible de un "paso" es el defecto
#     original de los 188 de UI);
#   - el bucle sigue con el modulo siguiente.
#
# El `finally` del teardown es la otra mitad. Antes, un modulo que reventaba
# se saltaba su `teardown_test_db.ps1` y dejaba la base colgada; asi quedo
# huerfana `asisto_test_audit_baja` en la corrida del 11/09. Ahora la base se
# destruye igual, que es ademas lo unico que mantiene esa limpieza dentro de
# los scripts del repo en vez de a mano.
$todos = @()
$noCorrieron = @()
foreach ($m in $modulos) {
    $dbModulo = "${TestDbPrefix}_$($m.Nombre)"
    Write-Output ""
    Write-Output "=== $($m.Script) (base: $dbModulo) ==="
    try {
        & "$PSScriptRoot\setup\build_test_db.ps1" -TestDbName $dbModulo
        $todos += & $m.Script -Database $dbModulo
    } catch {
        $motivo = $_.Exception.Message
        Write-Output ""
        Write-Output "  !! El modulo '$($m.Nombre)' NO PUDO TERMINAR: $motivo"
        Write-Output "     Se sigue con el resto; esta corrida NO puede quedar en verde."
        # El modulo caido entra en $todos COMO UNA FILA MAS, y eso importa:
        # este script hace `return $todos`, asi que quien lo llame y cuente
        # PASS/FAIL sobre lo devuelto tiene que VER el modulo que no corrio.
        # Si viviera solo en $noCorrieron, un llamador que mire "FAIL -eq 0"
        # leeria verde una corrida a la que le falta un modulo entero. Es la
        # misma clase de agujero que el "se salteo" indistinguible del "paso".
        $fila = New-TestResult $m.Nombre "(el modulo entero)" "NO CORRIO" $motivo
        $todos += $fila
        $noCorrieron += $fila
    } finally {
        if (-not $KeepDb) {
            # El teardown va en su propio try: si el modulo ya reviento, un
            # segundo error aca taparia el primero, que es el que explica la
            # corrida.
            try { & "$PSScriptRoot\setup\teardown_test_db.ps1" -TestDbName $dbModulo }
            catch { Write-Output "  !! No se pudo destruir '$dbModulo': $($_.Exception.Message)" }
        }
    }
}

Write-Output ""
Write-Output "================ RESUMEN ================"
$todos | Format-Table -AutoSize -Property Modulo, Test, Resultado | Out-String -Width 200 | Write-Output

# El @() NO es cosmetico y esto ya dio un falso verde. Con EXACTAMENTE UNA
# coincidencia, "($todos | Where-Object {...}).Count" devuelve VACIO en
# PowerShell 5.1 -- no 1, y tampoco 0: la expresion no es un array, es el
# objeto suelto, y .Count sobre el no resuelve. Con cero coincidencias si
# devuelve 0, que es lo que hacia parecer que la linea funcionaba.
#
# Consecuencia medida el 2026-08-12: la corrida tenia UN test en rojo y el
# resumen imprimio "PASS: 74   FAIL:    INFO: 4   TOTAL: 79" -- el conteo de
# FAIL en blanco -- y ademas la lista de abajo NO se imprimio, porque
# "$null -gt 0" es falso. El unico rastro del rojo era que 74+4 no llegaba a
# 79. Un test en rojo tiene que gritar, no esconderse en una aritmetica que
# no cierra.
$pass = @($todos | Where-Object { $_.Resultado -eq "PASS" }).Count
$fail = @($todos | Where-Object { $_.Resultado -eq "FAIL" }).Count
$info = @($todos | Where-Object { $_.Resultado -eq "INFO" }).Count
$caidos = @($todos | Where-Object { $_.Resultado -eq "NO CORRIO" }).Count
Write-Output ("PASS: $pass   FAIL: $fail   INFO: $info   NO CORRIO: $caidos   " +
              "TOTAL: $($todos.Count)")

# Red por si algun modulo devuelve algo que no es un resultado (ya paso: una
# tabla formateada colandose por el stream de salida) o un Resultado que no
# es ninguno de los cuatro. Sin esto, esos objetos solo se notan sumando a
# mano.
$clasificados = $pass + $fail + $info + $caidos
if ($clasificados -ne $todos.Count) {
    Write-Output ""
    Write-Output ("ATENCION: $($todos.Count) objetos devueltos y solo $clasificados " +
                  "clasificados como PASS/FAIL/INFO/NO CORRIO. Hay " +
                  "$($todos.Count - $clasificados) objeto(s) que no son resultados " +
                  "o que traen otro valor en Resultado.")
}

if ($fail -gt 0) {
    Write-Output ""
    Write-Output "Tests en FAIL (ver AUDITORIA.md para el detalle de cada hallazgo):"
    $todos | Where-Object { $_.Resultado -eq "FAIL" } | ForEach-Object {
        Write-Output "  - [$($_.Modulo)] $($_.Test)"
    }
}

# Los modulos que no terminaron van DESPUES de los FAIL y con su propio
# encabezado, porque son peor que un rojo: de un modulo que reviento no se
# sabe cuantas afirmaciones quedaron sin hacer. Los numeros de arriba son
# de lo que SI corrio, y sin esta advertencia se leerian como si fueran el
# total -- que es exactamente como un runner caido se disfraza de suite
# chica.
if ($noCorrieron.Count -gt 0) {
    Write-Output ""
    Write-Output "ATENCION: $($noCorrieron.Count) modulo(s) NO TERMINARON. Esto NO es verde,"
    Write-Output "y los PASS/FAIL de arriba son SOLO de los modulos que llegaron al final:"
    $noCorrieron | ForEach-Object {
        Write-Output "  - $($_.Modulo): $($_.Detalle)"
    }
    Write-Output ""
    Write-Output "De un modulo que no termino NO se sabe cuantas afirmaciones quedaron sin"
    Write-Output "hacer: no es 'un test menos', es un pedazo de cobertura de tamano"
    Write-Output "desconocido. Correlo suelto para ver donde se corta."
}

# EL VEREDICTO SALE POR DOS CANALES, Y LOS DOS HACEN FALTA.
#
# Hasta el 2026-09-22 este archivo terminaba en `return $todos` y NADA MAS. O
# sea que el resultado de la suite mas grande de las cuatro existia unicamente
# como texto impreso y como objetos en el pipeline: `$LASTEXITCODE` volvia
# VACIO. Las otras tres suites ya salian con `exit 0` / `exit 1`; esta era la
# unica que no, y es la que mas tarda y mas cubre.
#
# Por que importa, y no es teorico: el README invoca esta suite con
# `powershell -File tests\db\run_all.ps1`, que es exactamente la forma cuyo
# resultado se lee por codigo de salida. Cualquier automatizacion encima -- un
# hook de pre-commit, un workflow -- no tenia de donde leer si paso o fallo
# salvo parseando la salida. Se engancha con el punto 4 de AUDITORIA.md ("no
# hay hook ni CI"): el dia que eso se ataque, esta suite no podia informar.
#
# 1. Los objetos siguen saliendo por el pipeline. NO se cambio por `exit` a
#    secas: el comentario de arriba (linea 105) documenta que quien llame a
#    este script y cuente PASS/FAIL sobre lo devuelto tiene que VER el modulo
#    que no corrio. Emitir `$todos` antes del `exit` conserva ese contrato --
#    lo ya escrito al pipeline le llega igual al llamador.
# 2. El codigo de salida lleva el veredicto. Se copia la forma textual de
#    tests/contratos y tests/frontend, incluido que NO CORRIO pesa igual que
#    FAIL: de un modulo que reviento no se sabe cuantas afirmaciones quedaron
#    sin hacer, asi que para un CI las dos cosas son rojo.
#
# FALSADO EN LAS DOS DIRECCIONES el 2026-09-22, que es la mitad que faltaba:
# un runner que siempre devuelve 0 es indistinguible de uno que anda. Verde ->
# 0; un modulo forzado a FAIL -> 1; un modulo forzado a NO CORRIO -> 1. El
# detalle de las tres corridas esta en AUDITORIA.md.
$todos
if ($fail -gt 0 -or $caidos -gt 0) { exit 1 }
exit 0

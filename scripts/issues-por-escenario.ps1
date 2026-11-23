<#
.SYNOPSIS
    Pasa las issues de GitHub a una por escenario (E01 a E45).

.DESCRIPTION
    Lee scripts/issues-por-escenario.json (cuerpo, estado, labels y milestone de cada escenario;
    la tabla para leer está en docs/issues-por-escenario.md) y:
      1. Crea o actualiza los labels y crea los milestones que falten.
      2. Edita cada issue vieja de la guía para que quede con su primer escenario: título
         («E19 · Reservar turno de extracción»), cuerpo, labels y milestone.
      3. Crea una issue por cada escenario que le sobraba a una issue vieja, en orden de escenario.
      4. Cierra las issues de los escenarios hechos (con el PR en el comentario) y reabre las de
         los que faltan si estaban cerradas.
      5. Comenta en cada issue vieja a qué número pasó cada uno de sus escenarios.
      6. Cierra las issues del 17/11 que ampliaban un escenario («Avisos por el módulo de avisos»
         y «Autorización de la obra social desde su módulo»), si existen, diciendo dónde quedaron.
      7. Deja la correspondencia escenario -> número en scripts/issues-por-escenario.csv.

    Todo lo hace gh con la cuenta con la que hiciste `gh auth login`.
    Se puede volver a correr: reconoce por el título las issues que ya convirtió y no duplica nada.
    Compatible con Windows PowerShell 5.1 y con PowerShell 7.

.PARAMETER Prueba
    Muestra lo que haría, sin crear ni modificar nada en GitHub.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts/issues-por-escenario.ps1 -Prueba
    powershell -ExecutionPolicy Bypass -File scripts/issues-por-escenario.ps1
#>
[CmdletBinding()]
param(
    [switch]$Prueba,
    [string]$Datos = 'scripts/issues-por-escenario.json',
    [string]$Salida = 'scripts/issues-por-escenario.csv'
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$utf8SinBom = New-Object System.Text.UTF8Encoding($false)

# ---------------------------------------------------------------------------------------------
# Labels y milestones (los de la guía)
# ---------------------------------------------------------------------------------------------

$labels = @(
    @{ Nombre = 'area:acceso';   Color = '1d76db'; Descripcion = 'Acceso y alta clínica (E01-E11, E40, E42-E45)' },
    @{ Nombre = 'area:pagos';    Color = '0e8a16'; Descripcion = 'Presupuesto, pagos y cobertura (E13-E18, E41)' },
    @{ Nombre = 'area:turnos';   Color = 'fbca04'; Descripcion = 'Turnos y logística de muestras (E19-E26)' },
    @{ Nombre = 'area:corea';    Color = 'c5def5'; Descripcion = 'Envío a Corea (E28-E31)' },
    @{ Nombre = 'area:analisis'; Color = '5319e7'; Descripcion = 'Análisis y resultados (E12, E27, E32-E35)' },
    @{ Nombre = 'area:gestion';  Color = 'f9d0c4'; Descripcion = 'Gestión médica (E36-E38)' },
    @{ Nombre = 'infra';         Color = '6e7781'; Descripcion = 'Base, configuración, CI y deploy' },
    @{ Nombre = 'integracion';   Color = 'd93f0b'; Descripcion = 'Crea o amplía el cliente de una API externa' }
)

$milestones = @(
    @{ Titulo = 'Control 1 (17/11)'; Fecha = '2026-11-17T12:00:00Z'; Descripcion = 'Control presencial: la base del sistema' },
    @{ Titulo = 'Control 2 (24/11)'; Fecha = '2026-11-24T12:00:00Z'; Descripcion = 'Control virtual: el primer issue de cada integrante y el bot' },
    @{ Titulo = 'Control 3 (1/12)';  Fecha = '2026-12-01T12:00:00Z'; Descripcion = 'Control presencial: el circuito principal' },
    @{ Titulo = 'Entrega (8/12)';    Fecha = '2026-12-08T12:00:00Z'; Descripcion = 'Entrega y defensa de la app' }
)

# ---------------------------------------------------------------------------------------------
# Funciones
# ---------------------------------------------------------------------------------------------

function Invocar-Gh {
    <# Corre gh y devuelve su salida como un solo texto. Lanza un error si gh falla. #>
    param([Parameter(Mandatory)][string[]]$Argumentos)
    # gh escribe avisos en stderr: con Stop, PowerShell 5.1 podría tomarlos como error.
    $preferenciaAnterior = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try { $salida = & gh @Argumentos } finally { $ErrorActionPreference = $preferenciaAnterior }
    if ($LASTEXITCODE -ne 0) {
        throw "Falló: gh $($Argumentos -join ' ')"
    }
    return ($salida -join "`n")
}

function Escribir-Gh {
    <# Como Invocar-Gh, pero en modo prueba solo muestra el comando. #>
    param([Parameter(Mandatory)][string[]]$Argumentos)
    if ($Prueba) {
        Write-Host "      [prueba] gh $($Argumentos -join ' ')" -ForegroundColor DarkGray
        return ''
    }
    return Invocar-Gh -Argumentos $Argumentos
}

function Guardar-Temporal {
    <# Escribe el texto en un archivo temporal UTF-8 sin BOM y devuelve su ruta. #>
    param([Parameter(Mandatory)][string]$Texto)
    $ruta = [System.IO.Path]::GetTempFileName()
    [System.IO.File]::WriteAllText($ruta, $Texto, $utf8SinBom)
    return $ruta
}

function Buscar-Escenario {
    <# La issue que ya es de ese escenario («E19 · ...»), o $null. #>
    param([string]$Codigo)
    $prefijo = "$Codigo · "
    $encontradas = @($script:issuesGh | Where-Object { $_.Titulo.StartsWith($prefijo, [System.StringComparison]::Ordinal) } |
        Sort-Object Numero)
    if ($encontradas.Count -gt 1) {
        Write-Host "    Ojo: hay $($encontradas.Count) issues de $Codigo; se usa #$($encontradas[0].Numero)." -ForegroundColor Yellow
    }
    if ($encontradas.Count -eq 0) { return $null }
    return $encontradas[0]
}

function Buscar-Vieja {
    <# La issue vieja de la guía, por su título («Título» o «Título (E19, E20, E21)»), o $null. #>
    param([string]$Titulo)
    $conEscenarios = "$Titulo ("
    $encontradas = @($script:issuesGh | Where-Object {
            $_.Titulo -eq $Titulo -or $_.Titulo.StartsWith($conEscenarios, [System.StringComparison]::Ordinal)
        } | Sort-Object @{ Expression = { $_.Estado -eq 'OPEN' }; Descending = $true }, @{ Expression = 'Numero'; Descending = $true })
    if ($encontradas.Count -gt 1) {
        $otras = ($encontradas | Select-Object -Skip 1 | ForEach-Object { "#$($_.Numero)" }) -join ', '
        Write-Host "    Ojo: «$Titulo» está repetida; se usa #$($encontradas[0].Numero) y no se tocan $otras." -ForegroundColor Yellow
    }
    if ($encontradas.Count -eq 0) { return $null }
    return $encontradas[0]
}

function Unir {
    <# «a», «a y b», «a, b y c». #>
    param([string[]]$Partes)
    $Partes = @($Partes)
    if ($Partes.Count -le 1) { return ($Partes -join '') }
    return (($Partes[0..($Partes.Count - 2)]) -join ', ') + ' y ' + $Partes[-1]
}

function Texto-Numero {
    param($Numero)
    if ($null -eq $Numero) { return '#(nueva)' }
    return "#$Numero"
}

# ---------------------------------------------------------------------------------------------
# Controles previos
# ---------------------------------------------------------------------------------------------

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw 'No se encontró gh (GitHub CLI). Instalalo y corré gh auth login.'
}
if (-not (Test-Path $Datos)) {
    throw "No se encontró $Datos. Corré el script desde la raíz del repo."
}
$preferenciaAnterior = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
& gh auth status *> $null
$codigoAuth = $LASTEXITCODE
$ErrorActionPreference = $preferenciaAnterior
if ($codigoAuth -ne 0) {
    throw 'gh no está autenticado. Corré gh auth login.'
}
$repo = Invocar-Gh -Argumentos @('repo', 'view', '--json', 'nameWithOwner', '--jq', '.nameWithOwner')
$usuario = Invocar-Gh -Argumentos @('api', 'user', '--jq', '.login')
Write-Host "Repositorio: $repo" -ForegroundColor Cyan
Write-Host "Los cambios quedan a nombre de: $usuario" -ForegroundColor Cyan
if ($Prueba) { Write-Host 'Modo prueba: no se crea ni se modifica nada.' -ForegroundColor Yellow }

$plan = [System.IO.File]::ReadAllText((Resolve-Path $Datos).Path, [System.Text.Encoding]::UTF8) | ConvertFrom-Json
$escenarios = @(foreach ($e in $plan.escenarios) { $e })
$viejas = @(foreach ($v in $plan.viejas) { $v })
$absorbidas = @(foreach ($a in $plan.absorbidas) { $a })
$porCodigo = @{}
foreach ($e in $escenarios) { $porCodigo[$e.codigo] = $e }
Write-Host "Escenarios: $($escenarios.Count) ($(@($escenarios | Where-Object { $_.estado -eq 'hecho' }).Count) hechos)"

# ---------------------------------------------------------------------------------------------
# 1. Labels y milestones
# ---------------------------------------------------------------------------------------------

Write-Host "`n1. Labels y milestones" -ForegroundColor Cyan
foreach ($label in $labels) {
    Escribir-Gh -Argumentos @('label', 'create', $label.Nombre, '--color', $label.Color,
        '--description', $label.Descripcion, '--force') | Out-Null
}
Write-Host "  $($labels.Count) labels al día"
$listaMilestones = ConvertFrom-Json (Invocar-Gh -Argumentos @('api', 'repos/{owner}/{repo}/milestones?state=all&per_page=100'))
$milestonesExistentes = @(foreach ($m in $listaMilestones) { $m.title })
foreach ($ms in $milestones) {
    if ($milestonesExistentes -contains $ms.Titulo) { continue }
    Write-Host "  Se crea el milestone $($ms.Titulo)"
    Escribir-Gh -Argumentos @('api', 'repos/{owner}/{repo}/milestones', '-X', 'POST',
        '-f', "title=$($ms.Titulo)", '-f', "due_on=$($ms.Fecha)",
        '-f', "description=$($ms.Descripcion)") | Out-Null
}

# ---------------------------------------------------------------------------------------------
# 2. Plan: qué issue queda para cada escenario
# ---------------------------------------------------------------------------------------------

Write-Host "`n2. Issues actuales" -ForegroundColor Cyan
$jsonIssues = Invocar-Gh -Argumentos @('issue', 'list', '--state', 'all', '--limit', '1000',
    '--json', 'number,title,state,labels')
$script:issuesGh = @(foreach ($i in (ConvertFrom-Json $jsonIssues)) {
        [pscustomobject]@{
            Numero = [int]$i.number
            Titulo = [string]$i.title
            Estado = [string]$i.state
            Labels = @(foreach ($l in $i.labels) { [string]$l.name })
        }
    })
Write-Host "  $($script:issuesGh.Count) issues en GitHub"

$destino = @{}      # escenario -> issue existente que pasa a ser suya (o $null: se crea)
$antes = @{}        # escenario -> texto de la fila «Antes» del cuerpo
$divisiones = @()   # issues viejas que se dividen, para comentarles al final
$faltantes = @()    # títulos de la guía que no están en GitHub
foreach ($vieja in $viejas) {
    $codigos = @($vieja.escenarios)
    # La issue vieja con su título original o, si el script ya corrió, convertida en el primer escenario.
    $origen = Buscar-Vieja -Titulo $vieja.titulo
    $base = $origen
    if ($null -eq $base) { $base = Buscar-Escenario -Codigo $codigos[0] }
    $tituloGuia = "«$($vieja.titulo)»"
    $lista = Unir -Partes $codigos
    for ($k = 0; $k -lt $codigos.Count; $k++) {
        $codigo = $codigos[$k]
        $ya = Buscar-Escenario -Codigo $codigo
        if ($k -eq 0 -and $null -eq $ya) { $ya = $base }
        $destino[$codigo] = $ya

        if ($null -eq $base) {
            $antes[$codigo] = "En la guía era parte de $tituloGuia, que no estaba en GitHub"
        }
        elseif ($k -gt 0) {
            $antes[$codigo] = "Era parte de #$($base.Numero) $tituloGuia"
        }
        elseif ($codigos.Count -gt 1) {
            $antes[$codigo] = "Esta issue era $tituloGuia ($lista); se dividió en una por escenario"
        }
        else {
            $antes[$codigo] = "Esta issue era $tituloGuia"
        }
    }
    if ($null -ne $origen -and $codigos.Count -gt 1) {
        $divisiones += [pscustomobject]@{ Numero = $origen.Numero; Codigos = $codigos }
    }
    if ($null -ne $origen) { $donde = "#$($origen.Numero)" }
    elseif ($null -ne $base) { $donde = "#$($base.Numero) (ya convertida)" }
    else { $donde = 'NO ESTÁ EN GITHUB'; $faltantes += $vieja.titulo }
    Write-Host ("  {0,-64} {1,-22} -> {2}" -f $vieja.titulo, $donde, $lista)
}
if ($faltantes.Count -gt 0) {
    Write-Host "`n  Ojo: $($faltantes.Count) issues de la guía no están en GitHub con su título; sus escenarios se crean de cero:" -ForegroundColor Yellow
    foreach ($t in $faltantes) { Write-Host "    «$t»" -ForegroundColor Yellow }
    Write-Host '  Si alguna sí existe pero con otro título, cortá acá y renombrala antes de seguir.' -ForegroundColor Yellow
    if (-not $Prueba) {
        $respuesta = Read-Host '  ¿Seguir igual? (s/n)'
        if ($respuesta -notmatch '^[sS]') { Write-Host 'No se cambió nada.'; exit 1 }
    }
}

# ---------------------------------------------------------------------------------------------
# 3. Editar las que ya existen y crear las nuevas (en orden de escenario)
# ---------------------------------------------------------------------------------------------

$resultado = @{}    # escenario -> número
$filas = @()
$contador = @{ editadas = 0; creadas = 0; cerradas = 0; reabiertas = 0 }

function Aplicar-Estado {
    param($Escenario, $Numero, [string]$EstadoActual)
    if ($Escenario.estado -eq 'hecho' -and $EstadoActual -ne 'CLOSED') {
        $prs = Unir -Partes @($Escenario.prs)
        Escribir-Gh -Argumentos @('issue', 'close', "$Numero", '--reason', 'completed',
            '--comment', "Hecho: PR $prs, mergeado en development.") | Out-Null
        $script:contador.cerradas++
        return 'cerrada'
    }
    if ($Escenario.estado -ne 'hecho' -and $EstadoActual -eq 'CLOSED') {
        Escribir-Gh -Argumentos @('issue', 'reopen', "$Numero", '--comment',
            'Se reabre: este escenario todavía no está hecho.') | Out-Null
        $script:contador.reabiertas++
        return 'reabierta'
    }
    if ($EstadoActual -eq 'CLOSED') { return 'cerrada' }
    return 'abierta'
}

Write-Host "`n3. Issues por escenario" -ForegroundColor Cyan
$ordenados = @($escenarios | Sort-Object codigo)
# Primero las que se editan y después las que se crean, para que las nuevas queden numeradas en
# el orden de los escenarios.
$aEditar = @($ordenados | Where-Object { $null -ne $destino[$_.codigo] })
$aCrear = @($ordenados | Where-Object { $null -eq $destino[$_.codigo] })

foreach ($e in $aEditar) {
    $issue = $destino[$e.codigo]
    $cuerpo = $e.cuerpo.Replace('{{ANTES}}', $antes[$e.codigo])
    $archivo = Guardar-Temporal -Texto $cuerpo
    try {
        $argumentos = @('issue', 'edit', "$($issue.Numero)", '--title', $e.titulo, '--body-file', $archivo,
            '--milestone', $e.milestone)
        $deseados = @($e.labels)
        $agregar = @($deseados | Where-Object { $issue.Labels -notcontains $_ })
        $sacar = @($issue.Labels | Where-Object { $deseados -notcontains $_ })
        if ($agregar.Count -gt 0) { $argumentos += @('--add-label', ($agregar -join ',')) }
        if ($sacar.Count -gt 0) { $argumentos += @('--remove-label', ($sacar -join ',')) }
        Escribir-Gh -Argumentos $argumentos | Out-Null
    }
    finally {
        Remove-Item $archivo -ErrorAction SilentlyContinue
    }
    $contador.editadas++
    $estado = Aplicar-Estado -Escenario $e -Numero $issue.Numero -EstadoActual $issue.Estado
    $resultado[$e.codigo] = $issue.Numero
    Write-Host ("  #{0,-4} {1}  (editada, {2})" -f $issue.Numero, $e.titulo, $estado)
    $filas += [pscustomobject]@{ Escenario = $e.codigo; GitHub = $issue.Numero; Titulo = $e.titulo
        Estado = $e.estado; Responsable = $e.responsable; Accion = 'editada' }
}

foreach ($e in $aCrear) {
    $cuerpo = $e.cuerpo.Replace('{{ANTES}}', $antes[$e.codigo])
    $archivo = Guardar-Temporal -Texto $cuerpo
    try {
        $argumentos = @('issue', 'create', '--title', $e.titulo, '--body-file', $archivo,
            '--milestone', $e.milestone)
        foreach ($etiqueta in @($e.labels)) { $argumentos += @('--label', $etiqueta) }
        $url = Escribir-Gh -Argumentos $argumentos
    }
    finally {
        Remove-Item $archivo -ErrorAction SilentlyContinue
    }
    $contador.creadas++
    if ($Prueba) {
        $numero = $null
        $estado = if ($e.estado -eq 'hecho') { 'se cierra' } else { 'abierta' }
        if ($e.estado -eq 'hecho') { $contador.cerradas++ }
    }
    elseif ($url -match '/issues/(\d+)') {
        $numero = [int]$Matches[1]
        $estado = Aplicar-Estado -Escenario $e -Numero $numero -EstadoActual 'OPEN'
    }
    else {
        throw "No se pudo leer el número de la issue creada: $url"
    }
    $resultado[$e.codigo] = $numero
    Write-Host ("  {0,-5} {1}  (nueva, {2})" -f (Texto-Numero $numero), $e.titulo, $estado)
    $filas += [pscustomobject]@{ Escenario = $e.codigo; GitHub = $numero; Titulo = $e.titulo
        Estado = $e.estado; Responsable = $e.responsable; Accion = 'creada' }
}

# ---------------------------------------------------------------------------------------------
# 4. Comentarios en las issues que se dividieron
# ---------------------------------------------------------------------------------------------

Write-Host "`n4. Aviso en las issues que se dividieron" -ForegroundColor Cyan
foreach ($d in $divisiones) {
    $codigos = @($d.Codigos)
    $resto = @($codigos | Select-Object -Skip 1 | ForEach-Object { "$_ pasó a $(Texto-Numero $resultado[$_])" })
    $texto = "Se dividió en una issue por escenario. Esta queda para $($codigos[0]); $(Unir -Partes $resto)."
    Write-Host "  #$($d.Numero): $texto"
    Escribir-Gh -Argumentos @('issue', 'comment', "$($d.Numero)", '--body', $texto) | Out-Null
}
if ($divisiones.Count -eq 0) { Write-Host '  Ninguna (ya estaban divididas).' }

# ---------------------------------------------------------------------------------------------
# 5. Issues del 17/11 que ampliaban un escenario
# ---------------------------------------------------------------------------------------------

Write-Host "`n5. Ampliaciones que se unifican con su escenario" -ForegroundColor Cyan
foreach ($a in $absorbidas) {
    $issue = Buscar-Vieja -Titulo $a.titulo
    if ($null -eq $issue) {
        Write-Host "  «$($a.titulo)»: no está en GitHub, nada que hacer"
        continue
    }
    if ($issue.Estado -eq 'CLOSED') {
        Write-Host "  #$($issue.Numero) «$($a.titulo)»: ya estaba cerrada"
        continue
    }
    $destinos = Unir -Partes @(foreach ($c in @($a.escenarios)) { "$c ($(Texto-Numero $resultado[$c]))" })
    $prs = @($a.prs)
    if ($prs.Count -gt 0) {
        # Ya estaba hecha: se cierra como completada.
        $texto = "Hecho en el PR $(Unir -Partes $prs). Se unificó en $($destinos): las issues pasaron a ser una por escenario."
        $razon = 'completed'
    }
    else {
        $texto = "Se unificó en $($destinos): las issues pasaron a ser una por escenario."
        $razon = 'not planned'
    }
    Write-Host "  #$($issue.Numero): $texto"
    Escribir-Gh -Argumentos @('issue', 'close', "$($issue.Numero)", '--reason', $razon,
        '--comment', $texto) | Out-Null
}

# ---------------------------------------------------------------------------------------------
# 6. Correspondencia
# ---------------------------------------------------------------------------------------------

Write-Host "`nResumen: $($contador.editadas) editadas, $($contador.creadas) nuevas, $($contador.cerradas) cerradas como hechas, $($contador.reabiertas) reabiertas." -ForegroundColor Green
if ($Prueba) {
    Write-Host "En modo prueba no se escribe $Salida."
}
else {
    $filas | Sort-Object Escenario | Select-Object Escenario, GitHub, Titulo, Estado, Responsable, Accion |
        Export-Csv -Path $Salida -NoTypeInformation -Encoding UTF8
    Write-Host "Correspondencia guardada en $Salida"
}
Write-Host 'Listo. Para ver las que faltan: gh issue list --state open' -ForegroundColor Green

<#
.SYNOPSIS
    Carga en GitHub los labels, los milestones y los issues de docs/guia-issues.md.

.DESCRIPTION
    Lee la guía y no duplica su contenido:
      - la tabla de la sección 3, entre <!-- tabla-issues --> y <!-- fin tabla-issues -->;
      - el cuerpo de cada issue de la sección 5, entre <!-- issue:N --> y <!-- /issue:N -->.
    Crea o actualiza los labels, crea los milestones que falten y crea los issues en orden,
    sin asignar. Si un issue con el mismo título ya existe, lo saltea.
    Si GitHub asigna números distintos de los de la guía, reescribe las referencias #N y los
    nombres de rama de cada cuerpo con los números reales.
    Deja la correspondencia en scripts/issues-creados.csv.

    Correrlo desde la raíz del repo, con `gh auth login` hecho y antes de abrir otro issue o PR.
    Compatible con Windows PowerShell 5.1 y con PowerShell 7.

.PARAMETER Prueba
    Muestra lo que haría, sin crear ni modificar nada en GitHub.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts/crear_issues.ps1 -Prueba
    powershell -ExecutionPolicy Bypass -File scripts/crear_issues.ps1
#>
[CmdletBinding()]
param(
    [switch]$Prueba,
    [string]$Guia = 'docs/guia-issues.md',
    [string]$Salida = 'scripts/issues-creados.csv'
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$utf8SinBom = New-Object System.Text.UTF8Encoding($false)

# ---------------------------------------------------------------------------------------------
# Datos fijos: labels y milestones (sección 2 de la guía)
# ---------------------------------------------------------------------------------------------

$labels = @(
    @{ Nombre = 'area:acceso';   Color = '1d76db'; Descripcion = 'Acceso y alta clínica (E01-E11, E40)' },
    @{ Nombre = 'area:pagos';    Color = '0e8a16'; Descripcion = 'Presupuesto, pagos y cobertura (E13-E18, E41)' },
    @{ Nombre = 'area:turnos';   Color = 'fbca04'; Descripcion = 'Turnos y logística de muestras (E19-E26)' },
    @{ Nombre = 'area:corea';    Color = 'c5def5'; Descripcion = 'Envío a Corea (E28-E31)' },
    @{ Nombre = 'area:analisis'; Color = '5319e7'; Descripcion = 'Análisis y resultados (E12, E27, E32-E35)' },
    @{ Nombre = 'area:gestion';  Color = 'f9d0c4'; Descripcion = 'Gestión médica (E36-E38)' },
    @{ Nombre = 'infra';         Color = '6e7781'; Descripcion = 'Base, configuración, CI y deploy' },
    @{ Nombre = 'integracion';   Color = 'd93f0b'; Descripcion = 'Crea o amplía el cliente de una API externa' },
    @{ Nombre = 'tests';         Color = 'bfd4f2'; Descripcion = 'Solo tests' },
    @{ Nombre = 'docs';          Color = '0075ca'; Descripcion = 'Solo documentación' },
    @{ Nombre = 'bug';           Color = 'd73a4a'; Descripcion = 'Algo que no anda en develop' }
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
    # gh escribe avisos de progreso en stderr: con Stop, PowerShell 5.1 podría tomarlos como error.
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
        Write-Host "    [prueba] gh $($Argumentos -join ' ')" -ForegroundColor DarkGray
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

function Renumerar {
    <# Reemplaza #N y el prefijo de rama `N- por el número real que asignó GitHub. #>
    param([string]$Texto, [hashtable]$Mapa)
    $referencia = {
        param($m)
        $n = [int]$m.Groups[1].Value
        if ($Mapa.ContainsKey($n)) { return "#$($Mapa[$n])" }
        return $m.Value
    }.GetNewClosure()
    $rama = {
        param($m)
        $n = [int]$m.Groups[1].Value
        if ($Mapa.ContainsKey($n)) { return "$($Mapa[$n])" }
        return $m.Value
    }.GetNewClosure()
    $Texto = [regex]::Replace($Texto, '(?<![\w#&/])#(\d+)\b', [System.Text.RegularExpressions.MatchEvaluator]$referencia)
    $Texto = [regex]::Replace($Texto, '(?<=`)(\d+)(?=-[a-z])', [System.Text.RegularExpressions.MatchEvaluator]$rama)
    return $Texto
}

# ---------------------------------------------------------------------------------------------
# Controles previos
# ---------------------------------------------------------------------------------------------

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw 'No se encontró gh (GitHub CLI). Instalalo y corré gh auth login.'
}
if (-not (Test-Path $Guia)) {
    throw "No se encontró $Guia. Corré el script desde la raíz del repo."
}
# En PowerShell 5.1, con ErrorActionPreference = Stop, cualquier línea que gh escriba en stderr
# corta el script. Por eso este chequeo corre con Continue y se mira solo el código de salida.
$preferenciaAnterior = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
& gh auth status *> $null
$codigoAuth = $LASTEXITCODE
$ErrorActionPreference = $preferenciaAnterior
if ($codigoAuth -ne 0) {
    throw 'gh no está autenticado. Corré gh auth login.'
}
$repo = Invocar-Gh -Argumentos @('repo', 'view', '--json', 'nameWithOwner', '--jq', '.nameWithOwner')
Write-Host "Repositorio: $repo" -ForegroundColor Cyan
if ($Prueba) { Write-Host 'Modo prueba: no se crea ni se modifica nada.' -ForegroundColor Yellow }

# ---------------------------------------------------------------------------------------------
# Leer la guía
# ---------------------------------------------------------------------------------------------

$texto = [System.IO.File]::ReadAllText((Resolve-Path $Guia).Path, [System.Text.Encoding]::UTF8)

$bloqueTabla = [regex]::Match($texto, '(?s)<!-- tabla-issues -->(.*?)<!-- fin tabla-issues -->')
if (-not $bloqueTabla.Success) { throw 'No se encontró la tabla de issues (marcas tabla-issues).' }

$issues = @()
foreach ($fila in [regex]::Matches($bloqueTabla.Groups[1].Value, '(?m)^\|\s*#(\d+)\s*\|(.+)\|\s*$')) {
    $numero = [int]$fila.Groups[1].Value
    $columnas = @($fila.Groups[2].Value.Split('|') | ForEach-Object { $_.Trim() })
    if ($columnas.Count -ne 8) {
        throw "La fila del issue #$numero tiene $($columnas.Count) columnas después del número y se esperaban 8."
    }
    $titulo, $escenarios, $area, $puntos, $rama, $depende, $responsable, $milestone = $columnas

    $etiquetas = @([regex]::Matches($area, '`([^`]+)`') | ForEach-Object { $_.Groups[1].Value })
    if ($escenarios -match '^E\d') { $tituloGitHub = "$titulo ($escenarios)" } else { $tituloGitHub = $titulo }

    $seccion = [regex]::Match($texto, "(?s)<!-- issue:$numero -->(.*?)<!-- /issue:$numero -->")
    if (-not $seccion.Success) { throw "No se encontró el detalle del issue #$numero (marcas issue:$numero)." }
    $cuerpo = $seccion.Groups[1].Value.Trim()
    $cuerpo += "`n`n---`n_Generado desde ``docs/guia-issues.md``. Responsable según el reparto de la guía: $responsable. Puntos: $puntos._"

    $issues += [pscustomobject]@{
        Numero    = $numero
        Titulo    = $tituloGitHub
        Etiquetas = $etiquetas
        Milestone = $milestone
        Cuerpo    = $cuerpo
    }
}
if ($issues.Count -eq 0) { throw 'La tabla de issues está vacía.' }
$issues = @($issues | Sort-Object Numero)
Write-Host "Issues en la guía: $($issues.Count) (#$($issues[0].Numero) a #$($issues[-1].Numero))"

# Cada label y milestone que usan los issues tiene que estar definido arriba.
$nombresLabels = @($labels | ForEach-Object { $_.Nombre })
$titulosMilestones = @($milestones | ForEach-Object { $_.Titulo })
foreach ($issue in $issues) {
    foreach ($etiqueta in $issue.Etiquetas) {
        if ($nombresLabels -notcontains $etiqueta) { throw "El issue #$($issue.Numero) usa el label desconocido '$etiqueta'." }
    }
    if ($titulosMilestones -notcontains $issue.Milestone) {
        throw "El issue #$($issue.Numero) usa el milestone desconocido '$($issue.Milestone)'."
    }
}

# ---------------------------------------------------------------------------------------------
# 1. Labels
# ---------------------------------------------------------------------------------------------

Write-Host "`n1. Labels" -ForegroundColor Cyan
foreach ($label in $labels) {
    Write-Host "  $($label.Nombre)"
    Escribir-Gh -Argumentos @('label', 'create', $label.Nombre, '--color', $label.Color,
        '--description', $label.Descripcion, '--force') | Out-Null
}

# ---------------------------------------------------------------------------------------------
# 2. Milestones
# ---------------------------------------------------------------------------------------------

Write-Host "`n2. Milestones" -ForegroundColor Cyan
$jsonMilestones = Invocar-Gh -Argumentos @('api', 'repos/{owner}/{repo}/milestones?state=all&per_page=100')
# En PowerShell 5.1, ConvertFrom-Json devuelve el arreglo entero como un solo objeto: se recorre con foreach.
$listaMilestones = ConvertFrom-Json $jsonMilestones
$milestonesExistentes = @(foreach ($m in $listaMilestones) { $m.title })
foreach ($ms in $milestones) {
    if ($milestonesExistentes -contains $ms.Titulo) {
        Write-Host "  $($ms.Titulo): ya existe"
        continue
    }
    Write-Host "  $($ms.Titulo): se crea"
    Escribir-Gh -Argumentos @('api', 'repos/{owner}/{repo}/milestones', '-X', 'POST',
        '-f', "title=$($ms.Titulo)", '-f', "due_on=$($ms.Fecha)",
        '-f', "description=$($ms.Descripcion)") | Out-Null
}

# ---------------------------------------------------------------------------------------------
# 3. Issues
# ---------------------------------------------------------------------------------------------

Write-Host "`n3. Issues" -ForegroundColor Cyan
$jsonIssues = Invocar-Gh -Argumentos @('issue', 'list', '--state', 'all', '--limit', '500', '--json', 'number,title')
$existentes = @{}
$listaIssues = ConvertFrom-Json $jsonIssues
foreach ($i in $listaIssues) { $existentes[$i.title] = [int]$i.number }

$mapa = @{}          # número en la guía -> número en GitHub
$creados = @()
foreach ($issue in $issues) {
    if ($existentes.ContainsKey($issue.Titulo)) {
        $real = $existentes[$issue.Titulo]
        Write-Host "  #$($issue.Numero) ya existe como #$real : $($issue.Titulo)"
        $mapa[$issue.Numero] = $real
        $creados += [pscustomobject]@{ Guia = $issue.Numero; GitHub = $real; Titulo = $issue.Titulo; Nuevo = $false }
        continue
    }

    $archivo = Guardar-Temporal -Texto $issue.Cuerpo
    try {
        $argumentos = @('issue', 'create', '--title', $issue.Titulo, '--body-file', $archivo,
            '--milestone', $issue.Milestone)
        foreach ($etiqueta in $issue.Etiquetas) { $argumentos += @('--label', $etiqueta) }
        $url = Escribir-Gh -Argumentos $argumentos
    }
    finally {
        Remove-Item $archivo -ErrorAction SilentlyContinue
    }

    if ($Prueba) {
        $real = $issue.Numero
    }
    elseif ($url -match '/issues/(\d+)') {
        $real = [int]$Matches[1]
    }
    else {
        throw "No se pudo leer el número del issue creado: $url"
    }
    $aviso = ''
    if ($real -ne $issue.Numero) { $aviso = "  (en la guía es #$($issue.Numero))" }
    Write-Host "  #$real $($issue.Titulo)$aviso"
    $mapa[$issue.Numero] = $real
    $creados += [pscustomobject]@{ Guia = $issue.Numero; GitHub = $real; Titulo = $issue.Titulo; Nuevo = $true }
}

# ---------------------------------------------------------------------------------------------
# 4. Renumerar las referencias si GitHub asignó otros números
# ---------------------------------------------------------------------------------------------

$distintos = @($creados | Where-Object { $_.Guia -ne $_.GitHub })
if ($distintos.Count -gt 0) {
    Write-Host "`n4. Renumerar referencias: $($distintos.Count) issues tienen otro número en GitHub" -ForegroundColor Yellow
    foreach ($issue in $issues) {
        $fila = $creados | Where-Object { $_.Guia -eq $issue.Numero }
        if (-not $fila.Nuevo) { continue }   # los que ya existían no se tocan
        $archivo = Guardar-Temporal -Texto (Renumerar -Texto $issue.Cuerpo -Mapa $mapa)
        try {
            Write-Host "  #$($fila.GitHub)"
            Escribir-Gh -Argumentos @('issue', 'edit', "$($fila.GitHub)", '--body-file', $archivo) | Out-Null
        }
        finally {
            Remove-Item $archivo -ErrorAction SilentlyContinue
        }
    }
    Write-Host '  Ojo: la tabla de docs/guia-issues.md sigue con los números de la guía; usá el CSV.' -ForegroundColor Yellow
}
else {
    Write-Host "`n4. Los números de GitHub coinciden con los de la guía."
}

# ---------------------------------------------------------------------------------------------
# 5. Correspondencia
# ---------------------------------------------------------------------------------------------

if ($Prueba) {
    Write-Host "`n5. En modo prueba no se escribe $Salida."
}
else {
    $creados | Select-Object Guia, GitHub, Titulo |
        Export-Csv -Path $Salida -NoTypeInformation -Encoding UTF8
    Write-Host "`n5. Correspondencia guardada en $Salida"
}
Write-Host "`nListo. Revisá los issues con: gh issue list --limit 50" -ForegroundColor Green

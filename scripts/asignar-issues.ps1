<#
.SYNOPSIS
    Asigna cada issue en GitHub al integrante que la tiene a cargo.

.DESCRIPTION
    Lee scripts/issues-por-escenario.csv (escenario, número en GitHub y responsable) y asigna cada
    issue al usuario de GitHub de ese integrante, sacando a cualquier otro asignado. También asigna
    las tres issues que no son de un escenario: la base y las dos ampliaciones del 17/11.

    El usuario de GitHub de cada integrante sale de un commit suyo en el repo (GitHub sabe de qué
    cuenta es). Si alguno no se puede averiguar, pasalo a mano con -Usuarios.

    Todo lo hace gh con la cuenta con la que hiciste `gh auth login`. Se puede volver a correr: no
    toca las que ya están bien asignadas. Compatible con Windows PowerShell 5.1 y con PowerShell 7.

.PARAMETER Prueba
    Muestra lo que haría, sin modificar nada en GitHub.

.PARAMETER Usuarios
    Usuarios de GitHub a mano, si no se pueden averiguar: -Usuarios @{ 'Integrante 2' = 'leonel' }

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts/asignar-issues.ps1 -Prueba
    powershell -ExecutionPolicy Bypass -File scripts/asignar-issues.ps1
#>
[CmdletBinding()]
param(
    [switch]$Prueba,
    [hashtable]$Usuarios = @{},
    [string]$Correspondencia = 'scripts/issues-por-escenario.csv'
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

# Quién es cada integrante, según los commits de sus issues, y un commit suyo para averiguar su
# usuario de GitHub.
$integrantes = [ordered]@{
    'Integrante 1' = @{ Nombre = 'Nicolás Díaz';       Commit = 'ad2f7c2497f1ab4583a3c43890e711a69800b22c' }
    'Integrante 2' = @{ Nombre = 'Leonel David Gomez'; Commit = '2b5fbbc708d584c6295985ea9ba84f91aac43239' }
    'Integrante 3' = @{ Nombre = 'Justina Guerrero';   Commit = '56a582aa9929d7d7d75b9a872f03272f7f160f5f' }
    'Integrante 4' = @{ Nombre = 'Ivan Sgriletti';     Commit = 'c1f0a65f87fcc2795f45404892c9dde5a0c3c553' }
}

# Las issues que no son de un escenario, por el principio de su título.
$extras = @(
    @{ Titulo = 'Base: estructura, base de datos y login'; Responsable = 'Integrante 1' },
    @{ Titulo = 'Avisos por el módulo de avisos (mail y WhatsApp)'; Responsable = 'Integrante 3' },
    @{ Titulo = 'Autorización de la obra social desde su módulo'; Responsable = 'Integrante 4' }
)

function Invocar-Gh {
    <# Corre gh y devuelve su salida como un solo texto. Lanza un error si gh falla. #>
    param([Parameter(Mandatory)][string[]]$Argumentos)
    $preferenciaAnterior = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try { $salida = & gh @Argumentos } finally { $ErrorActionPreference = $preferenciaAnterior }
    if ($LASTEXITCODE -ne 0) {
        throw "Falló: gh $($Argumentos -join ' ')"
    }
    return ($salida -join "`n")
}

function Escribir-Gh {
    param([Parameter(Mandatory)][string[]]$Argumentos)
    if ($Prueba) {
        Write-Host "      [prueba] gh $($Argumentos -join ' ')" -ForegroundColor DarkGray
        return ''
    }
    return Invocar-Gh -Argumentos $Argumentos
}

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw 'No se encontró gh (GitHub CLI). Instalalo y corré gh auth login.'
}
if (-not (Test-Path $Correspondencia)) {
    throw "No se encontró $Correspondencia. Corré el script desde la raíz del repo."
}
$repo = Invocar-Gh -Argumentos @('repo', 'view', '--json', 'nameWithOwner', '--jq', '.nameWithOwner')
Write-Host "Repositorio: $repo" -ForegroundColor Cyan
if ($Prueba) { Write-Host 'Modo prueba: no se modifica nada.' -ForegroundColor Yellow }

# ---------------------------------------------------------------------------------------------
# 1. Usuario de GitHub de cada integrante
# ---------------------------------------------------------------------------------------------

Write-Host "`n1. Usuarios de GitHub" -ForegroundColor Cyan
$login = @{}
foreach ($clave in $integrantes.Keys) {
    $datos = $integrantes[$clave]
    if ($Usuarios.ContainsKey($clave)) {
        $login[$clave] = [string]$Usuarios[$clave]
    }
    else {
        $usuario = ''
        try {
            $usuario = Invocar-Gh -Argumentos @('api', "repos/{owner}/{repo}/commits/$($datos.Commit)", '--jq', '.author.login')
        }
        catch { $usuario = '' }
        # Si el mail del commit no está en ninguna cuenta, GitHub no sabe de quién es: null.
        if (-not $usuario.Trim() -or $usuario.Trim() -eq 'null') {
            throw "No pude averiguar el usuario de GitHub de $($datos.Nombre) ($clave). Pasalo a mano: -Usuarios @{ '$clave' = 'su-usuario' }"
        }
        $login[$clave] = $usuario.Trim()
    }
    Write-Host ("  {0}: {1,-20} -> {2}" -f $clave, $datos.Nombre, $login[$clave])
}

# ---------------------------------------------------------------------------------------------
# 2. Qué integrante va en cada issue
# ---------------------------------------------------------------------------------------------

$jsonIssues = Invocar-Gh -Argumentos @('issue', 'list', '--state', 'all', '--limit', '1000',
    '--json', 'number,title,assignees')
$issues = @{}
foreach ($i in (ConvertFrom-Json $jsonIssues)) {
    $issues[[int]$i.number] = [pscustomobject]@{
        Numero    = [int]$i.number
        Titulo    = [string]$i.title
        Asignados = @(foreach ($a in $i.assignees) { [string]$a.login })
    }
}

$plan = @()
foreach ($fila in (Import-Csv -Path $Correspondencia -Encoding UTF8)) {
    $plan += [pscustomobject]@{ Numero = [int]$fila.GitHub; Responsable = $fila.Responsable }
}
foreach ($extra in $extras) {
    $encontrada = @($issues.Values | Where-Object {
            $_.Titulo -eq $extra.Titulo -or $_.Titulo.StartsWith("$($extra.Titulo) (", [System.StringComparison]::Ordinal)
        })
    foreach ($issue in $encontrada) {
        $plan += [pscustomobject]@{ Numero = $issue.Numero; Responsable = $extra.Responsable }
    }
}

# ---------------------------------------------------------------------------------------------
# 3. Asignar
# ---------------------------------------------------------------------------------------------

Write-Host "`n2. Asignaciones" -ForegroundColor Cyan
$cambiadas = 0
foreach ($p in ($plan | Sort-Object Numero)) {
    if (-not $issues.ContainsKey($p.Numero)) {
        Write-Host "  #$($p.Numero): no existe en GitHub, se saltea" -ForegroundColor Yellow
        continue
    }
    if (-not $login.ContainsKey($p.Responsable)) {
        Write-Host "  #$($p.Numero): responsable desconocido '$($p.Responsable)', se saltea" -ForegroundColor Yellow
        continue
    }
    $issue = $issues[$p.Numero]
    $usuario = $login[$p.Responsable]
    $sacar = @($issue.Asignados | Where-Object { $_ -ne $usuario })
    $falta = $issue.Asignados -notcontains $usuario
    if (-not $falta -and $sacar.Count -eq 0) {
        Write-Host ("  #{0,-4} {1}  ({2}: ya estaba)" -f $issue.Numero, $issue.Titulo, $usuario)
        continue
    }
    $argumentos = @('issue', 'edit', "$($issue.Numero)")
    if ($falta) { $argumentos += @('--add-assignee', $usuario) }
    if ($sacar.Count -gt 0) { $argumentos += @('--remove-assignee', ($sacar -join ',')) }
    Escribir-Gh -Argumentos $argumentos | Out-Null
    $cambiadas++
    Write-Host ("  #{0,-4} {1}  -> {2}" -f $issue.Numero, $issue.Titulo, $usuario)
}

Write-Host "`nListo: $cambiadas issues asignadas." -ForegroundColor Green

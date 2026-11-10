param([Parameter(Mandatory = $true)][string]$Source)
$ErrorActionPreference = 'Stop'
$projectPath = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $projectPath
try {
    $pythonPath = Join-Path $projectPath '.venv\Scripts\python.exe'
    & $pythonPath -m observatory.cli import $Source
    if ($LASTEXITCODE -ne 0) { throw 'Importação reprovada' }
    & $pythonPath -m observatory.cli verify
    if ($LASTEXITCODE -ne 0) { throw 'Integridade reprovada' }
    & $pythonPath -m observatory.cli build
    if ($LASTEXITCODE -ne 0) { throw 'Build reprovado' }
} finally { Pop-Location }

param([int]$Port = 8765)
$ErrorActionPreference = 'Stop'
$projectPath = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $projectPath
try {
    $pythonPath = Join-Path $projectPath '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $pythonPath)) {
        throw 'Ambiente ausente. Execute python -m venv .venv e .\.venv\Scripts\python.exe -m pip install -e ".[dev]"'
    }
    & $pythonPath -m observatory.cli serve --port $Port
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao iniciar o dashboard' }
} finally { Pop-Location }

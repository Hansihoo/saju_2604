param(
    [switch]$SkipCompile
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$apiDir = Join-Path $repoRoot "apps\api"
$venvPython = Join-Path $apiDir ".venv\Scripts\python.exe"
$python = if (Test-Path $venvPython) { $venvPython } else { "python" }

Push-Location $apiDir
try {
    if (-not $SkipCompile) {
        & $python -m compileall app
    }

    & $python -m unittest discover -s tests -p "test_*.py"
}
finally {
    Pop-Location
}

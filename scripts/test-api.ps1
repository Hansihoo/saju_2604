param(
    [switch]$SkipCompile
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$apiDir = Join-Path $repoRoot "apps\api"
$venvPython = Join-Path $apiDir ".venv\Scripts\python.exe"
$python = if (Test-Path $venvPython) { $venvPython } else { "python" }
$previousLlmProvider = $env:SAJU_LLM_PROVIDER
$env:SAJU_LLM_PROVIDER = "fallback"

Push-Location $apiDir
try {
    & $python -m app.tools.ensure_skyfield_ephemeris --download --check

    if (-not $SkipCompile) {
        & $python -m compileall app
    }

    & $python -m unittest discover -s tests -p "test_*.py"
}
finally {
    if ($null -eq $previousLlmProvider) {
        Remove-Item Env:\SAJU_LLM_PROVIDER -ErrorAction SilentlyContinue
    }
    else {
        $env:SAJU_LLM_PROVIDER = $previousLlmProvider
    }
    Pop-Location
}

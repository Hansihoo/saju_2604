param(
    [switch]$Refresh,
    [string]$DataDir
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$apiDir = Join-Path $repoRoot "apps\api"
$venvPython = Join-Path $apiDir ".venv\Scripts\python.exe"
$python = if (Test-Path $venvPython) { $venvPython } else { "python" }

$arguments = @("-m", "app.tools.ensure_skyfield_ephemeris", "--download", "--check")
if ($Refresh) {
    $arguments += "--refresh"
}
if ($DataDir) {
    $arguments += @("--data-dir", $DataDir)
}

Push-Location $apiDir
try {
    & $python @arguments
}
finally {
    Pop-Location
}

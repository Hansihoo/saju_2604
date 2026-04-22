param(
    [string]$BindHost = "127.0.0.1",
    [int]$Port = 8000,
    [switch]$Reload,
    [switch]$AllowReloadInCodex
)

$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "dev-common.ps1")

$apiDir = Get-ApiDirectory
$python = Get-BackendPython

if ($Reload -and (Test-IsCodexShell) -and -not $AllowReloadInCodex) {
    throw "Reload is disabled in Codex / sandbox shells because it can loop on WinError 5. Use run-api.ps1 without -Reload."
}

$arguments = @(
    "-m",
    "uvicorn",
    "app.main:app",
    "--host",
    $BindHost,
    "--port",
    $Port
)

if ($Reload) {
    $arguments += "--reload"
}

Push-Location $apiDir
try {
    & $python @arguments
}
finally {
    Pop-Location
}

param(
    [switch]$BackendOnly,
    [switch]$FrontendOnly,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$apiDir = Join-Path $repoRoot "apps\api"
$webDir = Join-Path $repoRoot "apps\web"
$venvPython = Join-Path $apiDir ".venv\Scripts\python.exe"
$backendPython = if (Test-Path $venvPython) { $venvPython } else { "python" }

$backendCommand = "$backendPython -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
$frontendCommand = "pnpm --filter web dev -- --host 127.0.0.1 --port 5173"

function Start-DevWindow {
    param(
        [string]$Title,
        [string]$WorkingDirectory,
        [string]$Command
    )

    $fullCommand = "Set-Location -LiteralPath '$WorkingDirectory'; `$Host.UI.RawUI.WindowTitle = '$Title'; $Command"

    if ($DryRun) {
        Write-Host "[$Title]"
        Write-Host $fullCommand
        Write-Host ""
        return
    }

    Start-Process powershell -ArgumentList @(
        "-NoExit",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        $fullCommand
    ) | Out-Null
}

if (-not $FrontendOnly) {
    Start-DevWindow -Title "SaJu API" -WorkingDirectory $apiDir -Command $backendCommand
}

if (-not $BackendOnly) {
    Start-DevWindow -Title "SaJu Web" -WorkingDirectory $repoRoot -Command $frontendCommand
}

if (-not $DryRun) {
    Write-Host "Started development windows."
    if (-not $FrontendOnly) {
        Write-Host "API: http://127.0.0.1:8000"
        Write-Host "API Docs: http://127.0.0.1:8000/docs"
    }
    if (-not $BackendOnly) {
        Write-Host "Web: http://127.0.0.1:5173"
    }
}

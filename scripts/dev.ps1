param(
    [switch]$BackendOnly,
    [switch]$FrontendOnly,
    [switch]$DryRun,
    [switch]$DisableReload
)

$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "dev-common.ps1")

$apiDir = Get-ApiDirectory
$webDir = Get-WebDirectory
$backendPython = Get-BackendPython
$npmCommand = Get-NpmCommand

function Start-DetachedProcess {
    param(
        [string]$Title,
        [string]$WorkingDirectory,
        [string]$FilePath,
        [string[]]$Arguments = @(),
        [string[]]$PathEntries = @()
    )

    $formattedArguments = @($Arguments | ForEach-Object { Format-CommandArgument $_ })
    $displayCommand = (@(Format-CommandArgument $FilePath) + $formattedArguments) -join " "

    if ($DryRun) {
        Write-Host "[$Title]"
        Write-Host "Working directory: $WorkingDirectory"
        Write-Host $displayCommand
        Write-Host ""
        return
    }

    Repair-ProcessPathEnvironment
    foreach ($pathEntry in $PathEntries) {
        Add-ProcessPathEntry $pathEntry
    }

    Start-Process -FilePath $FilePath -WorkingDirectory $WorkingDirectory -ArgumentList $Arguments | Out-Null
}

$runningInCodex = Test-IsCodexShell
$useReload = -not $DisableReload -and -not $runningInCodex

if (-not $FrontendOnly) {
    $backendArguments = @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000")
    if ($useReload) {
        $backendArguments += "--reload"
    }

    Start-DetachedProcess -Title "SaJu API" -WorkingDirectory $apiDir -FilePath $backendPython -Arguments $backendArguments
}

if (-not $BackendOnly) {
    $frontendArguments = @("run", "dev", "--", "--host", "127.0.0.1", "--port", "5173")
    $frontendPathEntries = @()
    if (Test-Path $npmCommand) {
        $frontendPathEntries += (Split-Path $npmCommand -Parent)
    }
    Start-DetachedProcess -Title "SaJu Web" -WorkingDirectory $webDir -FilePath $npmCommand -Arguments $frontendArguments -PathEntries $frontendPathEntries
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
    if ($runningInCodex -and -not $FrontendOnly) {
        Write-Host "Codex shell detected: backend reload was disabled to avoid Windows named-pipe permission errors."
    }
}

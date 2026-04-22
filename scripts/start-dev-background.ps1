param(
    [switch]$ApiOnly,
    [switch]$WebOnly,
    [int]$ApiPort = 8000,
    [int]$WebPort = 5173,
    [int]$TimeoutSeconds = 30,
    [switch]$ClearLogs
)

$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "dev-common.ps1")

if ($ApiOnly -and $WebOnly) {
    throw "Choose either -ApiOnly or -WebOnly, not both."
}

$startApi = -not $WebOnly
$startWeb = -not $ApiOnly
$startedServices = @()

try {
    if ($startApi) {
        $existingApi = Read-ServiceMetadata -Name "api"
        if ($existingApi) {
            Stop-ManagedProcess -Name "api" | Out-Null
        }

        $apiMetadata = Start-ManagedProcess `
            -Name "api" `
            -FilePath (Get-BackendPython) `
            -WorkingDirectory (Get-ApiDirectory) `
            -Arguments @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$ApiPort") `
            -Port $ApiPort `
            -Url "http://127.0.0.1:$ApiPort/health" `
            -ClearLogs:$ClearLogs

        $startedServices += "api"
        if (-not (Wait-ForHttpReady -Url $apiMetadata.url -TimeoutSeconds $TimeoutSeconds)) {
            $apiErrors = (Get-LogTail -Path $apiMetadata.stderrLog -LineCount 20) -join [Environment]::NewLine
            throw "API failed to become ready on port $ApiPort.`n$apiErrors"
        }

        Write-Output "API started: http://127.0.0.1:$ApiPort"
    }

    if ($startWeb) {
        $existingWeb = Read-ServiceMetadata -Name "web"
        if ($existingWeb) {
            Stop-ManagedProcess -Name "web" | Out-Null
        }

        $npmCommand = Get-NpmCommand
        $webPathEntries = @()
        if (Test-Path $npmCommand) {
            $webPathEntries += (Split-Path $npmCommand -Parent)
        }

        $webMetadata = Start-ManagedProcess `
            -Name "web" `
            -FilePath $npmCommand `
            -WorkingDirectory (Get-WebDirectory) `
            -Arguments @("run", "dev", "--", "--host", "127.0.0.1", "--port", "$WebPort") `
            -Port $WebPort `
            -Url "http://127.0.0.1:$WebPort" `
            -PathEntries $webPathEntries `
            -ClearLogs:$ClearLogs

        $startedServices += "web"
        if (-not (Wait-ForHttpReady -Url $webMetadata.url -TimeoutSeconds $TimeoutSeconds)) {
            $webErrors = (Get-LogTail -Path $webMetadata.stderrLog -LineCount 20) -join [Environment]::NewLine
            throw "Web failed to become ready on port $WebPort.`n$webErrors"
        }

        Write-Output "Web started: http://127.0.0.1:$WebPort"
    }
}
catch {
    foreach ($serviceName in $startedServices) {
        Stop-ManagedProcess -Name $serviceName | Out-Null
    }
    throw
}

Write-Output "Managed logs: $(Get-DevRuntimeDirectory -EnsureExists)"

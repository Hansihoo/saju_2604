param(
    [switch]$Json
)

$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "dev-common.ps1")

$statuses = @(
    Get-ManagedServiceStatus -Name "api"
    Get-ManagedServiceStatus -Name "web"
)

if ($Json) {
    $statuses | ConvertTo-Json -Depth 4
    return
}

$statuses | Format-Table name, managed, running, healthy, processId, port, url, startedAt -AutoSize

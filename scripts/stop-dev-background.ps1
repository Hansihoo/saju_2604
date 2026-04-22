param(
    [switch]$ApiOnly,
    [switch]$WebOnly,
    [switch]$CleanLogs
)

$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "dev-common.ps1")

if ($ApiOnly -and $WebOnly) {
    throw "Choose either -ApiOnly or -WebOnly, not both."
}

$targets = @()
if ($ApiOnly) {
    $targets += "api"
}
elseif ($WebOnly) {
    $targets += "web"
}
else {
    $targets += "api", "web"
}

foreach ($target in $targets) {
    $result = Stop-ManagedProcess -Name $target -CleanLogs:$CleanLogs
    Write-Output ("{0}: {1}" -f $target, $result.reason)
}

param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("openai", "codex")]
    [string]$Provider,
    [string]$Model,
    [ValidateSet("none", "minimal", "low", "medium", "high", "xhigh")]
    [string]$ReasoningEffort,
    [int]$ApiPort = 8000,
    [int]$WebPort = 5173,
    [switch]$ApiOnly,
    [switch]$CheckOnly
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "dev-common.ps1")

# Override .env.local only for these children; restore the caller afterwards.
$providerOverrides = @{
    SAJU_LLM_PROVIDER = $Provider
    SAJU_LLM_MAX_ATTEMPTS = "1"
    SAJU_LLM_ALLOW_REPAIR = "0"
}
if ($Provider -eq "openai") {
    $providerOverrides.OPENAI_MODEL = $(if ($Model) { $Model } else { "gpt-5.4" })
    $providerOverrides.SAJU_LLM_REASONING_EFFORT = $(if ($ReasoningEffort) { $ReasoningEffort } else { "low" })
}
else {
    $providerOverrides.SAJU_CODEX_MODEL = $(if ($Model) { $Model } else { "gpt-6.1-sol" })
    $providerOverrides.SAJU_CODEX_REASONING_EFFORT = $(if ($ReasoningEffort) { $ReasoningEffort } else { "xhigh" })
    $providerOverrides.SAJU_CODEX_TIMEOUT_SECONDS = "600"
    $providerOverrides.SAJU_CODEX_SANDBOX = "read-only"
}
$providerPrevious = @{}
foreach ($providerName in $providerOverrides.Keys) {
    $providerPrevious[$providerName] = [Environment]::GetEnvironmentVariable($providerName, "Process")
}
try {
    foreach ($providerName in $providerOverrides.Keys) {
        [Environment]::SetEnvironmentVariable($providerName, $providerOverrides[$providerName], "Process")
    }
    Push-Location (Get-ApiDirectory)
    try {
        & (Get-BackendPython) -B -m app.tools.provider_status --provider $Provider --check-auth
        $providerPreflightExit = $LASTEXITCODE
    }
    finally { Pop-Location }
    if ($providerPreflightExit -ne 0) {
        throw "$Provider is not ready. No services were stopped or started. See the readiness result above."
    }
    if (-not $CheckOnly) {
        & (Join-Path $PSScriptRoot "start-dev-background.ps1") -ApiPort $ApiPort -WebPort $WebPort -ApiOnly:$ApiOnly
    }
}
finally {
    foreach ($providerName in $providerPrevious.Keys) {
        [Environment]::SetEnvironmentVariable($providerName, $providerPrevious[$providerName], "Process")
    }
}

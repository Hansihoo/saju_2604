param(
    [int]$ApiPort = 8000,
    [int]$WebPort = 5173
)

$ErrorActionPreference = "Stop"

# These overrides apply only to the local services started by this launcher.
$env:SAJU_LLM_PROVIDER = "codex"
$env:SAJU_CODEX_MODEL = "gpt-6.1-sol"
$env:SAJU_CODEX_REASONING_EFFORT = "xhigh"
$env:SAJU_LLM_REASONING_EFFORT = "xhigh"
$env:SAJU_CODEX_TIMEOUT_SECONDS = "600"
$env:SAJU_CODEX_SANDBOX = "read-only"
$env:SAJU_LLM_MAX_ATTEMPTS = "1"
$env:SAJU_LLM_ALLOW_REPAIR = "0"

& (Join-Path $PSScriptRoot "start-dev-background.ps1") -ApiPort $ApiPort -WebPort $WebPort
Write-Output "Local phrasing: Codex gpt-6.1-sol / xhigh. Uses the signed-in Codex account."

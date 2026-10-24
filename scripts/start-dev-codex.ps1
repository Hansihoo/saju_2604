param(
    [string]$Model = "gpt-6.1-sol",
    [string]$ReasoningEffort = "xhigh",
    [int]$ApiPort = 8000,
    [int]$WebPort = 5173,
    [switch]$ApiOnly,
    [switch]$CheckOnly
)

& (Join-Path $PSScriptRoot "start-dev-provider.ps1") -Provider codex @PSBoundParameters

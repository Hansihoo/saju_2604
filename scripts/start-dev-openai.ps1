param(
    [string]$Model = "gpt-5.4",
    [string]$ReasoningEffort = "low",
    [int]$ApiPort = 8000,
    [int]$WebPort = 5173,
    [switch]$ApiOnly,
    [switch]$CheckOnly
)

& (Join-Path $PSScriptRoot "start-dev-provider.ps1") -Provider openai @PSBoundParameters

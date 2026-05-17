$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$apiDir = Join-Path $repoRoot "apps\api"
$venvPython = Join-Path $apiDir ".venv\Scripts\python.exe"
$python = if (Test-Path $venvPython) { $venvPython } else { "python" }

$ranges = @(
    @{ Start = "1914-06-20"; End = "1914-07-25"; Name = "1914 leap-month boundary" },
    @{ Start = "2023-03-20"; End = "2023-04-10"; Name = "2023 leap lunar month" },
    @{ Start = "2024-02-01"; End = "2024-02-15"; Name = "2024 lunar new year" }
)

Push-Location $apiDir
try {
    foreach ($range in $ranges) {
        Write-Host "== KASI live spot check: $($range.Name) =="
        & $python -m app.tools.build_lunar_reference_table `
            --verify-with-kasi `
            --start-date $range.Start `
            --end-date $range.End
    }
}
finally {
    Pop-Location
}

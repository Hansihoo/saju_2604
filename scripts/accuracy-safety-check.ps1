$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot
try {
    Write-Host "== API regression =="
    pnpm test:api

    Write-Host "== Web build =="
    pnpm --filter web build

    Write-Host "== Accuracy diagnostic reports =="
    Push-Location (Join-Path $repoRoot "apps/api")
    try {
        python -m app.tools.build_lunar_reference_table --check
        python -m app.tools.build_solar_term_reference_table --check
        python -m app.tools.build_extended_solar_term_reference_table --check
        python tests/generate_iljin_reference_diff_report.py
        python tests/generate_lunar_reference_diff_report.py
        python tests/generate_solar_term_reference_diff_report.py
        python tests/generate_accuracy_mode_diff_report.py
        python tests/generate_canonical_year_month_diff_report.py
        python -m app.tools.run_golden_validation
    }
    finally {
        Pop-Location
    }
}
finally {
    Pop-Location
}

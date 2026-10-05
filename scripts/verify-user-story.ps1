param(
    [string]$ApiBase = "http://127.0.0.1:8000",
    [string]$WebBase = "http://127.0.0.1:5173",
    [string]$Output,
    [switch]$SkipBuild,
    [switch]$SkipTests,
    [switch]$AllApiTests
)

$ErrorActionPreference = "Stop"
$verificationRepoRoot = Split-Path -Parent $PSScriptRoot
$verificationApiDir = Join-Path $verificationRepoRoot "apps\api"
$verificationPython = Join-Path $verificationApiDir ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $verificationPython)) { $verificationPython = "python" }
if (-not $Output) { $Output = Join-Path $verificationRepoRoot "docs\ai\USER_STORY_VERIFICATION.json" }
$verificationOutputPath = [System.IO.Path]::GetFullPath($Output)
$verificationExitCode = 0
$verificationPreviousProvider = $env:SAJU_LLM_PROVIDER
$verificationPreviousBytecode = $env:PYTHONDONTWRITEBYTECODE

try {
    Push-Location $verificationApiDir
    try {
        # This environment affects this process/tests, not the running server.
        # The HTTP verifier independently checks that server before any POST.
        $env:SAJU_LLM_PROVIDER = "fallback"
        $env:PYTHONDONTWRITEBYTECODE = "1"
        & $verificationPython -B -m app.tools.verify_user_story --api-base $ApiBase --web-base $WebBase --output $verificationOutputPath
        $verificationRuntimeExit = $LASTEXITCODE
        if ($verificationRuntimeExit -ne 0) { $verificationExitCode = $verificationRuntimeExit }
        # A blocked preflight is terminal; no need for further work that might
        # disguise failure or prolong a run against an unconfirmed environment.
        if ($verificationRuntimeExit -ne 2 -and -not $SkipTests) {
            if ($AllApiTests) {
                & $verificationPython -B -m unittest discover -s tests -p "test_*.py"
            }
            else {
                & $verificationPython -B -m unittest tests.test_verify_user_story tests.test_verification_guard tests.test_saju_preview_pipeline tests.test_build_period_flows tests.test_birth_time_policy tests.test_generate_free_preview tests.test_generate_interpretation tests.test_interpretation_formatter tests.test_uncertainty_detection
            }
            if ($LASTEXITCODE -ne 0) { $verificationExitCode = 1 }
        }
    }
    finally { Pop-Location }

    if ($verificationRuntimeExit -ne 2 -and -not $SkipBuild) {
        Push-Location $verificationRepoRoot
        try {
            & pnpm build:web
            if ($LASTEXITCODE -ne 0) { $verificationExitCode = 1 }
        }
        finally { Pop-Location }
    }
    if ($verificationRuntimeExit -ne 2 -and -not $SkipTests) {
        & node (Join-Path $PSScriptRoot "verify-web-reading.cjs")
        if ($LASTEXITCODE -ne 0) { $verificationExitCode = 1 }
    }
}
finally {
    if ($null -eq $verificationPreviousProvider) { Remove-Item Env:\SAJU_LLM_PROVIDER -ErrorAction SilentlyContinue }
    else { $env:SAJU_LLM_PROVIDER = $verificationPreviousProvider }
    if ($null -eq $verificationPreviousBytecode) { Remove-Item Env:\PYTHONDONTWRITEBYTECODE -ErrorAction SilentlyContinue }
    else { $env:PYTHONDONTWRITEBYTECODE = $verificationPreviousBytecode }
}

exit $verificationExitCode

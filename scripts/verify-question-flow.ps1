param([Parameter(Mandatory=$true)][string]$Output, [ValidateSet('all','basic')][string]$ReviewScope = 'all')
$ErrorActionPreference = 'Stop'
$questionApiDir = Join-Path (Split-Path -Parent $PSScriptRoot) 'apps/api'
$questionOutput = [System.IO.Path]::GetFullPath($Output)
Push-Location $questionApiDir
try {
    python -B -m app.tools.verify_question_flow --output $questionOutput --review-scope $ReviewScope
    $questionExit = $LASTEXITCODE
}
finally { Pop-Location }
exit $questionExit

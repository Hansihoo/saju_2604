# Forward CLI options without changing the application's provider or model configuration.
$ErrorActionPreference = "Stop"
$agentRepoRoot = Split-Path -Parent $PSScriptRoot
$agentApiDir = Join-Path $agentRepoRoot "apps\api"
$agentPython = Join-Path $agentApiDir ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $agentPython)) { $agentPython = "python" }
$agentPreviousPythonPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = if ($agentPreviousPythonPath) { "$agentApiDir;$agentPreviousPythonPath" } else { $agentApiDir }
    & $agentPython -B -m app.tools.verify_codex_agents @args
    $agentExitCode = $LASTEXITCODE
}
finally {
    if ($null -eq $agentPreviousPythonPath) { Remove-Item Env:\PYTHONPATH -ErrorAction SilentlyContinue }
    else { $env:PYTHONPATH = $agentPreviousPythonPath }
}
exit $agentExitCode

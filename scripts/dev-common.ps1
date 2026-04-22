$script:RepoRoot = Split-Path -Parent $PSScriptRoot

function Get-RepoRoot {
    return $script:RepoRoot
}

function Get-ApiDirectory {
    return (Join-Path (Get-RepoRoot) "apps\api")
}

function Get-WebDirectory {
    return (Join-Path (Get-RepoRoot) "apps\web")
}

function Get-BackendPython {
    $apiDir = Get-ApiDirectory
    $venvPython = Join-Path $apiDir ".venv\Scripts\python.exe"
    if (Test-Path $venvPython) {
        return $venvPython
    }

    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCommand -and $pythonCommand.Source) {
        return $pythonCommand.Source
    }

    return "python"
}

function Get-NpmCommand {
    $npmCommand = "C:\Program Files\nodejs\npm.cmd"
    if (Test-Path $npmCommand) {
        return $npmCommand
    }

    return "npm.cmd"
}

function Test-IsCodexShell {
    return [bool]($env:CODEX_SHELL -or $env:CODEX_THREAD_ID -or $env:SBX_NONET_ACTIVE)
}

function Repair-ProcessPathEnvironment {
    $pathValue = [System.Environment]::GetEnvironmentVariable("Path", "Process")
    if (-not $pathValue) {
        $pathValue = [System.Environment]::GetEnvironmentVariable("PATH", "Process")
    }

    if ($pathValue) {
        [System.Environment]::SetEnvironmentVariable("Path", $pathValue, "Process")
    }

    [System.Environment]::SetEnvironmentVariable("PATH", $null, "Process")
}

function Add-ProcessPathEntry {
    param([string]$Entry)

    if ([string]::IsNullOrWhiteSpace($Entry) -or -not (Test-Path $Entry)) {
        return
    }

    $currentPath = [System.Environment]::GetEnvironmentVariable("Path", "Process")
    $pathEntries = @($currentPath -split ";" | Where-Object { $_ })
    if ($pathEntries -contains $Entry) {
        return
    }

    $updatedEntries = @($Entry) + $pathEntries
    [System.Environment]::SetEnvironmentVariable("Path", ($updatedEntries -join ";"), "Process")
}

function Format-CommandArgument {
    param([string]$Value)

    if ([string]::IsNullOrEmpty($Value)) {
        return "''"
    }

    if ($Value -match "[\s'`"]") {
        return "'{0}'" -f $Value.Replace("'", "''")
    }

    return $Value
}

function Get-DevRuntimeDirectory {
    param([switch]$EnsureExists)

    $runtimeDir = Join-Path (Get-RepoRoot) ".dev-runtime"
    if ($EnsureExists -and -not (Test-Path $runtimeDir)) {
        New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null
    }

    return $runtimeDir
}

function Get-ServiceMetadataPath {
    param(
        [ValidateSet("api", "web")]
        [string]$Name
    )

    return (Join-Path (Get-DevRuntimeDirectory -EnsureExists) "$Name.json")
}

function Get-ServiceLogPath {
    param(
        [ValidateSet("api", "web")]
        [string]$Name,
        [ValidateSet("stdout", "stderr")]
        [string]$Stream
    )

    return (Join-Path (Get-DevRuntimeDirectory -EnsureExists) "$Name.$Stream.log")
}

function Write-ServiceMetadata {
    param(
        [ValidateSet("api", "web")]
        [string]$Name,
        [int]$ProcessId,
        [int]$Port,
        [string]$Url,
        [string]$FilePath,
        [string]$WorkingDirectory,
        [string[]]$Arguments,
        [string]$StdoutLog,
        [string]$StderrLog
    )

    $metadata = [pscustomobject]@{
        name = $Name
        processId = $ProcessId
        port = $Port
        url = $Url
        filePath = $FilePath
        workingDirectory = $WorkingDirectory
        arguments = $Arguments
        stdoutLog = $StdoutLog
        stderrLog = $StderrLog
        startedAt = (Get-Date).ToString("o")
    }

    $metadata | ConvertTo-Json -Depth 4 | Set-Content -Path (Get-ServiceMetadataPath -Name $Name) -Encoding UTF8
    return $metadata
}

function Read-ServiceMetadata {
    param(
        [ValidateSet("api", "web")]
        [string]$Name
    )

    $metadataPath = Get-ServiceMetadataPath -Name $Name
    if (-not (Test-Path $metadataPath)) {
        return $null
    }

    return (Get-Content $metadataPath -Raw | ConvertFrom-Json)
}

function Remove-ServiceMetadata {
    param(
        [ValidateSet("api", "web")]
        [string]$Name
    )

    $metadataPath = Get-ServiceMetadataPath -Name $Name
    if (Test-Path $metadataPath) {
        Remove-Item -LiteralPath $metadataPath -Force
    }
}

function Get-ListeningProcessId {
    param([int]$Port)

    $netstatCommand = Join-Path $env:SystemRoot "System32\netstat.exe"
    if (-not (Test-Path $netstatCommand)) {
        $netstatCommand = "netstat"
    }

    $matches = & $netstatCommand -ano -p tcp | Select-String ":$Port\s+"
    foreach ($match in $matches) {
        $text = $match.ToString().Trim()
        if ($text -match "LISTENING\s+(\d+)$") {
            return [int]$Matches[1]
        }
    }

    return $null
}

function Wait-ForHttpReady {
    param(
        [string]$Url,
        [int]$TimeoutSeconds = 30
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -UseBasicParsing $Url -TimeoutSec 3
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                return $true
            }
        }
        catch {
        }

        Start-Sleep -Seconds 1
    }

    return $false
}

function Get-LogTail {
    param(
        [string]$Path,
        [int]$LineCount = 20
    )

    if (-not (Test-Path $Path)) {
        return @()
    }

    return @(Get-Content -LiteralPath $Path -Tail $LineCount)
}

function Start-ManagedProcess {
    param(
        [ValidateSet("api", "web")]
        [string]$Name,
        [string]$FilePath,
        [string]$WorkingDirectory,
        [string[]]$Arguments,
        [int]$Port,
        [string]$Url,
        [string[]]$PathEntries = @(),
        [switch]$ClearLogs
    )

    Repair-ProcessPathEnvironment
    foreach ($pathEntry in $PathEntries) {
        Add-ProcessPathEntry $pathEntry
    }

    $existingProcessId = Get-ListeningProcessId -Port $Port
    if ($existingProcessId) {
        throw "Port $Port is already in use by PID $existingProcessId."
    }

    $stdoutLog = Get-ServiceLogPath -Name $Name -Stream "stdout"
    $stderrLog = Get-ServiceLogPath -Name $Name -Stream "stderr"
    if ($ClearLogs) {
        Remove-Item -LiteralPath $stdoutLog, $stderrLog -Force -ErrorAction SilentlyContinue
    }

    $process = Start-Process -FilePath $FilePath -WorkingDirectory $WorkingDirectory -ArgumentList $Arguments -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog -PassThru

    return (Write-ServiceMetadata -Name $Name -ProcessId $process.Id -Port $Port -Url $Url -FilePath $FilePath -WorkingDirectory $WorkingDirectory -Arguments $Arguments -StdoutLog $stdoutLog -StderrLog $stderrLog)
}

function Stop-ManagedProcess {
    param(
        [ValidateSet("api", "web")]
        [string]$Name,
        [switch]$CleanLogs
    )

    $metadata = Read-ServiceMetadata -Name $Name
    if (-not $metadata) {
        return [pscustomobject]@{
            name = $Name
            stopped = $false
            reason = "not-managed"
        }
    }

    $stopped = $false
    if ($metadata.processId) {
        $process = Get-Process -Id $metadata.processId -ErrorAction SilentlyContinue
        if ($process) {
            Stop-Process -Id $metadata.processId -Force -ErrorAction SilentlyContinue
            $stopped = $true
        }
    }

    if ($metadata.port) {
        Start-Sleep -Milliseconds 500
        $listenerProcessId = Get-ListeningProcessId -Port ([int]$metadata.port)
        if ($listenerProcessId) {
            Stop-Process -Id $listenerProcessId -Force -ErrorAction SilentlyContinue
            $stopped = $true
        }
    }

    Remove-ServiceMetadata -Name $Name

    if ($CleanLogs) {
        Remove-Item -LiteralPath $metadata.stdoutLog, $metadata.stderrLog -Force -ErrorAction SilentlyContinue
    }

    return [pscustomobject]@{
        name = $Name
        stopped = $stopped
        reason = if ($stopped) { "stopped" } else { "not-running" }
    }
}

function Get-ManagedServiceStatus {
    param(
        [ValidateSet("api", "web")]
        [string]$Name
    )

    $metadata = Read-ServiceMetadata -Name $Name
    if (-not $metadata) {
        return [pscustomobject]@{
            name = $Name
            managed = $false
            running = $false
            healthy = $false
            processId = $null
            port = $null
            url = $null
            startedAt = $null
            stdoutLog = $null
            stderrLog = $null
        }
    }

    $running = [bool](Get-Process -Id $metadata.processId -ErrorAction SilentlyContinue)
    $healthy = $false
    if ($running -and $metadata.url) {
        $healthy = Wait-ForHttpReady -Url $metadata.url -TimeoutSeconds 2
    }

    return [pscustomobject]@{
        name = $metadata.name
        managed = $true
        running = $running
        healthy = $healthy
        processId = $metadata.processId
        port = $metadata.port
        url = $metadata.url
        startedAt = $metadata.startedAt
        stdoutLog = $metadata.stdoutLog
        stderrLog = $metadata.stderrLog
    }
}

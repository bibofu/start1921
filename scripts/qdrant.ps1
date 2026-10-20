param(
    [ValidateSet("start", "stop", "status")]
    [string]$Action = "start"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$qdrantExecutable = Join-Path $projectRoot "data\qdrant-runtime\v1.19.2\qdrant.exe"
$qdrantConfig = Join-Path $projectRoot "config\qdrant.yaml"
$runtimeDirectory = Join-Path $projectRoot "data\qdrant-runtime"
$processFile = Join-Path $runtimeDirectory "server-process.json"
$logDirectory = Join-Path $projectRoot "data\server"

function Get-ProjectQdrant {
    if (-not (Test-Path -LiteralPath $processFile)) { return $null }
    $record = Get-Content -LiteralPath $processFile -Raw | ConvertFrom-Json
    $candidate = Get-CimInstance Win32_Process -Filter "ProcessId = $([int]$record.process_id)"
    if ($null -eq $candidate) { return $null }
    if ($candidate.ExecutablePath -ne $qdrantExecutable -or
        $candidate.CommandLine -notlike "*$qdrantConfig*") {
        throw "The recorded process no longer matches this project's Qdrant server."
    }
    return $candidate
}

$runningServer = Get-ProjectQdrant
if ($Action -eq "status") {
    if ($null -eq $runningServer) {
        Write-Host "Project Qdrant is not running."
        exit 1
    }
    $health = Invoke-WebRequest -Uri "http://127.0.0.1:6333/readyz" -TimeoutSec 5
    Write-Host "Project Qdrant PID $($runningServer.ProcessId), readiness HTTP $($health.StatusCode)."
    exit 0
}
if ($Action -eq "stop") {
    if ($null -ne $runningServer) {
        Stop-Process -Id $runningServer.ProcessId
        Write-Host "Project Qdrant stopped."
    } else {
        Write-Host "Project Qdrant is not running."
    }
    exit 0
}
if ($null -ne $runningServer) {
    Write-Host "Project Qdrant is already running (PID $($runningServer.ProcessId))."
    exit 0
}
if (-not (Test-Path -LiteralPath $qdrantExecutable)) {
    throw "Qdrant v1.19.2 Windows binaries are missing. See QDRANT_SERVICE.md."
}
if (Get-NetTCPConnection -State Listen -LocalPort 6333,6334 -ErrorAction SilentlyContinue) {
    throw "Port 6333 or 6334 is occupied. Preserve the existing service and check its configuration."
}
New-Item -ItemType Directory -Force -Path $runtimeDirectory,$logDirectory | Out-Null
$logStamp = Get-Date -Format "yyyyMMdd-HHmmss-fff"
$serverProcess = Start-Process -FilePath $qdrantExecutable `
    -ArgumentList "--config-path", "`"$qdrantConfig`"" `
    -WorkingDirectory $projectRoot -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $logDirectory "qdrant-$logStamp.stdout.log") `
    -RedirectStandardError (Join-Path $logDirectory "qdrant-$logStamp.stderr.log") -PassThru
@{
    process_id = $serverProcess.Id
    executable = $qdrantExecutable
    config = $qdrantConfig
    started_at = (Get-Date).ToUniversalTime().ToString("o")
} | ConvertTo-Json | Set-Content -LiteralPath $processFile -Encoding utf8
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    $serverProcess.Refresh()
    if ($serverProcess.HasExited) {
        throw "Qdrant exited during startup. Inspect data/server/qdrant-$logStamp.*.log."
    }
    try {
        $health = Invoke-WebRequest -Uri "http://127.0.0.1:6333/readyz" -TimeoutSec 1
        if ($health.StatusCode -eq 200) {
            Write-Host "Project Qdrant is ready at http://127.0.0.1:6333 (PID $($serverProcess.Id))."
            exit 0
        }
    } catch {
        Start-Sleep -Milliseconds 500
    }
}
throw "Qdrant startup timed out. Inspect data/server/qdrant-$logStamp.*.log."

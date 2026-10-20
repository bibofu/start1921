param(
    [ValidateSet("start", "stop", "status")]
    [string]$Action = "start"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$pgCtl = Join-Path $projectRoot "data\postgres-runtime\pgsql\bin\pg_ctl.exe"
$clusterDir = Join-Path $projectRoot "data\postgres"
$logDir = Join-Path $projectRoot "data\server"

if (-not (Test-Path -LiteralPath $pgCtl)) {
    throw "PostgreSQL binaries are missing. See POSTGRESQL.md for setup."
}
if (-not (Test-Path -LiteralPath (Join-Path $clusterDir "PG_VERSION"))) {
    throw "The local PostgreSQL cluster is not initialized. See POSTGRESQL.md."
}
if ($Action -eq "status") {
    & $pgCtl status -D $clusterDir
    exit $LASTEXITCODE
}
if ($Action -eq "start") {
    & $pgCtl status -D $clusterDir *> $null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "PostgreSQL is already running."
        exit 0
    }
}
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$arguments = @($Action, "-D", "`"$clusterDir`"", "-w", "-t", "60")
if ($Action -eq "start") {
    $arguments += @("-l", "`"$(Join-Path $logDir 'postgresql.log')`"")
} else {
    $arguments += @("-m", "fast")
}
$operationStamp = Get-Date -Format "yyyyMMdd-HHmmss-fff"
$stdoutLog = Join-Path $logDir "postgres-$Action-$operationStamp.stdout.log"
$stderrLog = Join-Path $logDir "postgres-$Action-$operationStamp.stderr.log"
$process = Start-Process -FilePath $pgCtl -ArgumentList $arguments `
    -WorkingDirectory $projectRoot -WindowStyle Hidden `
    -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog -PassThru
# Start-Process -Wait includes the persistent postgres child on Windows.
# Wait only for pg_ctl itself, which exits once the server is ready.
$process.WaitForExit()
$process.Refresh()
Get-Content -LiteralPath $stdoutLog
if ($process.ExitCode -ne 0) {
    Get-Content -LiteralPath $stderrLog
    throw "PostgreSQL $Action failed (exit $($process.ExitCode)). See data/server/postgresql.log."
}
exit 0

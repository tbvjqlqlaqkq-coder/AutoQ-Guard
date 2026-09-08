$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$pidFile = Join-Path $projectRoot ".runtime\n8n.pid"

if (-not (Test-Path -LiteralPath $pidFile)) {
    Write-Host "n8n PID file not found; nothing to stop."
    exit 0
}
$n8nPid = [int](Get-Content -LiteralPath $pidFile -Raw)
$process = Get-Process -Id $n8nPid -ErrorAction SilentlyContinue
if ($process) {
    Stop-Process -Id $n8nPid
    $process.WaitForExit(10000)
    Write-Host "n8n stopped (PID $n8nPid)."
} else {
    Write-Host "n8n process was already stopped."
}
Remove-Item -LiteralPath $pidFile -Force

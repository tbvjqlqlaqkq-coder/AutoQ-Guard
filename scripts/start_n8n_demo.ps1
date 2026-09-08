param(
    [int]$Port = 5678,
    [string]$IntegrationToken = $env:AUTOQ_INTEGRATION_TOKEN
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$n8nCommand = Join-Path $projectRoot ".runtime\n8n\node_modules\.bin\n8n.cmd"
$dataRoot = Join-Path $projectRoot ".runtime\n8n-data"
$pidFile = Join-Path $projectRoot ".runtime\n8n.pid"
$stdoutLog = Join-Path $projectRoot ".runtime\n8n.stdout.log"
$stderrLog = Join-Path $projectRoot ".runtime\n8n.stderr.log"

if (-not (Test-Path -LiteralPath $n8nCommand)) {
    throw "n8n is not installed. Run scripts\setup_n8n_demo.ps1 first."
}
if ([string]::IsNullOrWhiteSpace($IntegrationToken)) {
    throw "Set AUTOQ_INTEGRATION_TOKEN or pass -IntegrationToken."
}
if (Test-Path -LiteralPath $pidFile) {
    $existingPid = [int](Get-Content -LiteralPath $pidFile -Raw)
    if (Get-Process -Id $existingPid -ErrorAction SilentlyContinue) {
        Write-Host "n8n is already running (PID $existingPid)."
        exit 0
    }
}

New-Item -ItemType Directory -Path $dataRoot -Force | Out-Null
$env:N8N_USER_FOLDER = $dataRoot
$env:N8N_PORT = "$Port"
$env:N8N_HOST = "127.0.0.1"
$env:N8N_DIAGNOSTICS_ENABLED = "false"
$env:N8N_BLOCK_ENV_ACCESS_IN_NODE = "false"
$env:AUTOQ_INTEGRATION_TOKEN = $IntegrationToken
$process = Start-Process -FilePath $n8nCommand -ArgumentList "start" -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog
Set-Content -LiteralPath $pidFile -Value $process.Id
Write-Host "n8n started: http://127.0.0.1:$Port (PID $($process.Id))"

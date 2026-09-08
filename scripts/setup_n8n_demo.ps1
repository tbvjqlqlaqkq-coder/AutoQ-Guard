param([string]$Version = "2.37.10")

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$runtimeRoot = Join-Path $projectRoot ".runtime\n8n"
$cacheRoot = Join-Path $projectRoot ".runtime\npm-cache"
New-Item -ItemType Directory -Path $runtimeRoot -Force | Out-Null
New-Item -ItemType Directory -Path $cacheRoot -Force | Out-Null
npm install --prefix $runtimeRoot "n8n@$Version" --cache $cacheRoot --no-audit --no-fund
Write-Host "n8n $Version setup complete: $runtimeRoot"

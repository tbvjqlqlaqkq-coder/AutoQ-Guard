param([string]$N8nUrl = "http://127.0.0.1:5678")

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$eventPath = Join-Path $projectRoot "n8n\medical-device-test-event.json"
$body = Get-Content -LiteralPath $eventPath -Raw
$uri = "$($N8nUrl.TrimEnd('/'))/webhook/autoq-quality-event"
$result = Invoke-RestMethod -Uri $uri -Method Post -ContentType "application/json" -Body $body
$result | ConvertTo-Json -Depth 8

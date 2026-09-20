$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$stateFile = Join-Path $projectRoot '.run/tls-demo.json'

if (-not (Test-Path $stateFile)) {
    throw '找不到本專案啟動的 TLS 示範服務紀錄。'
}

$state = Get-Content -Raw $stateFile | ConvertFrom-Json
foreach ($processId in @($state.proxy_pid, $state.app_pid)) {
    $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
    if ($process) {
        Stop-Process -Id $processId
    }
}
Remove-Item -LiteralPath $stateFile
Write-Host 'TLS 示範服務已停止。'

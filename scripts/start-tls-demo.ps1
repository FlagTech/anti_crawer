$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

$occupiedPorts = Get-NetTCPConnection -State Listen -LocalPort 8000,8443 -ErrorAction SilentlyContinue
if ($occupiedPorts) {
    $ports = ($occupiedPorts | Select-Object -ExpandProperty LocalPort -Unique) -join ', '
    throw "連接埠 $ports 已被使用。請先停止既有服務，再啟動 TLS 示範。"
}

if (-not (Test-Path 'certs/localhost.pem') -or -not (Test-Path 'certs/localhost-key.pem')) {
    throw '找不到 certs/localhost.pem 或 certs/localhost-key.pem。請先執行 mkcert 建立本機憑證。'
}

# mitmproxy requires a PEM containing the private key followed by the leaf cert.
$combinedCertificate = 'certs/mitmproxy-localhost.pem'
$key = Get-Content -Raw 'certs/localhost-key.pem'
$certificate = Get-Content -Raw 'certs/localhost.pem'
Set-Content -Path $combinedCertificate -Value "$key`n$certificate" -NoNewline
$env:TLS_PROXY_SECRET = 'local-tls-demo-proxy-only'

$app = Start-Process -FilePath '.venv/Scripts/python.exe' -ArgumentList '-m', 'uvicorn', 'anti_crawler_demo.app:app', '--host', '127.0.0.1', '--port', '8000' -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru
$proxy = Start-Process -FilePath '.venv/Scripts/mitmdump.exe' -ArgumentList '--mode', 'reverse:http://127.0.0.1:8000@8443', '--set', 'certs=localhost=certs/mitmproxy-localhost.pem', '--set', 'upstream_cert=false', '--set', 'connection_strategy_lazy', '--set', 'onboarding=false', '--set', 'termlog_verbosity=warn', '-s', 'proxy/tls_fingerprint_addon.py' -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru

New-Item -ItemType Directory -Force '.run' | Out-Null
@{ app_pid = $app.Id; proxy_pid = $proxy.Id } | ConvertTo-Json | Set-Content '.run/tls-demo.json'

Write-Host 'TLS 示範服務已啟動： https://localhost:8443/tls-fingerprint'
Write-Host '停止服務： .\scripts\stop-tls-demo.ps1'

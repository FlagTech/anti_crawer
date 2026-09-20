#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

if lsof -nP -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1 || lsof -nP -iTCP:8443 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "連接埠 8000 或 8443 已被使用。請先停止既有服務，再啟動 TLS 示範。" >&2
  exit 1
fi

if [[ ! -f certs/localhost.pem || ! -f certs/localhost-key.pem ]]; then
  echo "找不到 certs/localhost.pem 或 certs/localhost-key.pem。請先用 mkcert 建立本機憑證。" >&2
  exit 1
fi

mkdir -p .run
cat certs/localhost-key.pem certs/localhost.pem > certs/mitmproxy-localhost.pem
export TLS_PROXY_SECRET="local-tls-demo-proxy-only"

.venv/bin/python -m uvicorn anti_crawler_demo.app:app --host 127.0.0.1 --port 8000 >.run/tls-app.log 2>&1 &
app_pid=$!
.venv/bin/mitmdump --mode reverse:http://127.0.0.1:8000@8443 \
  --set certs=localhost=certs/mitmproxy-localhost.pem \
  --set upstream_cert=false \
  --set connection_strategy_lazy \
  --set onboarding=false \
  --set termlog_verbosity=warn \
  -s proxy/tls_fingerprint_addon.py >.run/tls-proxy.log 2>&1 &
proxy_pid=$!

printf 'APP_PID=%s\nPROXY_PID=%s\n' "$app_pid" "$proxy_pid" > .run/tls-demo.env
sleep 1
if ! kill -0 "$app_pid" 2>/dev/null || ! kill -0 "$proxy_pid" 2>/dev/null; then
  echo "TLS 示範服務啟動失敗；請查看 .run/tls-app.log 與 .run/tls-proxy.log。" >&2
  bash scripts/stop-tls-demo.sh || true
  exit 1
fi

echo "TLS 示範服務已啟動： https://localhost:8443/tls-fingerprint"
echo "停止服務： bash scripts/stop-tls-demo.sh"

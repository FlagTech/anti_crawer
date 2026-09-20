#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
state_file="$project_root/.run/tls-demo.env"

if [[ ! -f "$state_file" ]]; then
  echo "找不到本專案啟動的 TLS 示範服務紀錄。" >&2
  exit 1
fi

# shellcheck disable=SC1090
source "$state_file"
for process_id in "$PROXY_PID" "$APP_PID"; do
  if kill -0 "$process_id" 2>/dev/null; then
    kill "$process_id"
  fi
done
rm -f "$state_file"
echo "TLS 示範服務已停止。"

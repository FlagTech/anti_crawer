# 反爬蟲情境測試站

這是一個以 FastAPI 製作、僅供本機訓練的反爬蟲示範網站。每個網址只套用一種技術，並以「城市零售指數」報告表格作為實際抓取目標：一般使用者可在瀏覽器查看正常結果；curl 或 Python 程式則可驗證哪些請求會被阻擋、為什麼被阻擋，以及合規的取得方式。

> 這是防護與測試教材，不是繞過第三方網站防護的工具。請只對自己擁有或獲授權測試的系統使用這些技巧。

## 快速開始（Windows／PowerShell）

### 1. 安裝必要工具

本專案使用 [uv](https://docs.astral.sh/uv/) 管理 Python。若電腦尚未安裝 uv，Windows 可使用 Scoop：

```powershell
scoop install uv
```

複製專案後，安裝鎖定的 Python 相依套件：

```powershell
git clone https://github.com/FlagTech/anti_crawer.git
Set-Location anti_crawer
uv sync
```

若要執行動態內容、CAPTCHA 模擬等 Playwright 範例，另安裝一次 Chromium：

```powershell
uv run playwright install chromium
```

### 2. 啟動一般 HTTP 示範

```powershell
uv run anti-crawler-demo
```

開啟 [http://127.0.0.1:8000](http://127.0.0.1:8000)。除 TLS 指紋外的所有情境都可在此測試。按 `Ctrl+C` 停止服務。

### 3. 啟動 TLS ClientHello／JA3 情境

TLS 情境需要本機受信任的開發憑證與 HTTPS 反向代理。先停止前一步的 HTTP 服務，再只需做一次以下初始化：

```powershell
scoop install mkcert
mkcert -install
New-Item -ItemType Directory -Force certs
mkcert -cert-file certs/localhost.pem -key-file certs/localhost-key.pem localhost 127.0.0.1 ::1
```

`mkcert -install` 只將本機開發根憑證安裝到目前電腦的信任存放區；`certs/` 已列入 `.gitignore`，絕不可提交私密金鑰。

啟動 HTTPS 服務：

```powershell
.\scripts\start-tls-demo.ps1
```

若 PowerShell 的執行政策阻止腳本，可僅對這次執行使用：

```powershell
pwsh -ExecutionPolicy Bypass -File .\scripts\start-tls-demo.ps1
```

開啟 [https://localhost:8443/tls-fingerprint](https://localhost:8443/tls-fingerprint)。此腳本在背景啟動 FastAPI（`127.0.0.1:8000`）與 mitmproxy HTTPS 反向代理（`localhost:8443`）。

停止這兩個由腳本啟動的程序：

```powershell
.\scripts\stop-tls-demo.ps1
```

## macOS（Homebrew）

網站程式與所有 Python 範例同樣支援 macOS；Apple Silicon 與 Intel Mac 都可使用 uv。先安裝工具並同步相依套件：

```bash
brew install uv mkcert
git clone https://github.com/FlagTech/anti_crawer.git
cd anti_crawer
uv sync
uv run playwright install chromium  # 僅動態／CAPTCHA Playwright 範例需要
```

一般 HTTP 示範的啟動方式相同：

```bash
uv run anti-crawler-demo
```

TLS 情境只需首次建立本機憑證：

```bash
mkcert -install
mkdir -p certs
mkcert -cert-file certs/localhost.pem -key-file certs/localhost-key.pem localhost 127.0.0.1 ::1
bash scripts/start-tls-demo.sh
```

瀏覽 [https://localhost:8443/tls-fingerprint](https://localhost:8443/tls-fingerprint)，停止時執行：

```bash
bash scripts/stop-tls-demo.sh
```

若以 Firefox 測試，mkcert 官方建議另安裝 `nss`：`brew install nss`。`certs/` 包含私密金鑰，仍不可提交到 Git。

## 情境一覽

| 路徑 | 單一規則 | 預期觀察 |
| --- | --- | --- |
| `/rate-limit` | 10 秒內最多讀取 5 個索引或報告頁 | 第 6 次回 `429` 與 `Retry-After` |
| `/header-policy` | 要求 `Accept: text/html` 與瀏覽器型態 User-Agent | 缺少標頭時整頁回 `403` |
| `/session-gate` | 需先建立登入工作階段 cookie | 直接讀取回 `401` |
| `/deferred-content` | 資料列由頁面 JavaScript 載入 | 初始 HTML 沒有 `<tbody>` 資料列 |
| `/js-token` | 短效、一次性挑戰權杖 | 頁面流程完成後才渲染表格 |
| `/captcha-sim` | 本機算術驗證流程 | 手動答題後才顯示表格 |
| `/robots-honeypot` | robots.txt 與禁止的誘餌路徑 | 存取 `/training-honeypot` 回 `403` |
| `/tls-fingerprint` | TLS ClientHello／JA3 型態檢查 | `requests`／curl 被擋；Chrome 型態指紋可通過 |

每個頁面都有可展開的 curl 與 Python 卡片、阻擋原因，以及合規的測試方式。阻擋回應皆含 `X-Training-Rule` 標頭。

## 執行範例與測試

Python 對應範例位於 [`examples/python`](examples/python)。預設連到 `http://127.0.0.1:8000`，也可將基底網址作為第一個參數傳入。

```powershell
# 速率限制：程式會在 429 後讀取 Retry-After 並重試
uv run python examples/python/rate_limit_backoff.py

# 動態內容：以 Chromium 等待資料列
uv run python examples/python/deferred_content_passed.py

# TLS：一般 requests 被擋，curl-cffi 模擬 Chrome 指紋後可通過
uv run python examples/python/tls_fingerprint_blocked.py https://localhost:8443
uv run python examples/python/tls_fingerprint_passed.py https://localhost:8443

# 單元測試
uv run pytest -q
```

## TLS 的命令列測試

原生 curl 的 TLS 堆疊不會因為設定 User-Agent 而改變，因此此情境預期被阻擋：

```powershell
curl.exe -k -i https://localhost:8443/tls-fingerprint
```

curl-cffi 提供 CLI，也能以 Chrome 型態發出 TLS／HTTP/2 請求：

```powershell
uv run curl-cffi get https://localhost:8443/tls-fingerprint --impersonate chrome --no-verify --headers
```

這個 CLI 目前沒有指定自訂 CA 檔案的選項，因此 `--no-verify` **只適用於本專案的 localhost 訓練憑證**。正式系統不可略過憑證驗證。若要完整驗證 mkcert 憑證，請使用 `tls_fingerprint_passed.py`；它會明確指定 mkcert 的 `rootCA.pem`。

## 部署到 Railway

Railway 適合部署一般展示情境；但它的公開 HTTPS 網域會先在 Railway 邊緣終止 TLS，再將 HTTP 轉送至應用程式。因此 `/tls-fingerprint` 無法取得訪客原始的 TLS ClientHello，會依設計回覆 `403 tls-proxy-required`。其餘情境可正常運作。

在 Railway 建立 Project 後，選擇從 `FlagTech/anti_crawer` 的 `master` 分支部署，並在服務的 Deploy 設定填入：

```text
Build Command: pip install .
Start Command: python -m uvicorn anti_crawler_demo.app:app --host 0.0.0.0 --port $PORT
Healthcheck Path: /
```

接著在 Networking 產生公開網域。請維持單一 replica：本站的 session、速率計數與挑戰 token 都在記憶體中，多個 replica 會讓同一測試工作階段落到不同 instance，導致結果不穩定。

若必須公開展示真實 TLS 指紋，需使用 Railway TCP Proxy，將 raw TCP 轉送到自行管理的 TLS 終端（例如 mitmproxy），再以 Railway Private Networking 連到 FastAPI。TCP Proxy 會使用 Railway 指派的非標準連接埠，且公開憑證／私鑰需自行管理；通常更適合部署於能直接控制 443 與 TLS 終端的 VM。完整架構與限制請見[技術文件的 Railway 部署章節](docs/technical-guide.md#railway-部署)。

## 延伸文件

完整的架構、每項情境的請求流程、TLS 指紋實作與限制，請見[技術文件](docs/technical-guide.md)。

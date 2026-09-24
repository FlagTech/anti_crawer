# 反爬蟲情境測試站：技術文件

## 目的與範圍

本專案是可重現的本機訓練環境。它把反自動化控制拆成獨立 URL，避免多項規則疊加後無法判斷阻擋來源。每個情境都用相同的「2026 年 8 月城市零售指數」表格作為抓取目標，使測試者能比較：

1. 一般瀏覽器正常能看到的完整 HTML 或渲染後表格。
2. curl、`requests` 等不同 HTTP client 的實際回應。
3. 被擋時的 HTTP status、`X-Training-Rule` 與中文阻擋原因。
4. 在擁有測試授權的前提下，符合該情境設計的正確存取方式。

本專案不儲存真實帳號、資料或第三方 CAPTCHA 結果。session、挑戰 token、速率計數與事件資料只保留在記憶體，服務停止即清除。

## 系統架構

一般情境只有一個 FastAPI 服務：

```text
瀏覽器／curl／Python client
              │ HTTP :8000
              ▼
       FastAPI + Jinja2
              │
              ▼
     訓練資料表／阻擋說明頁
```

TLS 指紋情境必須在 TLS 終端處取得 ClientHello，因此額外使用反向代理：

```text
Chrome、curl、requests、curl-cffi
              │ HTTPS :8443，先送出 ClientHello
              ▼
 mitmproxy + tls_fingerprint_addon.py
    ├─ 計算 JA3
    ├─ 判定受控瀏覽器型態基線
    └─ 注入僅供內部使用的訓練標頭
              │ HTTP :8000
              ▼
        FastAPI /tls-fingerprint
```

FastAPI 不會自行「看見」TLS ClientHello；TLS 已在反向代理處結束。代理會注入 `X-Training-TLS-Proxy`、`X-Training-TLS-JA3` 與分類標頭；應用程式同時檢查共享的本機訓練密鑰，避免把一般 client 自行送出的同名標頭當成可信訊號。

這個 header 信任模式只適合「應用程式只暴露給受控反向代理」的部署。正式環境應將上游服務限制在私有網路、由反向代理移除外部同名標頭，並用安全的 secret 管理機制取代教學用預設值。

## 平台支援與本機啟動

應用程式本體、uv 鎖定檔與 Python 範例支援 Windows 與 macOS；它們不依賴 Windows 專用 API。Windows 提供 PowerShell 的 `start-tls-demo.ps1`／`stop-tls-demo.ps1`，macOS 提供相同功能的 `start-tls-demo.sh`／`stop-tls-demo.sh`。兩種腳本都會啟動 FastAPI 上游（8000）及 mitmproxy TLS 終端（8443），並把執行期 PID 與 log 寫入已忽略的 `.run/`。

macOS 使用 Homebrew 的最小安裝步驟：

```bash
brew install uv mkcert
uv sync
uv run playwright install chromium  # 只有 Playwright 範例需要
mkcert -install
mkdir -p certs
mkcert -cert-file certs/localhost.pem -key-file certs/localhost-key.pem localhost 127.0.0.1 ::1
bash scripts/start-tls-demo.sh
```

`mkcert -install` 會將本機 CA 加入 macOS 系統信任存放區；Firefox 使用自己的 NSS 資料庫時，另裝 `brew install nss`。停止 TLS 示範請執行 `bash scripts/stop-tls-demo.sh`。uv 與 mkcert 均提供 Homebrew 安裝方式。[uv 安裝文件](https://docs.astral.sh/uv/getting-started/installation/) [mkcert 文件](https://github.com/FiloSottile/mkcert)

## 範例卡的閱讀方式

每個情境頁的四張展開卡都附有與該段程式碼相對應的說明，不只列出命令。常見的 curl 選項如下：

| 選項 | 實際作用 | 使用情境 |
| --- | --- | --- |
| `-s` | 關閉進度列與一般錯誤訊息；不改變 HTTP 請求，只讓 stdout 適合交給管線 | 靜態或動態 HTML 的輸出檢查 |
| `-i` | 將回應的 status line 和 headers 接在輸出前；不會新增 request header | 觀察 `403`、`429`、`Retry-After`、`Location`、`X-Training-Rule` |
| `-H '名稱: 值'` | 逐字加入一個 request header；可重複使用以加入多個標頭 | header-policy 的 `Accept: text/html` |
| `-A 值` | 將 `User-Agent` request header 設為指定值，是 `-H 'User-Agent: 值'` 的捷徑 | header-policy 的瀏覽器型態 UA |
| `-c FILE` | 收到回應後，將 Set-Cookie 寫成 Netscape cookie jar 檔；不會自動在下一條命令使用它 | rate-limit、登入 session |
| `-b FILE` | 讀取 cookie jar，並在 request 中產生 `Cookie` header | 以同一個用戶端識別碼繼續請求 |
| `-L` | 收到 3xx 與 `Location` 後自動再發出下一個請求；本登入流程的 303 會以 GET 讀取目標頁 | 登入成功後抵達受保護資料頁 |
| `-d 資料` | 把欄位編碼為 `application/x-www-form-urlencoded` request body；沒有 `-X` 時 curl 會使用 POST | session-gate 登入表單 |

管線中的 `|` 會把左側程式的標準輸出交給右側程式；`grep -A 30 PATTERN` 則用正規表示式尋找 `PATTERN`，並多印命中行後 30 行。兩者只改變本機終端輸出，不會改變 HTTP 請求。

TLS 情境中的 `uv run curl-cffi get ... --impersonate chrome --no-verify --headers` 不是原生 curl 的替代參數：`get` 選擇 GET 子命令，`--impersonate chrome` 選擇 Chrome 型態的 TLS／HTTP/2 指紋，`--headers` 將回應標頭輸出；`--no-verify` 會略過伺服器憑證鏈驗證，只可用在本機 mkcert 教材，不能用於正式服務。

Python 卡片也說明使用的層次：靜態頁使用 `requests` 取得初始 HTML 再由 Beautiful Soup 以 CSS selector 解析；登入與限流情境使用 `requests.Session()` 保存 cookie；動態、token 與 CAPTCHA 情境使用 Playwright 執行頁面 JavaScript 並等待 DOM 狀態；TLS 情境使用 curl-cffi 的 Chrome impersonation。這些範例只針對本站授權測試環境，不應套用於未授權的網站。

## 各情境行為

### 基本公開資料頁（`/basic`）

此頁是其他情境的對照組，不套用任何反爬蟲規則。完整資料表直接存在初始 HTML，因此 curl、requests 與 Beautiful Soup 都可在一次 GET 請求後取得資料列。`basic_public_page.py` 展示最小的靜態表格解析方式。

### 請求頻率限制（`/rate-limit`）

索引頁與六份報告詳情頁共用同一個 session cookie 的滑動視窗：10 秒最多 5 次讀取。第 6 次回覆 `429 Too Many Requests`，並提供 `Retry-After`。資料表內的「閱讀報告」連結模擬爬蟲從索引追蹤多個詳細頁；`rate_limit_backoff.py` 會保存 cookie、解析連結、在得到 429 時等待指定秒數後重試。

### 請求標頭檢查（`/header-policy`）

整個 HTML 文件要求 `Accept: text/html` 和 Mozilla 型態的 User-Agent；缺少任一條件即回 `403`。這是最小化的教材規則，實務上不應把 User-Agent 當作身分證明，因為它可被任意偽造。

### 無頭模式標頭檢查（`/headless-header`）

此頁只檢查 `User-Agent` 是否含有 `HeadlessChrome`。部分舊版 Chrome／自動化工具在無頭模式下會留下這個產品標記；命中時伺服器在回傳整份 HTML 前以 `403 headless-user-agent` 阻擋，未命中時則直接回傳資料表。

這是刻意簡化的「標頭特徵」示範，並非可靠的無頭偵測。User-Agent 可被任意設定，新版 Chrome headless 模式也可能使用與一般 Chrome 相同的 User-Agent。實務上應將它視為低可信度訊號，與行為、session、節流、瀏覽器完整性與風險評分一起使用，而不是把改寫 User-Agent 當成安全邊界。

### 登入工作階段保護（`/session-gate`）

`/session-gate/login` 提供真實的表單登入流程；唯一訓練帳號為 `learner@example.test`，密碼為 `DemoPass!2026`。帳密驗證成功後，伺服器建立獨立、HttpOnly 的 `demo_session` cookie，再以 303 redirect 到受保護頁。直接請求 `/session-gate` 不會有資料表，而會以 303 導向登入頁。這模擬網站在登入後由伺服器保存工作階段的情境，而不是以固定 header 解鎖。

### 動態內容載入（`/deferred-content`）

初始 HTML 只有表格結構。頁面 JavaScript 發出受控的非同步請求後才插入 `<tbody>` 資料列，因此 `requests + BeautifulSoup` 只能讀到空表格；Playwright 必須等待資料列出現。

動態載入不是完整的存取控制：若資料端點沒有伺服器端限制，只要知道端點仍可能取得資料。本情境用來說明「取得 HTML」與「取得頁面渲染結果」的差異。

### JavaScript 短效權杖（`/js-token`）

頁面先取得 30 秒有效、只能使用一次的 challenge token，再以 token 讀取資料。正式系統的權杖應綁定 session、過期時間與 nonce，避免重放。它與登入後的 access token 不同：前者用於證明本次請求已完成反自動化挑戰，後者用於辨識使用者和授權範圍；正式服務可同時要求兩者。

### CAPTCHA 模擬（`/captcha-sim`）

這是本機的一次性算術題，不使用第三方 CAPTCHA。一般使用者可填答並按鈕驗證；自動化測試使用 Playwright 操作同一個頁面。它只展示「互動挑戰成功後才顯示資料」的狀態流程，不宣稱具備商用 CAPTCHA 的安全性。

### robots.txt 與誘餌路徑（`/robots.txt`、`/training-honeypot`）

`robots.txt` 宣告禁止 `/training-honeypot`。它是爬蟲禮儀協定，不是存取控制；實際阻擋由 honeypot 路徑本身的 `403` 完成並留下訓練事件。合規爬蟲應先讀取 robots 規則，並排除禁止路徑。

### TLS ClientHello／JA3（`/tls-fingerprint`）

TLS ClientHello 是 HTTPS 握手中的第一個 client 訊息，發生在 HTTP request headers 之前。代理會從 ClientHello 取出：

- TLS legacy version
- cipher suites
- TLS extension IDs
- supported groups
- EC point formats

JA3 將上述欄位（忽略 GREASE 值）串成固定格式後計算 MD5。`proxy/tls_fingerprint_addon.py` 也檢查 ClientHello 是否同時呈現現代 Chromium 常見的 GREASE 值與 `h2` ALPN，作為此教材的「browser-like」基線。

`requests` 與原生 curl 使用不同的 TLS 函式庫，因此雖可任意修改 HTTP User-Agent，ClientHello 仍不符合基線而回 `403 tls-fingerprint-mismatch`。`curl-cffi` 以 `impersonate="chrome"` 發出 Chrome 型態的 TLS／HTTP/2 指紋，故本機範例會通過。

## TLS 指紋的重要限制

TLS 指紋不是使用者身分，也不是不可偽造的安全證明。瀏覽器更新、作業系統 TLS 函式庫、代理、企業安全設備與網路協定都可能改變指紋；專門的 client 亦可模擬它。正式環境應將它視為風險訊號，搭配帳號信譽、session、節流、行為特徵、IP／網路信譽和人工挑戰，而非單獨作為封鎖依據。

curl-cffi 的 browser impersonation 由 libcurl-impersonate 整合提供；它可模擬 TLS／JA3 與 HTTP/2 指紋，但不提供一般瀏覽器的 JavaScript runtime。[curl-cffi 官方文件](https://curl-cffi.readthedocs.io/en/latest/quick_start.html)

## TLS 開發憑證與信任鏈

`mkcert` 會建立本機開發 CA，並可將 CA 安裝到作業系統信任存放區。專案使用它簽發只包含 `localhost`、`127.0.0.1` 與 `::1` 的葉端憑證。mitmproxy 可使用含私鑰與憑證的 PEM 作為自訂伺服器憑證。[mitmproxy 憑證文件](https://docs.mitmproxy.org/stable/concepts/certificates/)

Python `requests` 不一定讀取 Windows 信任存放區，因此 `tls_fingerprint_blocked.py` 與 `tls_fingerprint_passed.py` 都會取得 `mkcert -CAROOT` 結果，並指定該位置的 `rootCA.pem`。這能確保範例是在「已驗證本機憑證」的情況下被 TLS 指紋規則擋下或通過。

curl-cffi CLI 的 `--no-verify` 只應用於本機示範，絕不能延伸到公開網站或正式環境。

## Railway 部署

### 可直接部署的範圍

Railway 的一般公開網域由平台邊緣處理 HTTPS，應用程式收到的是平台轉送的 HTTP 請求。這使 `/rate-limit`、`/header-policy`、`/headless-header`、`/session-gate`、`/deferred-content`、`/js-token`、`/captcha-sim` 與 `/robots-honeypot` 都可正常公開展示；但 `/tls-fingerprint` 無法看見訪客原始 ClientHello，會回覆 `403 tls-proxy-required`。這是預期行為，不應在 Railway 上以任意 HTTP header 偽造 TLS 訊號。

部署步驟如下：

1. 在 Railway 建立 Project，選擇 **Deploy from GitHub repo**，並連結 `FlagTech/anti_crawer` 的 `master` 分支。
2. 在該服務的 Deploy 設定覆寫以下設定：

   ```text
   Build Command: pip install .
   Start Command: python -m uvicorn anti_crawler_demo.app:app --host 0.0.0.0 --port $PORT
   Healthcheck Path: /
   ```

3. 在 Networking 產生 Railway 網域或新增自有網域。
4. 將服務維持為 **單一 replica**。

Railway 注入 `PORT` 變數，公開 HTTP 服務必須監聽該 port。Healthcheck 必須回傳 2xx，才會被 Railway 視為可接收流量；本站的 `/` 已符合此要求。[Railway FastAPI 指南](https://docs.railway.com/guides/fastapi) [Railway healthcheck 文件](https://docs.railway.com/deployments/healthchecks)

本站所有狀態都在記憶體：若啟用多 replica、重新部署或服務重新啟動，session、token、CAPTCHA 挑戰和速率計數都不會共享或保留。若未來要水平擴充，應將這些狀態移至 Redis 或資料庫，並重新設計 client/session affinity。

### 在 Railway 保留 TLS ClientHello 的替代架構

若要保留真正的 TLS 指紋檢查，不能使用 Railway 的一般 HTTPS 網域作為 TLS 終端。可行但較不便利的架構是：

```text
使用者
  │ HTTPS（自訂網域 + Railway 指派的 TCP port）
  ▼
Railway TCP Proxy
  ▼
自管 TLS proxy（擷取 ClientHello、終止 TLS）
  │ Railway Private Networking
  ▼
FastAPI 服務
```

Railway TCP Proxy 會把 raw TCP 轉送到指定的內部 port，因此 TLS proxy 可以收到 ClientHello。它會提供一個網域與連接埠；即使設定自有網域，使用者仍須使用 Railway 指派的 port。自管 proxy 也必須負責公開可驗證的憑證和私鑰。Railway 一般公開網域不支援匯入外部 SSL 憑證。[Railway TCP Proxy 文件](https://docs.railway.com/networking/tcp-proxy) [Railway 網域與憑證文件](https://docs.railway.com/networking/domains/working-with-domains)

因此，若目標是讓一般使用者以標準 `https://example.com:443` 使用 TLS 指紋示範，較好的選擇是可直接控制 443 與 TLS 終端的 VM 或容器平台。Railway 可作為一般展示站，並將 TLS 指紋情境保留在本機或專用 TLS proxy 環境。

## 開發與驗證

```powershell
uv sync
uv run pytest -q

# TLS 反向代理啟動後的行為檢查
uv run python examples/python/tls_fingerprint_blocked.py https://localhost:8443
uv run python examples/python/tls_fingerprint_passed.py https://localhost:8443
```

預期結果：第一個 TLS 範例印出 `403 tls-fingerprint-mismatch`；第二個印出 `200` 和六筆表格資料。

## 維運與安全注意事項

- 不要將 `certs/`、私密金鑰、session cookie 或真實 access token 提交到 Git。
- 不要將此示範的 `TLS_PROXY_SECRET` 預設值部署到公開環境。
- TLS 情境應只綁定 localhost；不要把 `8443` 對外公開。
- 觀測資料排除 `Authorization` 與 `Proxy-Authorization` 標頭，也不保存 request body。
- 停止服務後，記憶體中的訓練狀態會消失；這是設計使然。

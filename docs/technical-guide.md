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

## 各情境行為

### 請求頻率限制（`/rate-limit`）

索引頁與六份報告詳情頁共用同一個 session cookie 的滑動視窗：10 秒最多 5 次讀取。第 6 次回覆 `429 Too Many Requests`，並提供 `Retry-After`。資料表內的「閱讀報告」連結模擬爬蟲從索引追蹤多個詳細頁；`rate_limit_backoff.py` 會保存 cookie、解析連結、在得到 429 時等待指定秒數後重試。

### 請求標頭檢查（`/header-policy`）

整個 HTML 文件要求 `Accept: text/html` 和 Mozilla 型態的 User-Agent；缺少任一條件即回 `403`。這是最小化的教材規則，實務上不應把 User-Agent 當作身分證明，因為它可被任意偽造。

### 登入工作階段保護（`/session-gate`）

`/session-gate/start` 建立示範 session cookie，再以 303 redirect 到受保護頁。直接請求 `/session-gate` 不會有資料表，並回 `401`。這模擬網站在登入後由伺服器保存工作階段的情境，而不是以固定 header 解鎖。

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

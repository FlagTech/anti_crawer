from __future__ import annotations

import hashlib
import os
import secrets
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

from fastapi import Cookie, FastAPI, Header, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

ROOT = Path(__file__).parent
SESSION_COOKIE = "demo_session"
TRAINING_USERNAME = "learner@example.test"
TRAINING_PASSWORD = "DemoPass!2026"
DEMOS = {
    "basic": ("基本公開資料頁（No protection）", "不套用反爬蟲規則", "最簡易的對照組：完整資料表直接出現在 HTML，任何一般 HTTP client 都可讀取。"),
    "rate-limit": ("請求頻率限制（Rate limiting）", "10 秒內最多讀取 5 個頁面", "模擬爬蟲從索引追蹤多份報告時，伺服器如何以滑動視窗限制連續讀取。"),
    "header-policy": ("請求標頭檢查（Header policy）", "要求合理的網頁導覽標頭", "比較缺少標頭的自動請求與符合網頁導覽條件的完整 HTML 回應。"),
    "headless-header": ("無頭模式標頭檢查（Headless header）", "拒絕含 HeadlessChrome 的 User-Agent", "模擬網站由 User-Agent 內的無頭瀏覽器標記辨識自動化工具，並回傳整頁 403。"),
    "session-gate": ("登入工作階段保護（Session gate）", "必須先登入才能讀取資料", "模擬會員登入後才可閱讀受保護資料；沒有有效工作階段時不提供資料表。"),
    "deferred-content": ("動態內容載入（Deferred content）", "資料列在頁面載入後取得", "初始文件不含資料列，需由能執行 JavaScript 的瀏覽器完成載入。"),
    "js-token": ("JavaScript 短效權杖（JavaScript token）", "需取得一次性短效權杖", "頁面完成短暫的 JavaScript 流程後才會取得資料列。"),
    "captcha-sim": ("人機驗證模擬（CAPTCHA simulation）", "需完成受控挑戰流程", "以本機訓練用的簡易挑戰流程模擬人機驗證後的資料存取。"),
    "robots-honeypot": ("爬蟲規則與誘餌路徑（robots.txt + honeypot）", "記錄禁止路徑的存取", "展示 robots.txt 與不公開誘餌路徑如何協助觀測不遵守規則的自動工具。"),
    "tls-fingerprint": ("TLS ClientHello 指紋（TLS fingerprint）", "檢查 TLS 連線的用戶端指紋", "由 HTTPS 反向代理擷取 ClientHello，依受控的瀏覽器型態基線決定是否提供資料表。"),
}
DATASET = [
    {"id": "R-101", "name": "臺北市零售指數", "period": "2026-08", "value": "108.4", "published": "2026-09-02 09:00"},
    {"id": "R-102", "name": "新北市零售指數", "period": "2026-08", "value": "106.9", "published": "2026-09-08 14:30"},
    {"id": "R-103", "name": "桃園市零售指數", "period": "2026-08", "value": "109.7", "published": "2026-09-15 10:15"},
    {"id": "R-104", "name": "臺中市零售指數", "period": "2026-08", "value": "107.2", "published": "2026-09-23 16:45"},
    {"id": "R-105", "name": "臺南市零售指數", "period": "2026-08", "value": "105.8", "published": "2026-10-01 11:20"},
    {"id": "R-106", "name": "高雄市零售指數", "period": "2026-08", "value": "107.6", "published": "2026-10-07 15:10"},
]
TECHNIQUE_INFO = {
    "basic": ("無反爬蟲保護", "整頁 HTML 直接包含資料表，沒有 cookie、標頭、登入、JavaScript、速率或 TLS 指紋條件。", "直接用 curl 或 requests 取得本頁，再以 Beautiful Soup 選取 #dataset-table 的資料列即可。此頁是用來對照其他單一防護情境的基準。"),
    "rate-limit": ("滑動視窗限流", "索引與報告詳情頁共用 10 秒最多 5 次的讀取配額；超限回傳 429 與 Retry-After。", "保存同一個 session cookie，遇到 429 時讀取 Retry-After、等待後再重試。"),
    "header-policy": ("導覽標頭檢查", "整個 HTML 頁面要求 Accept: text/html 與瀏覽器樣式 User-Agent，缺少時回傳 403。", "在受控測試中提供網站要求的兩個標頭，再解析回傳的完整 HTML。"),
    "headless-header": ("無頭模式 User-Agent 標記檢查", "此頁只讀取 HTTP `User-Agent`。若值中包含 `HeadlessChrome`（部分自動化瀏覽器預設會附帶的產品標記），便拒絕整份 HTML 並回傳 403。沒有此標記時，資料表直接存在回應中。", "這是觀察標頭差異的教材，不是可靠的身分驗證：User-Agent 可被改寫，且新版 Chrome 的 headless 模式未必含此字串。合規測試應使用正式瀏覽器設定或網站核准的自動化方式；實務上需結合其他伺服器端風險訊號。"),
    "session-gate": ("登入後的工作階段驗證", "模擬會員在登入頁以唯一的訓練帳號與密碼送出表單；伺服器驗證成功後建立獨立、HttpOnly 的 session cookie，才會提供受保護資料頁。", "一般使用者在登入頁輸入 learner@example.test／DemoPass!2026；程式則以 Session 保存 cookie，POST 表單到 /session-gate/login 後再抓取 /session-gate。"),
    "deferred-content": ("動態資料載入", "初始 HTML 只提供表格結構，資料列由頁面 JavaScript 自動非同步載入。", "使用 Playwright 等可執行 JavaScript 的瀏覽器工具，等待資料列出現。"),
    "js-token": (
        "JavaScript 短效挑戰權杖",
        "此機制不只是把資料改成動態載入：資料端點會要求一次性、短效的 challenge token。流程通常為：① 載入頁面與挑戰腳本；② 頁面 JavaScript 送出挑戰結果，向伺服器換取 token；③ JavaScript 帶 token 請求資料並渲染表格。這三步都由頁面自動完成。正式環境會驗證挑戰結果，並將 token 綁定目前的 session、過期時間與一次性 nonce，避免竄改或重放。",
        "這是反自動化用的 challenge token，不等於登入後的 access token：登入憑證用來辨識使用者與授權範圍；challenge token 用來證明這次請求已通過反自動化檢查。受保護 API 可同時要求兩者。合規的網頁用戶端應讓瀏覽器執行流程、取得短效 token 後立即使用；純 HTTP client 無法自動完成此流程。",
    ),
    "captcha-sim": ("互動式人機驗證模擬", "資料表需在使用者手動完成受控的一次性算術題目後才會出現；未填答或答案錯誤時不載入資料。", "一般使用者在頁面輸入答案並按下驗證按鈕；自動化測試可用 Playwright 讀取題目、填答並送出。此為本機訓練模擬，不串接第三方商用 CAPTCHA。"),
    "robots-honeypot": ("爬蟲規則與誘餌路徑", "一般資料頁可讀，但禁止的 /training-honeypot 會記錄事件並回傳 403。", "先讀 robots.txt、排除禁止路徑，只抓一般資料頁與正常連結。"),
    "tls-fingerprint": ("TLS ClientHello／JA3 指紋檢查", "TLS 交握尚未送出 HTTP 標頭前，HTTPS 反向代理會讀取 ClientHello 的 TLS 版本、cipher suites、擴充欄位、supported groups 與 point formats，計算 JA3 雜湊。此本機範例以「含現代瀏覽器常見 GREASE 值及 h2 ALPN」作為受控基線。", "請用 https://localhost:8443/tls-fingerprint 開啟一般瀏覽器，讓反向代理在交握時取得指紋。純 curl／requests 不會偽裝成瀏覽器 TLS 堆疊，會被刻意擋下；Python 範例使用 curl-cffi 的 Chrome impersonation。TLS 指紋不是身分驗證，正式環境應結合速率、帳號、工作階段與風險訊號。"),
}

TLS_PROXY_SECRET = os.getenv("TLS_PROXY_SECRET", "local-tls-demo-proxy-only")


@dataclass
class Event:
    at: float
    path: str
    status: int
    rule: str
    message: str
    headers: dict[str, str]
    details: dict[str, Any]


class DemoStore:
    def __init__(self) -> None:
        self.rate_hits: dict[str, deque[float]] = defaultdict(deque)
        self.sessions: set[str] = set()
        self.tokens: dict[str, tuple[str, float]] = {}
        self.captchas: dict[str, tuple[int, float]] = {}
        self.events: dict[str, deque[Event]] = defaultdict(lambda: deque(maxlen=30))

    def event(self, client: str, request: Request, status: int, rule: str, message: str, **details: Any) -> None:
        safe_headers = {k: v for k, v in request.headers.items() if k.lower() not in {"authorization", "proxy-authorization"}}
        self.events[client].appendleft(Event(time.time(), request.url.path, status, rule, message, safe_headers, details))


store = DemoStore()
app = FastAPI(title="Anti-crawler demo", docs_url=None, redoc_url=None)
templates = Jinja2Templates(directory=str(ROOT / "templates"))
app.mount("/static", StaticFiles(directory=str(ROOT / "static")), name="static")


@app.middleware("http")
async def assign_demo_client(request: Request, call_next: Any) -> Any:
    assigned = request.cookies.get("demo_client") or secrets.token_urlsafe(12)
    request.state.demo_client = assigned
    response = await call_next(request)
    if not request.cookies.get("demo_client"):
        response.set_cookie("demo_client", assigned, httponly=True, samesite="lax")
    return response


def client_id(demo_client: str | None, request: Request | None = None) -> str:
    if demo_client:
        return demo_client
    if request is not None:
        return request.state.demo_client
    return secrets.token_urlsafe(12)


def reply(request: Request, client: str, status: int, rule: str, message: str, data: Any = None, **extra: Any) -> JSONResponse:
    store.event(client, request, status, rule, message, **extra)
    body = {"ok": status < 400, "status": status, "rule": rule, "message": message, "data": data, **extra}
    headers = {"X-Training-Rule": rule}
    if "retry_after" in extra:
        headers["Retry-After"] = str(extra["retry_after"])
    return JSONResponse(body, status_code=status, headers=headers)


def browser_headers_present(request: Request) -> bool:
    return "text/html" in request.headers.get("accept", "").lower() and "mozilla" in request.headers.get("user-agent", "").lower()


def is_headless_user_agent(request: Request) -> bool:
    """Educational-only detection of the legacy HeadlessChrome UA product token."""
    return "headlesschrome" in request.headers.get("user-agent", "").lower()


def page_block(request: Request, demo: str, status: int, rule: str, reason: str, recovery: str, retry_after: int | None = None) -> HTMLResponse:
    headers = {"X-Training-Rule": rule}
    if retry_after is not None:
        headers["Retry-After"] = str(retry_after)
    return templates.TemplateResponse(request, "blocked.html", {"demo": demo, "reason": reason, "recovery": recovery, "status": status}, status_code=status, headers=headers)


def allow_rate_limited_page(request: Request, client: str) -> int | None:
    now = time.time()
    hits = store.rate_hits[client]
    while hits and hits[0] <= now - 10:
        hits.popleft()
    if len(hits) >= 5:
        return max(1, int(10 - (now - hits[0])) + 1)
    hits.append(now)
    return None


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    response = templates.TemplateResponse(request, "index.html", {"demos": DEMOS})
    if not request.cookies.get("demo_client"):
        response.set_cookie("demo_client", client_id(None), httponly=True, samesite="lax")
    return response


@app.get("/robots.txt", response_class=PlainTextResponse)
async def robots() -> str:
    return "User-agent: *\nDisallow: /training-honeypot\n"


@app.get("/training-honeypot")
async def honeypot(request: Request, demo_client: str | None = Cookie(default=None)) -> JSONResponse:
    client = client_id(demo_client, request)
    return reply(request, client, 403, "honeypot-hit", "已進入僅供觀測的誘餌路徑；此存取已被記錄並拒絕。")


@app.get("/session-gate/login", response_class=HTMLResponse)
async def session_login_page(request: Request) -> HTMLResponse:
    if request.cookies.get(SESSION_COOKIE) in store.sessions:
        return RedirectResponse("/session-gate", status_code=303)
    return templates.TemplateResponse(request, "login.html", {"error": None, "username": TRAINING_USERNAME, "password": TRAINING_PASSWORD})


@app.post("/session-gate/login", response_class=HTMLResponse)
async def session_login(request: Request) -> HTMLResponse:
    form = parse_qs((await request.body()).decode("utf-8"), keep_blank_values=True)
    username = form.get("username", [""])[0]
    password = form.get("password", [""])[0]
    if not secrets.compare_digest(username, TRAINING_USERNAME) or not secrets.compare_digest(password, TRAINING_PASSWORD):
        return templates.TemplateResponse(request, "login.html", {"error": "帳號或密碼不正確，尚未建立登入工作階段。", "username": TRAINING_USERNAME, "password": TRAINING_PASSWORD}, status_code=401)
    session_id = secrets.token_urlsafe(24)
    store.sessions.add(session_id)
    response = RedirectResponse("/session-gate", status_code=303)
    response.set_cookie(SESSION_COOKIE, session_id, httponly=True, samesite="lax")
    return response


@app.post("/session-gate/logout")
async def session_logout(request: Request) -> RedirectResponse:
    session_id = request.cookies.get(SESSION_COOKIE)
    if session_id:
        store.sessions.discard(session_id)
    response = RedirectResponse("/session-gate/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE)
    return response


@app.get("/rate-limit/reports/{report_id}", response_class=HTMLResponse)
async def rate_limit_report(request: Request, report_id: str) -> HTMLResponse:
    report = next((item for item in DATASET if item["id"] == report_id), None)
    if report is None:
        return HTMLResponse("找不到指定報告", status_code=404)
    client = client_id(request.cookies.get("demo_client"), request)
    retry = allow_rate_limited_page(request, client)
    if retry is not None:
        return page_block(request, "rate-limit", 429, "rate-limit", f"10 秒內已連續讀取 5 個報告頁面；請在 {retry} 秒後再試。", "等待 Retry-After 指定秒數，再繼續讀取下一份報告。", retry)
    details = [
        ("報告編號", report["id"]), ("指標名稱", report["name"]), ("統計期間", report["period"]),
        ("指數", report["value"]), ("報告發布時間", report["published"]), ("資料來源", "城市零售統計資料庫"),
        ("更新頻率", "每月"), ("計算方式", "以 2021 年平均值為 100"),
    ]
    return templates.TemplateResponse(request, "report.html", {"report": report, "details": details})


@app.get("/{demo}", response_class=HTMLResponse)
async def demo_page(request: Request, demo: str) -> HTMLResponse:
    if demo not in DEMOS:
        return HTMLResponse("找不到指定情境", status_code=404)
    client = client_id(request.cookies.get("demo_client"), request)
    rows: list[dict[str, str]] | None = None
    if demo == "basic":
        rows = DATASET
    elif demo == "rate-limit":
        retry = allow_rate_limited_page(request, client)
        if retry is not None:
            return page_block(request, demo, 429, "rate-limit", f"10 秒內已連續讀取 5 個索引或報告頁面；請在 {retry} 秒後再試。", "降低請求頻率後重新抓取同一頁。", retry)
        rows = DATASET
    elif demo == "header-policy":
        if not browser_headers_present(request):
            return page_block(request, demo, 403, "header-policy", "缺少一般 HTML 瀏覽器導覽所需的 Accept 或 User-Agent 標頭。", "以 text/html 的 Accept 與瀏覽器樣式 User-Agent 重新請求本頁。")
        rows = DATASET
    elif demo == "headless-header":
        if is_headless_user_agent(request):
            return page_block(request, demo, 403, "headless-user-agent", "User-Agent 含有 HeadlessChrome 標記，符合本頁設定的無頭模式特徵。", "這是僅供教材的標頭檢查；請改用一般瀏覽器設定或核准的測試方式。請注意，改寫 User-Agent 並不是正式防護的可靠繞過方式。")
        rows = DATASET
    elif demo == "session-gate":
        if request.cookies.get(SESSION_COOKIE) not in store.sessions:
            return RedirectResponse("/session-gate/login", status_code=303, headers={"X-Training-Rule": "session-required"})
        rows = DATASET
    elif demo == "robots-honeypot":
        rows = DATASET
    elif demo == "tls-fingerprint":
        trusted_proxy = request.headers.get("x-training-tls-proxy") == TLS_PROXY_SECRET
        ja3 = request.headers.get("x-training-tls-ja3", "")
        classification = request.headers.get("x-training-tls-classification", "")
        if not trusted_proxy:
            return page_block(request, demo, 403, "tls-proxy-required", "此頁必須透過本機 HTTPS TLS 指紋反向代理讀取；直接連到 HTTP 的 8000 埠不會有 ClientHello 可供檢查。", "請啟動 TLS 測試服務，並改用 https://localhost:8443/tls-fingerprint。")
        if len(ja3) != 32 or classification != "browser-like":
            shown = ja3[:12] if ja3 else "未取得"
            return page_block(request, demo, 403, "tls-fingerprint-mismatch", f"TLS ClientHello 指紋未符合本機的瀏覽器型態基線（JA3：{shown}…）。這次交握缺少範例要求的現代瀏覽器 GREASE 或 h2 ALPN 訊號。", "使用一般瀏覽器開啟本頁，或用 curl-cffi 的 Chrome impersonation 讀取並解析資料表。")
        rows = DATASET
    response = templates.TemplateResponse(request, "demo.html", {"demo": demo, "meta": DEMOS[demo], "rows": rows, "technique": TECHNIQUE_INFO[demo]})
    if not request.cookies.get("demo_client"):
        response.set_cookie("demo_client", client_id(None), httponly=True, samesite="lax")
    return response


@app.get("/api/events/{demo}")
async def events(request: Request, demo: str, demo_client: str | None = Cookie(default=None)) -> dict[str, Any]:
    client = client_id(demo_client, request)
    items = [
        {"at": e.at, "path": e.path, "status": e.status, "rule": e.rule, "message": e.message, "headers": e.headers, "details": e.details}
        for e in store.events[client] if demo in e.path or (demo == "robots-honeypot" and "honeypot" in e.rule)
    ]
    return {"events": items}


@app.post("/api/{demo}/{action}")
async def action(
    demo: str, action: str, request: Request, demo_client: str | None = Cookie(default=None),
    x_demo_client: str | None = Header(default=None), accept: str | None = Header(default=None),
) -> JSONResponse:
    client = client_id(demo_client, request)
    now = time.time()
    if demo not in DEMOS:
        return reply(request, client, 404, "unknown-demo", "找不到指定情境。")
    if demo == "rate-limit":
        hits = store.rate_hits[client]
        while hits and hits[0] <= now - 10:
            hits.popleft()
        if len(hits) >= 5:
            retry = max(1, int(10 - (now - hits[0])) + 1)
            return reply(request, client, 429, "rate-limit", "請求次數過多，請等待後再試。", retry_after=retry)
        hits.append(now)
        return reply(request, client, 200, "rate-limit", "本次請求已允許。", {"remaining": 5 - len(hits), "rows": DATASET})
    if demo == "header-policy":
        if x_demo_client != "training-browser" or not accept or "application/json" not in accept:
            return reply(request, client, 403, "header-policy", "缺少必要的示範請求標頭，或標頭值不正確。")
        return reply(request, client, 200, "header-policy", "請求標頭檢查已通過。", {"rows": DATASET})
    if demo == "session-gate":
        session_id = request.cookies.get(SESSION_COOKIE)
        if action == "logout":
            if session_id:
                store.sessions.discard(session_id)
            response = reply(request, client, 200, "session-cleared", "示範登入工作階段已清除。")
            response.delete_cookie(SESSION_COOKIE)
            return response
        if session_id not in store.sessions:
            return reply(request, client, 401, "session-required", "請先從 /session-gate/login 送出正確的登入表單。")
        return reply(request, client, 200, "session-valid", "已取得登入後的受保護資料。", {"rows": DATASET})
    if demo == "deferred-content":
        if request.headers.get("x-requested-with") != "XMLHttpRequest":
            return reply(request, client, 403, "deferred-request", "此資料表僅會回傳給頁面的非同步資料請求。")
        return reply(request, client, 200, "deferred-content", "資料表已在初始頁面回應後載入。", {"rows": DATASET})
    if demo == "js-token":
        if action == "issue":
            token = secrets.token_urlsafe(16)
            store.tokens[token] = (client, now + 30)
            return reply(request, client, 200, "token-issued", "已簽發 30 秒有效的一次性權杖。", {"token": token})
        payload = await request.json()
        token = payload.get("token", "")
        owner = store.tokens.pop(token, None)
        if not owner or owner[0] != client or owner[1] < now:
            return reply(request, client, 403, "token-invalid", "權杖不存在、已過期或已使用過。")
        return reply(request, client, 200, "token-valid", "權杖驗證已通過。", {"rows": DATASET})
    if demo == "captcha-sim":
        if action == "issue":
            answer = secrets.randbelow(8) + 2
            store.captchas[client] = (answer, now + 60)
            return reply(request, client, 200, "captcha-issued", "請完成訓練題目。", {"prompt": f"請計算：{answer - 2} + 2 = ?"})
        payload = await request.json()
        challenge = store.captchas.pop(client, None)
        if not challenge or challenge[1] < now or str(challenge[0]) != str(payload.get("answer")):
            return reply(request, client, 403, "captcha-failed", "挑戰答案錯誤或已過期。")
        return reply(request, client, 200, "captcha-passed", "訓練挑戰已完成。", {"rows": DATASET})
    if demo == "robots-honeypot":
        return reply(request, client, 200, "robots-info", "一般資料頁可讀取；僅供觀測的誘餌路徑會拒絕存取。", {"rows": DATASET})
    return reply(request, client, 400, "invalid-action", "不支援的操作。")


def main() -> None:
    import uvicorn
    uvicorn.run("anti_crawler_demo.app:app", host="127.0.0.1", port=8000, reload=True)

from fastapi.testclient import TestClient

from anti_crawler_demo.app import app, store


def client() -> TestClient:
    store.rate_hits.clear()
    store.sessions.clear()
    store.tokens.clear()
    store.captchas.clear()
    store.events.clear()
    return TestClient(app)


def test_index_and_robots_are_available() -> None:
    c = client()
    assert c.get("/").status_code == 200
    robots = c.get("/robots.txt")
    assert robots.status_code == 200
    assert "Disallow: /training-honeypot" in robots.text


def test_page_rules_are_applied_to_each_html_document() -> None:
    c = client()
    for scenario in ("basic", "rate-limit", "robots-honeypot"):
        page = c.get(f"/{scenario}")
        assert page.status_code == 200
        assert "2026 年 8 月城市零售指數" in page.text
        assert "R-101" in page.text
    header_blocked = c.get("/header-policy")
    assert header_blocked.status_code == 403
    assert header_blocked.headers["x-training-rule"] == "header-policy"
    header_passed = c.get("/header-policy", headers={"Accept": "text/html", "User-Agent": "Mozilla/5.0 training-browser"})
    assert header_passed.status_code == 200
    assert "R-101" in header_passed.text
    unauthenticated = c.get("/session-gate", follow_redirects=False)
    assert unauthenticated.status_code == 303
    assert unauthenticated.headers["location"] == "/session-gate/login"
    login_page = c.get("/session-gate/login")
    assert "learner@example.test" not in login_page.text
    assert "DemoPass!2026" not in login_page.text
    assert c.post("/session-gate/login", data={"username": "wrong@example.test", "password": "wrong"}).status_code == 401
    session_page = c.post("/session-gate/login", data={"username": "learner@example.test", "password": "DemoPass!2026"})
    assert session_page.status_code == 200
    assert "R-101" in session_page.text
    for scenario in ("deferred-content", "js-token", "captcha-sim"):
        page = c.get(f"/{scenario}")
        assert page.status_code == 200
        assert "R-101" not in page.text
    tls_direct = c.get("/tls-fingerprint")
    assert tls_direct.status_code == 403
    assert tls_direct.headers["x-training-rule"] == "tls-proxy-required"


def test_rate_limit_blocks_sixth_request() -> None:
    c = client()
    for _ in range(5):
        assert c.post("/api/rate-limit/check").status_code == 200
    blocked = c.post("/api/rate-limit/check")
    assert blocked.status_code == 429
    assert blocked.json()["retry_after"] >= 1
    assert blocked.headers["retry-after"] == str(blocked.json()["retry_after"])
    assert blocked.headers["x-training-rule"] == "rate-limit"


def test_rate_limit_covers_index_and_linked_report_pages() -> None:
    c = client()
    index = c.get("/rate-limit")
    assert index.status_code == 200
    assert '/rate-limit/reports/R-101' in index.text
    reports = {}
    for report_id in ("R-101", "R-102", "R-103", "R-104"):
        page = c.get(f"/rate-limit/reports/{report_id}")
        reports[report_id] = page
        assert page.status_code == 200
        assert "報告詳細資料" in page.text
    assert "2026-09-02 09:00" in reports["R-101"].text
    assert "2026-09-23 16:45" in reports["R-104"].text
    blocked = c.get("/rate-limit/reports/R-101")
    assert blocked.status_code == 429
    assert blocked.headers["x-training-rule"] == "rate-limit"
    assert "Retry-After" in blocked.text


def test_header_policy_and_session_gate() -> None:
    c = client()
    assert c.post("/api/header-policy/check").status_code == 403
    assert c.post("/api/header-policy/check", headers={"X-Demo-Client": "training-browser", "Accept": "application/json"}).status_code == 200
    assert c.post("/api/session-gate/read").status_code == 401
    c.post("/session-gate/login", data={"username": "learner@example.test", "password": "DemoPass!2026"})
    assert c.post("/api/session-gate/read").status_code == 200
    assert c.post("/api/session-gate/logout").status_code == 200
    assert c.post("/api/session-gate/read").status_code == 401


def test_deferred_content_has_its_own_single_request_requirement() -> None:
    c = client()
    assert c.post("/api/deferred-content/read").status_code == 403
    loaded = c.post("/api/deferred-content/read", headers={"X-Requested-With": "XMLHttpRequest"})
    assert loaded.status_code == 200
    assert len(loaded.json()["data"]["rows"]) == 6


def test_token_is_single_use_and_captcha_requires_answer() -> None:
    c = client()
    token = c.post("/api/js-token/issue").json()["data"]["token"]
    assert c.post("/api/js-token/use", json={"token": token}).status_code == 200
    assert c.post("/api/js-token/use", json={"token": token}).status_code == 403
    prompt = c.post("/api/captcha-sim/issue").json()["data"]["prompt"]
    answer = int("".join(char for char in prompt.split("+")[0] if char.isdigit())) + 2
    assert c.post("/api/captcha-sim/verify", json={"answer": answer}).status_code == 200


def test_tls_fingerprint_requires_trusted_proxy_and_browser_baseline() -> None:
    c = client()
    assert c.get("/tls-fingerprint").status_code == 403
    blocked = c.get("/tls-fingerprint", headers={"X-Training-TLS-Proxy": "local-tls-demo-proxy-only", "X-Training-TLS-JA3": "a" * 32, "X-Training-TLS-Classification": "non-browser-like"})
    assert blocked.status_code == 403
    accepted = c.get("/tls-fingerprint", headers={"X-Training-TLS-Proxy": "local-tls-demo-proxy-only", "X-Training-TLS-JA3": "a" * 32, "X-Training-TLS-Classification": "browser-like"})
    assert accepted.status_code == 200
    assert "R-101" in accepted.text

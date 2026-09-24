"""Use a real Playwright headless Chromium process against the training page."""

from playwright.sync_api import sync_playwright

from common import BASE_URL

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page()
    response = page.goto(f"{BASE_URL}/headless-header")
    print(response.status, response.headers.get("x-training-rule"))  # 403 headless-user-agent
    browser.close()

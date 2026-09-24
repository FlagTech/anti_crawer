"""Use a visible Playwright Chromium window, then read the rendered table."""

from playwright.sync_api import sync_playwright

from common import BASE_URL

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=False)
    page = browser.new_page()
    response = page.goto(f"{BASE_URL}/headless-header")
    page.locator("#dataset-table tbody tr").first.wait_for()
    print(response.status, page.locator("#dataset-table tbody tr").all_inner_texts())
    browser.close()

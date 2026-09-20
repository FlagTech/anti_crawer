"""Fill the manual training CAPTCHA prompt, then extract the rendered table."""
import re

from playwright.sync_api import sync_playwright
from common import BASE_URL

with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    page = browser.new_page()
    page.goto(f"{BASE_URL}/captcha-sim")
    prompt = page.locator("#captcha-prompt").inner_text()
    answer = sum(map(int, re.findall(r"\d+", prompt)))
    page.locator("#captcha-answer").fill(str(answer))
    page.locator("#captcha-submit").click()
    page.locator("#dataset-table:not([hidden]) tbody tr").first.wait_for()
    print(page.locator("#dataset-table tbody tr").all_inner_texts())
    browser.close()

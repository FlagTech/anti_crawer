"""Shared helpers for the executable crawler examples."""
from __future__ import annotations

import sys

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

BASE_URL = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:8000"


def rows_from_html(html: str) -> list[list[str]]:
    soup = BeautifulSoup(html, "html.parser")
    return [[cell.get_text(" ", strip=True) for cell in row.select("td")] for row in soup.select("#dataset-table tbody tr")]


def rows_from_browser(path: str) -> list[str]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.goto(f"{BASE_URL}{path}")
        page.locator("#dataset-table:not([hidden]) tbody tr").first.wait_for()
        rows = page.locator("#dataset-table tbody tr").all_inner_texts()
        browser.close()
    return rows

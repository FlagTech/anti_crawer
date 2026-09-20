"""Playwright executes the token workflow and waits for the rendered table."""
from common import rows_from_browser

print(rows_from_browser("/js-token"))

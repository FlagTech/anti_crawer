"""Fetch the whole page with a non-headless Chrome-shaped User-Agent for this lab."""

import requests

from common import BASE_URL, rows_from_html

response = requests.get(
    f"{BASE_URL}/headless-header",
    headers={"User-Agent": "Mozilla/5.0 Chrome/140.0"},
)
print(response.status_code, rows_from_html(response.text))

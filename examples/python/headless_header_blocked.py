"""Reproduce the training block using a legacy HeadlessChrome User-Agent token."""

import requests

from common import BASE_URL

response = requests.get(
    f"{BASE_URL}/headless-header",
    headers={"User-Agent": "Mozilla/5.0 HeadlessChrome/140.0"},
)
print(response.status_code, response.headers.get("X-Training-Rule"))

"""Fetch and parse the full table after supplying the required page headers."""
import requests
from common import BASE_URL, rows_from_html

response = requests.get(f"{BASE_URL}/header-policy", headers={"Accept": "text/html", "User-Agent": "Mozilla/5.0 training-browser"})
print(response.status_code, rows_from_html(response.text))

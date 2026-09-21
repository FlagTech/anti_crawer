"""Fetch the unprotected page and parse its static data table."""
import requests

from common import BASE_URL, rows_from_html

response = requests.get(f"{BASE_URL}/basic")
print(response.status_code, rows_from_html(response.text))

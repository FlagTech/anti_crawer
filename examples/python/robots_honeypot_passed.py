"""Fetch the normal data page and parse its table without entering the trap."""
import requests
from common import BASE_URL, rows_from_html

response = requests.get(f"{BASE_URL}/robots-honeypot")
print(response.status_code, rows_from_html(response.text))

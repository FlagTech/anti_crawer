"""A plain HTTP fetch cannot complete the page's controlled challenge flow."""
import requests
from common import BASE_URL, rows_from_html

print(rows_from_html(requests.get(f"{BASE_URL}/captcha-sim").text))
